
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")

# Tournament records can be updated here until a verified
# live-score provider is connected.
TOURNAMENTS = [
    {
        "name": "BGIS",
        "status": "Upcoming",
        "game": "BGMI"
    },
    {
        "name": "BMPS",
        "status": "Upcoming",
        "game": "BGMI"
    },
    {
        "name": "BMSD",
        "status": "Upcoming",
        "game": "BGMI"
    }
]

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/api/tournaments")
def tournaments():
    return jsonify({
        "source": "Initial tracker data",
        "live_connected": False,
        "tournaments": TOURNAMENTS
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
