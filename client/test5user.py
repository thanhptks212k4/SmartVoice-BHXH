import requests
import websocket
import threading
import json
import speech_recognition as sr
import time
import pyaudio

# --- CẤU HÌNH ---
BASE_URL = "http://192.168.1.35:3000"
WS_URL = "ws://192.168.1.35:3000"

USERS = [
    {"username": "BHXH1", "password": "123456"},
    {"username": "BHXH2", "password": "123456"},
    {"username": "BHXH3", "password": "123456"},
    {"username": "BHXH4", "password": "123456"},
    {"username": "BHXH5", "password": "123456"},
]

# Câu hỏi test cho từng user
TEST_MESSAGES = [
    "bảo hiểm xã hội là gì",
    "mức đóng bảo hiểm xã hội là bao nhiêu",
    "điều kiện để hưởng lương hưu là gì",
    "bảo hiểm thất nghiệp được hưởng bao lâu",
    "cách tính tiền thai sản như thế nào",
]

CHANNELS = 1
RATE = 24000
p = pyaudio.PyAudio()

# Màu log
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def login(user):
    try:
        res = requests.post(f"{BASE_URL}/auth/login", json=user)
        if res.status_code == 200:
            token = res.json().get("token")
            print(f"{GREEN}[{user['username']}] Đăng nhập thành công!{RESET}")
            return token
        else:
            print(f"{YELLOW}[{user['username']}] Đăng nhập thất bại: {res.text}{RESET}")
            return None
    except Exception as e:
        print(f"{YELLOW}[{user['username']}] Lỗi: {e}{RESET}")
        return None


def play_audio_stream(url, username):
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=RATE,
            output=True
        )
        with requests.get(url, stream=True) as r:
            if r.status_code != 200:
                stream.close()
                return
            first_chunk = True
            for chunk in r.iter_content(chunk_size=4096):
                if not chunk:
                    continue
                if first_chunk:
                    chunk = chunk[44:]
                    first_chunk = False
                    if not chunk:
                        continue
                stream.write(chunk)
        stream.stop_stream()
        stream.close()
    except Exception as e:
        print(f"{YELLOW}[{username}] Lỗi phát audio: {e}{RESET}")


def run_user(username, password, message):
    token = login({"username": username, "password": password})
    if not token:
        return

    start_time = [0]
    done_event = threading.Event()

    def on_open(ws):
        print(f"{CYAN}[{username}] Kết nối WS, gửi: '{message}'{RESET}")
        start_time[0] = time.time()
        ws.send(json.dumps({"text": message, "language": "VI", "timestamp": ""}))

    def on_message(ws, msg):
        data = json.loads(msg)
        msg_type = data.get("type")

        if msg_type == "AI_VOICE_REPLY":
            latency = time.time() - start_time[0]
            text = data.get("text", "")
            audio_url = data.get("audioUrl", "")
            print(f"{GREEN}[{username}] ⏱ {latency:.2f}s | Reply: {text}{RESET}")
            if audio_url:
                play_audio_stream(audio_url, username)
            done_event.set()
            ws.close()

    def on_error(ws, err):
        print(f"{YELLOW}[{username}] Lỗi WS: {err}{RESET}")
        done_event.set()

    def on_close(ws, c, m):
        print(f"{YELLOW}[{username}] Đóng kết nối{RESET}")
        done_event.set()

    ws = websocket.WebSocketApp(
        f"{WS_URL}?token={token}",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()


if __name__ == "__main__":
    print(f"\n{CYAN}=== Test 5 user đồng thời ==={RESET}\n")

    threads = []
    for i, user in enumerate(USERS):
        t = threading.Thread(
            target=run_user,
            args=(user["username"], user["password"], TEST_MESSAGES[i])
        )
        threads.append(t)

    # Khởi động tất cả cùng lúc
    start_all = time.time()
    for t in threads:
        t.start()

    for t in threads:
        t.join()

    total = time.time() - start_all
    print(f"\n{GREEN}=== Tổng thời gian: {total:.2f}s ==={RESET}")
    print(f"{CYAN}Nếu song song: ~= thời gian của 1 user{RESET}")
    print(f"{CYAN}Nếu tuần tự:   ~= thời gian của 1 user x 5{RESET}")