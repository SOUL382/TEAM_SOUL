# Team SouL BGMI Tournament Tracker

A fan-made BGMI tournament scoreboard with a public leaderboard and password-protected admin workspace.

## Features
- Multiple tournaments
- Team registration and optional four-player roster text
- Match result entry with editable placement points and kill points
- BGMI placement-point defaults (1st 10, 2nd 6, 3rd 5, 4th 4, 5th 3, 6th 2, 7th–8th 1)
- Public standings and match history
- Admin edit/delete for recorded scores and team highlights

## Run locally

```bash
pip install -r requirements.txt
ADMIN_PASSWORD='choose-a-password' SECRET_KEY='use-a-long-random-secret' python app.py
```

Open `http://127.0.0.1:10000` for the public site and `/admin` for the admin workspace.

## Deploy the development branch on Render

Use branch `pmgc-scoreboard-v1`, build command `pip install -r requirements.txt`, and start command `gunicorn app:app`.

Set these environment variables in the Render service:
- `ADMIN_PASSWORD`: choose a strong, unique admin password. Do not share it in chat or commit it to GitHub.
- `SECRET_KEY`: a long random secret value.
- `DB_PATH`: `/var/data/tournaments.db` when using the persistent disk below.

Attach a Render persistent disk mounted at `/var/data` so tournament data survives redeploys. Without a persistent disk, the SQLite database may be lost when the service is recreated or redeployed.

This project does not currently fetch official live scores automatically. Admins enter verified match results manually.

## Important

This is an independent fan project and is not affiliated with Team SouL, KRAFTON, or the Battlegrounds Mobile India organizers.
