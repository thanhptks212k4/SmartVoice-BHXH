"""
Flask-SocketIO server — cầu nối giữa client.py (Python) và React UI (browser).

Chạy:  python server.py
Port:  5500

Flow:
  client.py  →  emit("set_state", {s: "listening"})  →  server.py
  server.py  →  emit("state",     {s: "listening"})  →  React UI (browser)
"""

from flask import Flask
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = "bhxh-voice-2024"

socketio = SocketIO(app, cors_allowed_origins="*")


@socketio.on("connect")
def handle_connect():
    print("[SocketIO] Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    print("[SocketIO] Client disconnected")


@socketio.on("set_state")
def handle_set_state(data):
    """Nhận state từ client.py, broadcast tới tất cả browser."""
    state = data.get("s", "idle")
    print(f"[SocketIO] State → {state}")
    # Broadcast tới TẤT CẢ client (bao gồm React UI)
    emit("state", {"s": state}, broadcast=True)


if __name__ == "__main__":
    print("=" * 40)
    print("  SocketIO Bridge Server")
    print("  http://localhost:5500")
    print("=" * 40)
    socketio.run(app, host="0.0.0.0", port=5500, debug=False, allow_unsafe_werkzeug=True)
