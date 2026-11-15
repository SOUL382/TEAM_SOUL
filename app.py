import os
import sqlite3
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)
app.secret_key = os.environ.get("SECRET_KEY", "local-development-key-change-in-render")
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "tournaments.db"))
PLACEMENT_POINTS = {1: 10, 2: 6, 3: 5, 4: 4, 5: 3, 6: 2, 7: 1, 8: 1}

def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def init_db():
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS tournaments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          game TEXT NOT NULL DEFAULT 'BGMI',
          status TEXT NOT NULL DEFAULT 'Upcoming',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS teams (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tournament_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          players TEXT NOT NULL DEFAULT '',
          highlighted INTEGER NOT NULL DEFAULT 0,
          UNIQUE(tournament_id, name),
          FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS results (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tournament_id INTEGER NOT NULL,
          match_number INTEGER NOT NULL,
          map_name TEXT NOT NULL,
          team_name TEXT NOT NULL,
          placement INTEGER NOT NULL,
          kills INTEGER NOT NULL,
          placement_points INTEGER NOT NULL DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS scheduled_matches (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tournament_id INTEGER NOT NULL,
          match_number INTEGER NOT NULL,
          match_date TEXT NOT NULL,
          map_name TEXT NOT NULL,
          start_time_trt TEXT NOT NULL,
          start_time_ist TEXT NOT NULL,
          UNIQUE(tournament_id, match_number),
          FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS grand_finals_map_selection (
          tournament_id INTEGER PRIMARY KEY,
          showmatch_winner TEXT NOT NULL,
          banned_map TEXT NOT NULL,
          selected_map TEXT NOT NULL,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
        );
        """)
        # Upgrade databases created by the earlier tracker version.
        db.execute("CREATE INDEX IF NOT EXISTS idx_results_tournament ON results(tournament_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_teams_tournament ON teams(tournament_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_schedule_tournament ON scheduled_matches(tournament_id)")
        # Create the stage-specific Gauntlet board once; keep the 39-team PMGC board intact.
        gauntlet_teams = [
            "4K Esports", "4Thrives", "AK Gold Esports", "All Gamers",
            "Aurora Gaming", "Gaming Stars Esports", "Hustler Crew", "iKURD Esports",
            "Nongshim RedForce", "RoW Esports", "S2G Esports", "Sharper Esports",
            "Team SouL", "The MongolZ", "Wolves Esports", "XForce Rejects"
        ]
        row = db.execute("SELECT id FROM tournaments WHERE name=?", ("PMGC 2026 - The Gauntlet",)).fetchone()
        if row:
            gauntlet_id = row["id"]
        else:
            cur = db.execute("INSERT INTO tournaments(name,game,status) VALUES(?,?,?)",
                             ("PMGC 2026 - The Gauntlet", "BGMI", "Upcoming"))
            gauntlet_id = cur.lastrowid
        for team in gauntlet_teams:
            db.execute("INSERT OR IGNORE INTO teams(tournament_id,name) VALUES(?,?)", (gauntlet_id, team))
        # Create separate Red and Green group scoreboards with editable Gauntlet placeholders.
        group_rosters = {
            "PMGC 2026 - Green Group": [
                "Nigma Galaxy", "AlUla Club", "Team Flash", "eArena",
                "BRX MSM Esports", "Horaa Esports", "FURIA", "OLD NOT",
                "Weibo Gaming", "DRX", "Boars Gaming",
                "Gauntlet #7", "Gauntlet #10", "Gauntlet #11", "Gauntlet #14", "Gauntlet #15"
            ],
            "PMGC 2026 - Red Group": [
                "R8 Esports", "Geekay Esports", "Bigetron by Vitality", "BUF Esports",
                "Selibon", "Trained to Kill", "Alpha7 Esports", "GOAT Team",
                "LGD Gaming", "Dplus KIA", "Varrel",
                "Gauntlet #8", "Gauntlet #9", "Gauntlet #12", "Gauntlet #13", "Gauntlet #16"
            ]
        }
        for group_name, roster in group_rosters.items():
            group_row = db.execute("SELECT id FROM tournaments WHERE name=?", (group_name,)).fetchone()
            if group_row:
                group_id = group_row["id"]
            else:
                group_cur = db.execute(
                    "INSERT INTO tournaments(name,game,status) VALUES(?,?,?)",
                    (group_name, "BGMI", "Upcoming")
                )
                group_id = group_cur.lastrowid
            for team_name in roster:
                db.execute(
                    "INSERT OR IGNORE INTO teams(tournament_id,name) VALUES(?,?)",
                    (group_id, team_name)
                )

            # Seed the confirmed 12-match Group Stage dates; maps and start times remain TBA until officially published.
            if not db.execute("SELECT 1 FROM scheduled_matches WHERE tournament_id=? LIMIT 1", (group_id,)).fetchone():
                group_dates = (
                    ("2026-11-29", "2026-11-30")
                    if "Green Group" in group_name
                    else ("2026-12-02", "2026-12-03")
                )
                for day_index, match_date in enumerate(group_dates):
                    for slot in range(6):
                        match_no = day_index * 6 + slot + 1
                        db.execute("""INSERT INTO scheduled_matches
                            (tournament_id,match_number,match_date,map_name,start_time_trt,start_time_ist)
                            VALUES(?,?,?,?,?,?)""",
                            (group_id, match_no, match_date, "TBA", "TBA", "TBA"))

        # Seed Last Chance and Grand Finals as independent stage scoreboards.
        stage_rosters = {
            "PMGC 2026 - Last Chance": (
                [f"Red Group #{rank}" for rank in range(4, 12)] +
                [f"Green Group #{rank}" for rank in range(4, 12)]
            ),
            "PMGC 2026 - Grand Finals": (
                ["Host Country Invitee"] +
                [f"Gauntlet Qualifier #{rank}" for rank in range(1, 7)] +
                [f"Group Stage Qualifier #{rank}" for rank in range(1, 7)] +
                [f"Last Chance Qualifier #{rank}" for rank in range(1, 4)]
            )
        }
        for stage_name, roster in stage_rosters.items():
            stage_row = db.execute("SELECT id FROM tournaments WHERE name=?", (stage_name,)).fetchone()
            if stage_row:
                stage_id = stage_row["id"]
            else:
                stage_cur = db.execute(
                    "INSERT INTO tournaments(name,game,status) VALUES(?,?,?)",
                    (stage_name, "BGMI", "Upcoming")
                )
                stage_id = stage_cur.lastrowid
            for team_name in roster:
                db.execute(
                    "INSERT OR IGNORE INTO teams(tournament_id,name) VALUES(?,?)",
                    (stage_id, team_name)
                )
            if not db.execute("SELECT 1 FROM scheduled_matches WHERE tournament_id=? LIMIT 1", (stage_id,)).fetchone():
                if "Last Chance" in stage_name:
                    stage_days = [("2026-12-05", 6), ("2026-12-06", 6)]
                else:
                    stage_days = [("2026-12-11", 6), ("2026-12-12", 6), ("2026-12-13", 7)]
                match_no = 1
                for match_date, matches_that_day in stage_days:
                    for _ in range(matches_that_day):
                        db.execute("""INSERT INTO scheduled_matches
                            (tournament_id,match_number,match_date,map_name,start_time_trt,start_time_ist)
                            VALUES(?,?,?,?,?,?)""",
                            (stage_id, match_no, match_date, "TBA", "TBA", "TBA"))
                        match_no += 1

        if not db.execute("SELECT 1 FROM scheduled_matches WHERE tournament_id=? LIMIT 1", (gauntlet_id,)).fetchone():
            maps = ["Rondo", "Erangel", "Erangel", "Erangel", "Miramar", "Miramar"]
            times_trt = ["15:00", "15:40", "16:20", "17:00", "17:40", "18:20"]
            times_ist = ["17:30", "18:10", "18:50", "19:30", "20:10", "20:50"]
            for day, date in enumerate(("2026-11-26", "2026-11-27")):
                for slot, map_name in enumerate(maps):
                    match_no = day * 6 + slot + 1
                    db.execute("""INSERT INTO scheduled_matches
                        (tournament_id,match_number,match_date,map_name,start_time_trt,start_time_ist)
                        VALUES(?,?,?,?,?,?)""",
                        (gauntlet_id, match_no, date, map_name, times_trt[slot], times_ist[slot]))

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error": "Admin login required"}), 401
        return fn(*args, **kwargs)
    return wrapped

def error(message, status=400):
    return jsonify({"error": message}), status

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/admin")
def admin_page():
    return send_from_directory(BASE_DIR, "admin.html")

@app.route("/style.css")
def stylesheet():
    return send_from_directory(BASE_DIR, "style.css", mimetype="text/css")

@app.route("/script.js")
def public_script():
    return send_from_directory(BASE_DIR, "script.js", mimetype="application/javascript")

@app.route("/admin.js")
def admin_script():
    return send_from_directory(BASE_DIR, "admin.js", mimetype="application/javascript")

@app.route("/api/tournaments", methods=["GET"])
def get_tournaments():
    with connect_db() as db:
        rows = db.execute("SELECT * FROM tournaments ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/tournaments", methods=["POST"])
@admin_required
def add_tournament():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return error("Tournament name is required")
    game = str(data.get("game", "BGMI")).strip() or "BGMI"
    status = str(data.get("status", "Upcoming")).strip() or "Upcoming"
    with connect_db() as db:
        cur = db.execute("INSERT INTO tournaments(name, game, status) VALUES(?,?,?)", (name, game, status))
        tid = cur.lastrowid
    return jsonify({"id": tid, "name": name, "game": game, "status": status}), 201

@app.route("/api/tournaments/<int:tid>", methods=["PATCH"])
@admin_required
def update_tournament(tid):
    data = request.get_json(silent=True) or {}
    fields = {k: str(data[k]).strip() for k in ("name", "status", "game") if k in data}
    if not fields:
        return error("No tournament fields supplied")
    sql = ", ".join(f"{k}=?" for k in fields)
    with connect_db() as db:
        cur = db.execute(f"UPDATE tournaments SET {sql} WHERE id=?", (*fields.values(), tid))
        if not cur.rowcount:
            return error("Tournament not found", 404)
    return jsonify({"ok": True})

@app.route("/api/teams", methods=["GET", "POST"])
def teams_api():
    if request.method == "POST" and not session.get("admin"):
        return error("Admin login required", 401)
    tid = request.args.get("tournament_id", type=int)
    if request.method == "GET":
        if not tid:
            return error("tournament_id is required")
        with connect_db() as db:
            rows = db.execute("SELECT * FROM teams WHERE tournament_id=? ORDER BY name", (tid,)).fetchall()
        return jsonify([dict(r) for r in rows])
    data = request.get_json(silent=True) or {}
    try:
        tid = int(data["tournament_id"])
        name = str(data["name"]).strip()
        players = str(data.get("players", "")).strip()
        if not name:
            return error("Team name is required")
        with connect_db() as db:
            cur = db.execute("INSERT INTO teams(tournament_id,name,players) VALUES(?,?,?)", (tid, name, players))
        return jsonify({"id": cur.lastrowid, "name": name}), 201
    except sqlite3.IntegrityError:
        return error("That team is already added, or the tournament does not exist")
    except (KeyError, ValueError, TypeError):
        return error("Valid tournament and team name are required")

@app.route("/api/teams/bulk", methods=["POST"])
@admin_required
def bulk_add_teams():
    data = request.get_json(silent=True) or {}
    try:
        tid = int(data.get("tournament_id"))
    except (TypeError, ValueError):
        return error("A valid tournament is required")
    raw_teams = data.get("teams", [])
    if not isinstance(raw_teams, list) or not raw_teams:
        return error("Paste at least one team name")
    with connect_db() as db:
        if not db.execute("SELECT id FROM tournaments WHERE id=?", (tid,)).fetchone():
            return error("Tournament not found", 404)
        added, skipped = [], []
        for item in raw_teams:
            if isinstance(item, str):
                name, players = item.strip(), ""
            elif isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                players = str(item.get("players", "")).strip()
            else:
                continue
            if not name:
                continue
            exists = db.execute(
                "SELECT id FROM teams WHERE tournament_id=? AND name=? COLLATE NOCASE",
                (tid, name)
            ).fetchone()
            if exists:
                skipped.append(name)
                continue
            db.execute(
                "INSERT INTO teams(tournament_id,name,players) VALUES(?,?,?)",
                (tid, name, players)
            )
            added.append(name)
    return jsonify({"added": added, "added_count": len(added),
                    "skipped": skipped, "skipped_count": len(skipped)}), 201

@app.route("/api/teams/<int:team_id>", methods=["PATCH"])
@admin_required
def update_team(team_id):
    data = request.get_json(silent=True) or {}
    allowed = {k: data[k] for k in ("name", "players", "highlighted") if k in data}
    if not allowed:
        return error("No team fields supplied")
    if "highlighted" in allowed:
        allowed["highlighted"] = 1 if allowed["highlighted"] else 0
    if "name" in allowed:
        allowed["name"] = str(allowed["name"]).strip()
        if not allowed["name"]:
            return error("Team name cannot be blank")
    with connect_db() as db:
        current = db.execute("SELECT tournament_id,name FROM teams WHERE id=?", (team_id,)).fetchone()
        if not current:
            return error("Team not found", 404)
        if "name" in allowed and allowed["name"].casefold() != current["name"].casefold():
            duplicate = db.execute(
                "SELECT id FROM teams WHERE tournament_id=? AND name=? COLLATE NOCASE AND id<>?",
                (current["tournament_id"], allowed["name"], team_id)
            ).fetchone()
            if duplicate:
                return error("Another team already has that name")
            db.execute(
                "UPDATE results SET team_name=? WHERE tournament_id=? AND team_name=? COLLATE NOCASE",
                (allowed["name"], current["tournament_id"], current["name"])
            )
        sql = ", ".join(f"{k}=?" for k in allowed)
        db.execute(f"UPDATE teams SET {sql} WHERE id=?", (*allowed.values(), team_id))
    return jsonify({"ok": True})

@app.route("/api/results", methods=["GET", "POST"])
def results_api():
    if request.method == "POST" and not session.get("admin"):
        return error("Admin login required", 401)
    if request.method == "GET":
        tid = request.args.get("tournament_id", type=int)
        query = "SELECT * FROM results"
        params = []
        if tid:
            query += " WHERE tournament_id=?"
            params.append(tid)
        query += " ORDER BY match_number DESC, placement ASC"
        with connect_db() as db:
            rows = db.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    data = request.get_json(silent=True) or {}
    try:
        tid = int(data["tournament_id"])
        match = int(data["match_number"])
        placement = int(data["placement"])
        kills = int(data["kills"])
        map_name = str(data["map_name"]).strip()
        team_name = str(data["team_name"]).strip()
        pp = int(data.get("placement_points", PLACEMENT_POINTS.get(placement, 0)))
        if match < 1 or placement < 1 or kills < 0 or pp < 0 or not map_name or not team_name:
            return error("Check match, placement, map, team and score values")
        with connect_db() as db:
            exists = db.execute("SELECT id FROM tournaments WHERE id=?", (tid,)).fetchone()
            if not exists:
                return error("Tournament not found", 404)
            cur = db.execute("""INSERT INTO results
              (tournament_id,match_number,map_name,team_name,placement,kills,placement_points)
              VALUES(?,?,?,?,?,?,?)""", (tid,match,map_name,team_name,placement,kills,pp))
        return jsonify({"id": cur.lastrowid, "total_points": kills + pp}), 201
    except (KeyError, ValueError, TypeError):
        return error("All score fields must be valid numbers and text")


@app.route("/api/results/bulk", methods=["POST"])
@admin_required
def bulk_results():
    data = request.get_json(silent=True) or {}
    try:
        tid = int(data.get("tournament_id"))
        match = int(data.get("match_number"))
        map_name = str(data.get("map_name", "")).strip()
        entries = data.get("entries")
        if not map_name or match < 1 or not isinstance(entries, list):
            return error("Choose a valid match and map, then enter every team's score")
        with connect_db() as db:
            tournament = db.execute("SELECT id FROM tournaments WHERE id=?", (tid,)).fetchone()
            if not tournament:
                return error("Tournament not found", 404)
            teams = db.execute("SELECT name FROM teams WHERE tournament_id=? ORDER BY name", (tid,)).fetchall()
            team_names = [r["name"] for r in teams]
            if not team_names or len(entries) != len(team_names):
                return error("Submit one score for every registered team")
            scheduled = db.execute(
                "SELECT map_name FROM scheduled_matches WHERE tournament_id=? AND match_number=?",
                (tid, match)
            ).fetchone()
            if scheduled and scheduled["map_name"].casefold() != map_name.casefold():
                return error("The selected map does not match this scheduled match")
            submitted = {}
            placements = set()
            for item in entries:
                if not isinstance(item, dict):
                    return error("Invalid team score row")
                team = str(item.get("team_name", "")).strip()
                try:
                    placement, kills = int(item.get("placement")), int(item.get("kills"))
                except (TypeError, ValueError):
                    return error("Every team needs a placement and kill count")
                key = team.casefold()
                if key not in {n.casefold() for n in team_names} or key in submitted:
                    return error("Team names must match the registered teams exactly once")
                if placement < 1 or placement > len(team_names) or placement in placements or kills < 0:
                    return error("Placements must be unique and kills cannot be negative")
                placements.add(placement)
                submitted[key] = (team, placement, kills)
            if len(submitted) != len(team_names) or len(placements) != len(team_names):
                return error("Enter a unique placement for every team")
            for team, placement, kills in submitted.values():
                pp = PLACEMENT_POINTS.get(placement, 0)
                db.execute(
                    "DELETE FROM results WHERE tournament_id=? AND match_number=? AND team_name=? COLLATE NOCASE",
                    (tid, match, team)
                )
                db.execute("""INSERT INTO results
                    (tournament_id,match_number,map_name,team_name,placement,kills,placement_points)
                    VALUES(?,?,?,?,?,?,?)""",
                    (tid, match, map_name, team, placement, kills, pp)
                )
        return jsonify({"ok": True, "saved": len(entries), "match_number": match})
    except (TypeError, ValueError):
        return error("Tournament and match values must be valid numbers")

@app.route("/api/qualification")
def qualification():
    tid = request.args.get("tournament_id", type=int)
    if not tid:
        return error("tournament_id is required")
    with connect_db() as db:
        teams = [r["name"] for r in db.execute(
            "SELECT name FROM teams WHERE tournament_id=? ORDER BY name", (tid,)
        ).fetchall()]
        scheduled_count = db.execute(
            "SELECT COUNT(*) FROM scheduled_matches WHERE tournament_id=?", (tid,)
        ).fetchone()[0]
        match_rows = db.execute(
            "SELECT match_number, team_name FROM results WHERE tournament_id=?",
            (tid,)
        ).fetchall()
        teams_by_match = {}
        for row in match_rows:
            teams_by_match.setdefault(row["match_number"], set()).add(row["team_name"].casefold())
        registered = {name.casefold() for name in teams}
        complete_matches = sum(1 for names in teams_by_match.values()
                               if registered and registered.issubset(names))
        rows = db.execute("""
            SELECT t.name AS team_name,
                   COALESCE(SUM(r.kills), 0) AS kills,
                   COALESCE(SUM(r.placement_points), 0) AS placement_points,
                   COALESCE(SUM(r.kills+r.placement_points), 0) AS total_points
            FROM teams t
            LEFT JOIN results r ON r.tournament_id=t.tournament_id
                AND r.team_name=t.name COLLATE NOCASE
            WHERE t.tournament_id=?
            GROUP BY t.id,t.name
            HAVING COUNT(r.id) > 0
            ORDER BY total_points DESC, kills DESC, placement_points DESC, t.name COLLATE NOCASE
        """, (tid,)).fetchall()
    required = scheduled_count or 12
    locked = bool(teams) and complete_matches >= required
    ranked = [dict(r, rank=i+1) for i,r in enumerate(rows)]
    return jsonify({
        "complete_matches": complete_matches,
        "required_matches": required,
        "locked": locked,
        "tiebreaker": "Total points, then kills, then placement points, then team name",
        "qualified": ranked[:6],
        "provisional": not locked
    })

@app.route("/api/group-qualification")
def group_qualification():
    tid = request.args.get("tournament_id", type=int)
    if not tid:
        return error("tournament_id is required")
    with connect_db() as db:
        tournament = db.execute("SELECT name FROM tournaments WHERE id=?", (tid,)).fetchone()
        if not tournament or "Group" not in tournament["name"]:
            return error("This tracker is only available for Red and Green Groups", 400)
        teams = [r["name"] for r in db.execute(
            "SELECT name FROM teams WHERE tournament_id=? ORDER BY name", (tid,)
        ).fetchall()]
        scheduled_count = db.execute(
            "SELECT COUNT(*) FROM scheduled_matches WHERE tournament_id=?", (tid,)
        ).fetchone()[0]
        match_rows = db.execute(
            "SELECT match_number, team_name FROM results WHERE tournament_id=?", (tid,)
        ).fetchall()
        teams_by_match = {}
        for row in match_rows:
            teams_by_match.setdefault(row["match_number"], set()).add(row["team_name"].casefold())
        registered = {name.casefold() for name in teams}
        complete_matches = sum(1 for names in teams_by_match.values()
                               if registered and registered.issubset(names))
        rows = db.execute("""
            SELECT t.name AS team_name,
                   COALESCE(SUM(r.kills), 0) AS kills,
                   COALESCE(SUM(r.placement_points), 0) AS placement_points,
                   COALESCE(SUM(r.kills+r.placement_points), 0) AS total_points
            FROM teams t
            LEFT JOIN results r ON r.tournament_id=t.tournament_id
                AND r.team_name=t.name COLLATE NOCASE
            WHERE t.tournament_id=?
            GROUP BY t.id,t.name
            ORDER BY total_points DESC, kills DESC, placement_points DESC, t.name COLLATE NOCASE
        """, (tid,)).fetchall()
    required = scheduled_count or 12
    locked = bool(teams) and complete_matches >= required
    ranked = []
    for i, row in enumerate(rows):
        item = dict(row, rank=i+1)
        item["status"] = ("Grand Finals" if i < 3 else
                          "Last Chance" if i < 11 else "Eliminated")
        ranked.append(item)
    return jsonify({
        "complete_matches": complete_matches,
        "required_matches": required,
        "locked": locked,
        "tiebreaker": "Total points, then kills, then placement points, then team name",
        "teams": ranked
    })



@app.route("/api/last-chance-qualification")
def last_chance_qualification():
    tid = request.args.get("tournament_id", type=int)
    if not tid:
        return error("tournament_id is required")
    with connect_db() as db:
        tournament = db.execute("SELECT name FROM tournaments WHERE id=?", (tid,)).fetchone()
        if not tournament or "Last Chance" not in tournament["name"]:
            return error("This tracker is only available for the Last Chance stage", 400)
        teams = [r["name"] for r in db.execute(
            "SELECT name FROM teams WHERE tournament_id=? ORDER BY name", (tid,)
        ).fetchall()]
        scheduled_count = db.execute(
            "SELECT COUNT(*) FROM scheduled_matches WHERE tournament_id=?", (tid,)
        ).fetchone()[0]
        match_rows = db.execute(
            "SELECT match_number, team_name FROM results WHERE tournament_id=?", (tid,)
        ).fetchall()
        teams_by_match = {}
        for row in match_rows:
            teams_by_match.setdefault(row["match_number"], set()).add(row["team_name"].casefold())
        registered = {name.casefold() for name in teams}
        complete_matches = sum(1 for names in teams_by_match.values()
                               if registered and registered.issubset(names))
        rows = db.execute("""
            SELECT t.name AS team_name,
                   COALESCE(SUM(r.kills), 0) AS kills,
                   COALESCE(SUM(r.placement_points), 0) AS placement_points,
                   COALESCE(SUM(r.kills+r.placement_points), 0) AS total_points
            FROM teams t
            LEFT JOIN results r ON r.tournament_id=t.tournament_id
                AND r.team_name=t.name COLLATE NOCASE
            WHERE t.tournament_id=?
            GROUP BY t.id,t.name
            ORDER BY total_points DESC, kills DESC, placement_points DESC, t.name COLLATE NOCASE
        """, (tid,)).fetchall()
    required = scheduled_count or 12
    locked = len(teams) == 16 and complete_matches >= required
    ranked = []
    for i, row in enumerate(rows):
        item = dict(row, rank=i+1)
        item["status"] = "Grand Finals" if i < 3 else "Eliminated"
        ranked.append(item)
    return jsonify({
        "complete_matches": complete_matches,
        "required_matches": required,
        "locked": locked,
        "tiebreaker": "Total points, then kills, then placement points, then team name",
        "teams": ranked
    })


@app.route("/api/smash-rule")
def smash_rule():
    tid = request.args.get("tournament_id", type=int)
    if not tid:
        return error("tournament_id is required")
    with connect_db() as db:
        tournament = db.execute("SELECT name FROM tournaments WHERE id=?", (tid,)).fetchone()
        if not tournament or "Grand Finals" not in tournament["name"]:
            return error("This tracker is only available for Grand Finals", 400)
        teams = [r["name"] for r in db.execute(
            "SELECT name FROM teams WHERE tournament_id=? ORDER BY name", (tid,)
        ).fetchall()]
        if len(teams) != 16:
            return error("Grand Finals must have 16 registered teams", 400)
        result_rows = db.execute("""
            SELECT match_number, team_name, placement, kills, placement_points
            FROM results WHERE tournament_id=? ORDER BY match_number, placement
        """, (tid,)).fetchall()
        by_match = {}
        for row in result_rows:
            by_match.setdefault(row["match_number"], []).append(dict(row))
        registered = {name.casefold() for name in teams}
        complete = {
            n for n, rows in by_match.items()
            if registered.issubset({r["team_name"].casefold() for r in rows})
        }
        def totals_through(last_match):
            totals = {name.casefold(): {"team_name": name, "kills": 0,
                      "placement_points": 0, "total_points": 0} for name in teams}
            for match_no, rows in by_match.items():
                if match_no > last_match or match_no not in complete:
                    continue
                for row in rows:
                    item = totals.get(row["team_name"].casefold())
                    if item:
                        item["kills"] += row["kills"]
                        item["placement_points"] += row["placement_points"]
                        item["total_points"] += row["kills"] + row["placement_points"]
            return sorted(totals.values(), key=lambda x: (
                -x["total_points"], -x["kills"], -x["placement_points"],
                x["team_name"].casefold()
            ))
        completed_count = 0
        while completed_count + 1 in complete:
            completed_count += 1
        threshold = None
        if completed_count >= 12:
            after_12 = totals_through(12)
            threshold = after_12[0]["total_points"] + 10 if after_12 else None
        eligible = set()
        champion = None
        champion_match = None
        if threshold is not None:
            for match_no in range(13, min(completed_count, 19) + 1):
                before = totals_through(match_no - 1)
                eligible = {x["team_name"].casefold() for x in before
                            if x["total_points"] >= threshold}
                winners = [r for r in by_match.get(match_no, [])
                           if r["placement"] == 1 and r["team_name"].casefold() in eligible]
                if winners:
                    champion = winners[0]["team_name"]
                    champion_match = match_no
                    break
        final_fallback = False
        if champion is None and completed_count >= 19:
            final_board = totals_through(19)
            champion = final_board[0]["team_name"] if final_board else None
            champion_match = 19
            final_fallback = True
        latest_completed = completed_count
        current_board = totals_through(latest_completed)
        current_eligible = []
        if threshold is not None and champion is None:
            current_eligible = [x for x in current_board if x["total_points"] >= threshold]
        status = ("CHAMPION CONFIRMED" if champion else
                  "MATCH POINT ACTIVE" if threshold is not None else
                  "WAITING FOR MATCH 12")
    return jsonify({
        "complete_matches": completed_count,
        "required_matches": 19,
        "match_12_complete": 12 in complete,
        "threshold": threshold,
        "eligible_teams": current_eligible,
        "champion": champion,
        "champion_match": champion_match,
        "fallback": final_fallback,
        "status": status,
        "tiebreaker": "Total points, then kills, then placement points, then team name",
        "standings": current_board
    })


@app.route("/api/grand-finals-map-selection", methods=["GET", "POST"])
def grand_finals_map_selection():
    tid = request.args.get("tournament_id", type=int)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        try:
            tid = int(data.get("tournament_id"))
        except (TypeError, ValueError):
            return error("A valid Grand Finals tournament is required")
        if not session.get("admin"):
            return error("Admin login required", 401)
    if not tid:
        return error("tournament_id is required")
    with connect_db() as db:
        tournament = db.execute("SELECT name FROM tournaments WHERE id=?", (tid,)).fetchone()
        if not tournament or tournament["name"] != "PMGC 2026 - Grand Finals":
            return error("This tracker is only available for Grand Finals", 400)
        teams = [r["name"] for r in db.execute(
            "SELECT name FROM teams WHERE tournament_id=? ORDER BY name", (tid,)
        ).fetchall()]
        rows = db.execute("""
            SELECT match_number, team_name, placement, kills, placement_points
            FROM results WHERE tournament_id=? AND match_number<=18
            ORDER BY match_number, placement
        """, (tid,)).fetchall()
        by_match = {}
        for row in rows:
            by_match.setdefault(row["match_number"], []).append(dict(row))
        registered = {name.casefold() for name in teams}
        complete = {
            n for n, match_rows in by_match.items()
            if registered.issubset({r["team_name"].casefold() for r in match_rows})
        }
        completed_count = 0
        while completed_count + 1 in complete:
            completed_count += 1
        totals = {name.casefold(): {"team_name": name, "kills": 0,
                  "placement_points": 0, "total_points": 0} for name in teams}
        for match_no, match_rows in by_match.items():
            if match_no not in complete or match_no > 18:
                continue
            for row in match_rows:
                item = totals.get(row["team_name"].casefold())
                if item:
                    item["kills"] += row["kills"]
                    item["placement_points"] += row["placement_points"]
                    item["total_points"] += row["kills"] + row["placement_points"]
        leaderboard = sorted(totals.values(), key=lambda x: (
            -x["total_points"], -x["kills"], -x["placement_points"],
            x["team_name"].casefold()
        ))
        leader = leaderboard[0] if completed_count >= 18 and leaderboard else None
        saved = db.execute(
            "SELECT showmatch_winner,banned_map,selected_map,updated_at "
            "FROM grand_finals_map_selection WHERE tournament_id=?", (tid,)
        ).fetchone()
        if request.method == "POST":
            if len(teams) != 16:
                return error("Grand Finals must have 16 registered teams", 400)
            if completed_count < 18 or not leader:
                return error("Complete all 16 team results through Match 18 before recording the map selection")
            winner = str(data.get("showmatch_winner", "")).strip()
            banned = str(data.get("banned_map", "")).strip()
            selected = str(data.get("selected_map", "")).strip()
            if not winner or not banned or not selected:
                return error("Enter the Showmatch winner, banned map and Match 19 selected map")
            if winner.casefold() not in registered:
                return error("Showmatch winner must be one of the registered Grand Finals teams")
            if banned.casefold() == selected.casefold():
                return error("The Match 19 map cannot be the map banned by the Showmatch winner")
            db.execute("""
                INSERT INTO grand_finals_map_selection
                    (tournament_id,showmatch_winner,banned_map,selected_map,updated_at)
                VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(tournament_id) DO UPDATE SET
                    showmatch_winner=excluded.showmatch_winner,
                    banned_map=excluded.banned_map,
                    selected_map=excluded.selected_map,
                    updated_at=CURRENT_TIMESTAMP
            """, (tid, winner, banned, selected))
            saved = db.execute(
                "SELECT showmatch_winner,banned_map,selected_map,updated_at "
                "FROM grand_finals_map_selection WHERE tournament_id=?", (tid,)
            ).fetchone()
    saved_data = dict(saved) if saved else None
    return jsonify({
        "match_18_complete": completed_count >= 18,
        "complete_matches": completed_count,
        "leader_after_match_18": leader,
        "selection": saved_data
    })


@app.route("/api/session")
def session_status():
    return jsonify({"admin": bool(session.get("admin"))})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    password = os.environ.get("ADMIN_PASSWORD")
    password_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    supplied = str(data.get("password", ""))
    valid = (
        password is not None and supplied == password
    ) or (
        password_hash is not None and check_password_hash(password_hash, supplied)
    )
    if not valid:
        return error("Invalid password or admin password not configured", 401)
    session["admin"] = True
    return jsonify({"ok": True})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/standings")
def standings():
    tid = request.args.get("tournament_id", type=int)
    if not tid:
        return error("tournament_id is required")
    with connect_db() as db:
        rows = db.execute("""
            SELECT t.name AS team_name,
                   t.highlighted AS highlighted,
                   COALESCE(SUM(r.kills), 0) AS total_kills,
                   COALESCE(SUM(r.placement_points), 0) AS placement_points,
                   COALESCE(SUM(r.kills + r.placement_points), 0) AS total_points,
                   COUNT(DISTINCT r.match_number) AS matches_played
            FROM teams t
            LEFT JOIN results r
              ON r.tournament_id=t.tournament_id
             AND r.team_name=t.name COLLATE NOCASE
            WHERE t.tournament_id=?
            GROUP BY t.id, t.name, t.highlighted
            ORDER BY total_points DESC, total_kills DESC,
                     placement_points DESC, t.name COLLATE NOCASE
        """, (tid,)).fetchall()
    return jsonify([dict(row, rank=i+1) for i, row in enumerate(rows)])


@app.route("/api/schedule")
def schedule():
    tid = request.args.get("tournament_id", type=int)
    if not tid:
        return error("tournament_id is required")
    with connect_db() as db:
        rows = db.execute("""
            SELECT match_number, match_date, map_name, start_time_trt, start_time_ist
            FROM scheduled_matches
            WHERE tournament_id=?
            ORDER BY match_number
        """, (tid,)).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/results/<int:result_id>", methods=["PATCH", "DELETE"])
@admin_required
def manage_result(result_id):
    if request.method == "DELETE":
        with connect_db() as db:
            cur = db.execute("DELETE FROM results WHERE id=?", (result_id,))
            if not cur.rowcount:
                return error("Result not found", 404)
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    allowed = {}
    try:
        for key in ("match_number", "placement", "kills", "placement_points"):
            if key in data:
                allowed[key] = int(data[key])
    except (TypeError, ValueError):
        return error("Score values must be valid numbers")
    if not allowed:
        return error("No score fields supplied")
    if (allowed.get("match_number", 1) < 1 or
        allowed.get("placement", 1) < 1 or
        allowed.get("kills", 0) < 0 or
        allowed.get("placement_points", 0) < 0):
        return error("Invalid score values")
    with connect_db() as db:
        cur = db.execute(
            "UPDATE results SET " + ", ".join(f"{k}=?" for k in allowed) + " WHERE id=?",
            (*allowed.values(), result_id)
        )
        if not cur.rowcount:
            return error("Result not found", 404)
    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
