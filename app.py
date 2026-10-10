
import os
import sqlite3
from functools import wraps
from flask import (
    Flask, request, jsonify, session,
    redirect, send_from_directory
)
from werkzeug.security import check_password_hash

app = Flask(__name__, static_folder=".")
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deploy")
DB_PATH = os.environ.get("DB_PATH", "tournaments.db")


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                game TEXT NOT NULL DEFAULT 'BGMI',
                status TEXT NOT NULL DEFAULT 'Upcoming'
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
                FOREIGN KEY (tournament_id)
                    REFERENCES tournaments(id)
            );
        """)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error": "Admin login required"}), 401
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/admin")
def admin_page():
    return send_from_directory(".", "admin.html")


@app.route("/api/tournaments")
def get_tournaments():
    with connect_db() as db:
        rows = db.execute(
            "SELECT * FROM tournaments ORDER BY id DESC"
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/tournaments", methods=["POST"])
@admin_required
def add_tournament():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    game = str(data.get("game", "BGMI")).strip()

    if not name:
        return jsonify({"error": "Tournament name is required"}), 400

    with connect_db() as db:
        cur = db.execute(
            "INSERT INTO tournaments (name, game) VALUES (?, ?)",
            (name, game or "BGMI")
        )
        tournament_id = cur.lastrowid

    return jsonify({"id": tournament_id, "name": name}), 201


@app.route("/api/results", methods=["GET"])
def get_results():
    tournament_id = request.args.get("tournament_id", type=int)

    query = """
        SELECT r.*, t.name AS tournament_name
        FROM results r
        JOIN tournaments t ON t.id = r.tournament_id
    """
    params = []

    if tournament_id:
        query += " WHERE r.tournament_id = ?"
        params.append(tournament_id)

    query += " ORDER BY r.match_number, r.placement"

    with connect_db() as db:
        rows = db.execute(query, params).fetchall()

    return jsonify([dict(row) for row in rows])


@app.route("/api/results", methods=["POST"])
@admin_required
def add_result():
    data = request.get_json(silent=True) or {}

    try:
        tournament_id = int(data["tournament_id"])
        match_number = int(data["match_number"])
        placement = int(data["placement"])
        kills = int(data["kills"])
        map_name = str(data["map_name"]).strip()
        team_name = str(data["team_name"]).strip()
        placement_points = int(data.get("placement_points", 0))
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Check all score fields"}), 400

    if (
        match_number < 1 or placement < 1 or kills < 0
        or placement_points < 0
        or not map_name or not team_name
    ):
        return jsonify({"error": "Invalid score values"}), 400

    with connect_db() as db:
        exists = db.execute(
            "SELECT id FROM tournaments WHERE id = ?",
            (tournament_id,)
        ).fetchone()

        if not exists:
            return jsonify({"error": "Tournament not found"}), 404

        cur = db.execute("""
            INSERT INTO results
            (tournament_id, match_number, map_name, team_name,
             placement, kills, placement_points)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            tournament_id, match_number, map_name, team_name,
            placement, kills, placement_points
        ))

    return jsonify({
        "id": cur.lastrowid,
        "total_points": kills + placement_points
    }), 201


@app.route("/api/standings")
def standings():
    tournament_id = request.args.get("tournament_id", type=int)

    query = """
        SELECT team_name,
               SUM(kills) AS total_kills,
               SUM(placement_points) AS placement_points,
               SUM(kills + placement_points) AS total_points,
               COUNT(DISTINCT match_number) AS matches_played
        FROM results
    """
    params = []

    if tournament_id:
        query += " WHERE tournament_id = ?"
        params.append(tournament_id)

    query += """
        GROUP BY team_name
        ORDER BY total_points DESC, total_kills DESC
    """

    with connect_db() as db:
        rows = db.execute(query, params).fetchall()

    return jsonify([dict(row) for row in rows])


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    password = os.environ.get("ADMIN_PASSWORD")
    password_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    supplied = str(data.get("password", ""))

    valid = (
        password is not None and supplied == password
    ) or (
        password_hash is not None
        and check_password_hash(password_hash, supplied)
    )

    if not valid:
        return jsonify({
            "error": "Invalid password or admin password not configured"
        }), 401

    session["admin"] = True
    return jsonify({"ok": True})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
