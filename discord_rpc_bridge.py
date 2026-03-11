from flask import Flask, request
from pypresence import Presence
import time

CLIENT_ID = "1460710566250152017"

app = Flask(__name__)

rpc = None
connected = False
last_payload = None

# =========================
# CONNECT / DISCONNECT
# =========================
def connect_rpc():
    global rpc, connected
    try:
        rpc = Presence(CLIENT_ID)
        rpc.connect()
        connected = True
        print("Discord RPC connected")
    except Exception as e:
        connected = False
        print("RPC connect error:", e)

def disconnect_rpc():
    global rpc, connected
    try:
        if rpc:
            rpc.close()
    except:
        pass
    rpc = None
    connected = False

connect_rpc()

# =========================
# TIMESTAMP UTILITY
# =========================
def timestamp(duration, position):
    now = int(time.time())
    return now - position, now + (duration - position)

# =========================
# PAYLOAD SANITIZER
# =========================
def sanitize_buttons(data):
    buttons = data.get("buttons")
    if not buttons:
        data.pop("buttons", None)
    else:
        data["buttons"] = buttons[:2]
    return data

# =========================
# ROUTE /status
# =========================
@app.route("/status", methods=["POST"])
def status():
    global last_payload, connected

    data = request.json or {}
    data = sanitize_buttons(data)

    # Anti-spam
    if data == last_payload and not data.get("force"):
        return "SKIP"

    last_payload = data

    # Reconnect if needed
    if not connected:
        connect_rpc()
        if not connected:
            return "NO RPC"

    try:
        # -------- VIDEO --------
        if data.get("type") == "video":
            title = data.get("title", "Video")
            show = data.get("show")
            season = data.get("season")
            episode = data.get("episode")

            details = title
            if show and str(season) != "None" and str(episode) != "None":
                details = f"{show} S{season}E{episode}"

            if (
                not data.get("paused")
                and data.get("duration", 0) > 0
                and data.get("position", 0) >= 0
            ):
                start, end = timestamp(data["duration"], data["position"])
            else:
                start = end = None

            rpc.update(
                state="⏸ Paused" if data.get("paused") else "▶ Watching",
                details=details[:128], # Discord limit
                large_image=data.get("large_image", "kodi"),
                large_text=data.get("large_text", "Kodi Media Center")[:128],
                small_image=data.get("small_image"),
                start=start,
                end=end,
                buttons=data.get("buttons")
            )

        # -------- MUSIC --------
        elif data.get("type") == "music":
            artist = data.get("artist", "Unknown Artist")
            title = data.get("title", "Music")
            
            if (
                not data.get("paused")
                and data.get("duration", 0) > 0
                and data.get("position", 0) >= 0
            ):
                start, end = timestamp(data["duration"], data["position"])
            else:
                start = end = None

            rpc.update(
                state=f"by {artist}"[:128],
                details=title[:128],
                large_image=data.get("large_image", "music"),
                large_text=data.get("large_text", "Kodi Music")[:128],
                small_image=data.get("small_image"),
                start=start,
                end=end,
                buttons=data.get("buttons")
            )

        # -------- MENU --------
        else:
            menu_name = data.get("details", "Menu")
            rpc.update(
                state="In Kodi On Demand",
                details=f"Browsing the {menu_name} Menu"[:128],
                large_image=data.get("large_image", "kodi"),
                large_text=data.get("large_text", "Kodi")[:128],
                buttons=data.get("buttons")
            )

    except Exception as e:
        print("RPC error:", e)
        disconnect_rpc()

    return "OK"

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    print("Discord RPC Bridge running...")
    app.run(host="127.0.0.1", port=5678)