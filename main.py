import xbmc
import xbmcgui
import xbmcaddon
import json
import urllib.request
import time
import threading
import os

addon = xbmcaddon.Addon()
monitor = xbmc.Monitor()

# =========================
# CONFIG
# =========================
SERVER_URL = "http://127.0.0.1:5678/status"
POLL_INTERVAL = 2
WATCHDOG_INTERVAL = 15

# =========================
# STATE
# =========================
rpc_running = False
rpc_thread = None
send_lock = threading.Lock()
last_send_time = 0
last_window_id = None
player_events = None

# =========================
# PLAYER EVENTS
# =========================
class PlayerEvents(xbmc.Player):
    def onAVStarted(self):
        send(get_activity(force=True))

    def onPlayBackPaused(self):
        send(get_activity(force=True))

    def onPlayBackResumed(self):
        send(get_activity(force=True))

    def onPlayBackStopped(self):
        send(get_activity(force=True))

    def onPlayBackEnded(self):
        send(get_activity(force=True))

# =========================
# PLAYBACK INFO
# =========================
def get_playback():
    player = xbmc.Player()

    if not player.isPlaying():
        return None

    filename = os.path.basename(player.getPlayingFile() or "")

    if player.isPlayingVideo():
        info = player.getVideoInfoTag()
        title = info.getTitle()
        if not title or title == "":
            title = filename if filename else "Unknown video"
            
        return {
            "type": "video",
            "title": title,
            "show": info.getTVShowTitle(),
            "season": info.getSeason(),
            "episode": info.getEpisode(),
            "duration": int(player.getTotalTime()),
            "position": int(player.getTime()),
            "paused": player.isPaused(),
            "large_image": "kodi_video",
            "large_text": title,
            "small_image": "pause" if player.isPaused() else "play",
            "details": title,
        }

    if player.isPlayingAudio():
        info = player.getMusicInfoTag()
        # Fix per lista artisti
        artists = info.getArtist()
        artist_name = " - ".join(artists) if isinstance(artists, list) and artists else str(artists)
        if not artist_name or artist_name == "":
            artist_name = "Unknown Artist"
            
        title = info.getTitle()
        if not title or title == "":
            title = filename if filename else "Unknown Track"

        return {
            "type": "music",
            "title": title,
            "artist": artist_name,
            "album": info.getAlbum() or "",
            "duration": int(player.getTotalTime()),
            "position": int(player.getTime()),
            "paused": player.isPaused(),
            "large_image": "music",
            "large_text": title,
            "small_image": "pause" if player.isPaused() else "play",
            "details": title,
        }

    return None

# =========================
# MENU INFO
# =========================
def get_menu():
    global last_window_id

    label = xbmc.getInfoLabel("System.CurrentWindow") or "Kodi menu"
    window_id = xbmc.getInfoLabel("System.CurrentWindowId") or "0"

    changed = window_id != last_window_id
    last_window_id = window_id

    return {
        "type": "menu",
        "details": label,
        "large_image": "kodi_menu",
        "large_text": label,
        "force": changed
    }

# =========================
# ACTIVITY
# =========================
def get_activity(force=False):
    data = get_playback() or get_menu()
    if not data:
        return None
    if force:
        data["force"] = True
    return data

# =========================
# HTTP SEND
# =========================
def send(data):
    global last_send_time

    if not data or not rpc_running:
        return

    with send_lock:
        now = time.time()
        if not data.get("force", False) and now - last_send_time < POLL_INTERVAL:
            return

        try:
            clean_data = {k: v for k, v in data.items() if v is not None}

            req = urllib.request.Request(
                SERVER_URL,
                data=json.dumps(clean_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            urllib.request.urlopen(req, timeout=2).close()
            last_send_time = now

        except Exception as e:
            xbmc.log(f"[RPC SEND ERROR] {e}", xbmc.LOGERROR)

# =========================
# THREAD LOOP
# =========================
def activity_loop():
    while rpc_running and not monitor.abortRequested():
        try:
            activity = get_activity()
            if activity:
                if time.time() - last_send_time > WATCHDOG_INTERVAL:
                    activity["force"] = True
                send(activity)
        except Exception as e:
            xbmc.log(f"[RPC LOOP ERROR] {e}", xbmc.LOGERROR)
        time.sleep(POLL_INTERVAL)

# =========================
# PUBLIC CONTROL
# =========================
def start_rpc():
    global rpc_running, rpc_thread, player_events

    if rpc_running:
        return

    rpc_running = True
    player_events = PlayerEvents()

    rpc_thread = threading.Thread(
        target=activity_loop,
        daemon=True
    )
    rpc_thread.start()
    
    # =========================
    # NOTIFICA INIZIALE
    # =========================
    xbmcgui.Dialog().notification(
        "Clover RPC",
        "Connected Via Proxy",
        xbmcgui.NOTIFICATION_INFO,
        3000
    )

def stop_rpc():
    global rpc_running

    if not rpc_running:
        return

    rpc_running = False
    monitor.waitForAbort(1)

# =========================
# EXECUTION ENTRY POINT
# =========================
if __name__ == '__main__':
    start_rpc()
    
    # Mantiene il servizio in esecuzione finché Kodi è attivo
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
            
    stop_rpc()