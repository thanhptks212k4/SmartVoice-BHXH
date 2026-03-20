import requests
import websocket
import threading
import json
import pyaudio
import speech_recognition as sr
import time
from pydub import AudioSegment
import io
import sys

# --- CẤU HÌNH ---
BASE_URL = "http://localhost:3000"
WS_URL = "ws://localhost:3000"
USER_DATA = {
    "username": "duy1",
    "password": "123456"
}

CHANNELS = 1
RATE = 24000
CHUNK = 1024

p = pyaudio.PyAudio()
recognizer = sr.Recognizer()
mic = sr.Microphone()

# Biến trạng thái (tránh global)
STATE = {
    "start_request_time": 0
}

# Màu log
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def play_audio_stream(url: str, ws):
    """
    Phát audio theo luồng streaming — reset chuẩn mỗi lần phát.
    """
    try:
        print(f"{CYAN}{url}{RESET}")

        # Reset mốc đo cho mỗi lượt mới
        start_time = None
        first_chunk_time = None

        with requests.get(url, stream=True) as r:
            if r.status_code != 200:
                print(f"{YELLOW}⚠️  Không thể lấy audio từ {url}{RESET}")
                return

            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True
            )

            print(f"{GREEN}▶  Đang phát phản hồi (streaming)...{RESET}")

            buffer = b""
            chunk_count = 0

            # 🟢 Bắt đầu đo khi thực sự bắt đầu đọc stream
            start_time = time.time()

            for chunk in r.iter_content(chunk_size=4096):
                if not chunk:
                    continue

                # Ghi nhận thời điểm nhận chunk đầu tiên
                if chunk_count == 0:
                    first_chunk_time = time.time()
                    latency = first_chunk_time - start_time
                    print(f"{YELLOW}⏱ Chunk đầu sau: {latency:.2f}s{RESET}")

                buffer += chunk
                chunk_count += 1

                if len(buffer) >= 8192:
                    stream.write(buffer)
                    buffer = b""

            if buffer:
                stream.write(buffer)

            stream.stop_stream()
            stream.close()

        print(f"{GREEN}✅ Phát xong, quay lại lắng nghe bạn...{RESET}")
        loop_speech_to_server(ws)

    except Exception as e:
        print(f"{YELLOW}⚠️  Lỗi phát âm thanh streaming: {e}{RESET}")

def login_and_get_token():
    """
    Đăng nhập để lấy token từ API backend.
    """
    try:
        print(f"🔐 Đăng nhập tài khoản: {USER_DATA['username']}...")
        res = requests.post(f"{BASE_URL}/auth/login", json=USER_DATA)
        if res.status_code == 200:
            token = res.json().get("token")
            print(f"{GREEN}✅ Lấy Token thành công!{RESET}\n")
            return token
        else:
            print(f"{YELLOW}❌ Đăng nhập thất bại: {res.text}{RESET}")
            return None
    except Exception as e:
        print(f"{YELLOW}⚠️  Lỗi kết nối API: {e}{RESET}")
        return None


def recognize_once():
    """
    Ghi âm và nhận diện giọng nói 1 lần.
    """
    with mic as source:
        print("🎤 Chuẩn bị ghi âm...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print("🎧 Đang lắng nghe bạn nói...")
        audio = recognizer.listen(source, phrase_time_limit=15)
        print("🧠 Đang xử lý giọng nói...")

    try:
        text = recognizer.recognize_google(audio, language="vi-VN").strip()
        if text:
            print(f"{CYAN}💬 Bạn nói: {text}{RESET}")
        return text
    except sr.UnknownValueError:
        print(f"{YELLOW}⚠️  Không nghe rõ, bỏ qua.{RESET}")
        return ""
    except sr.RequestError as e:
        print(f"{YELLOW}⚠️  Lỗi STT: {e}{RESET}")
        return ""


def loop_speech_to_server(ws):
    """
    Gửi text (STT) từ mic lên server qua WebSocket.
    """
    text = recognize_once()
    if text:
        # ⏱ Bắt đầu đo từ lúc gửi text đi
        STATE["start_request_time"] = time.time()
        data = {"text": text, "language": "VI", "timestamp": ""}
        ws.send(json.dumps(data))
    else:
        loop_speech_to_server(ws)


def on_message(ws, message):
    """
    Xử lý tin nhắn WebSocket nhận được từ server.
    """
    data = json.loads(message)
    msg_type = data.get("type")

    if msg_type == "AI_VOICE_REPLY":
        bot_text = data.get("text")
        audio_url = data.get("audioUrl")
        print(bot_text)
        print(audio_url)

        # ⏱ Tính thời gian từ lúc gửi text đến khi có audioUrl
        if STATE["start_request_time"] > 0:
            latency = time.time() - STATE["start_request_time"]
            print(f"{YELLOW}⏱ Latency (Text -> audioUrl): {latency:.2f} giây{RESET}")
            STATE["start_request_time"] = 0

        if bot_text:
            print(f"\n{GREEN}[BYTEHOME]: {bot_text}{RESET}")

        if audio_url:
            play_audio_stream(audio_url, ws)

    elif msg_type == "AI_VOICE_DONE":
        print(f"{CYAN}🤖 Bot nói xong, quay lại lắng nghe bạn...{RESET}")
        loop_speech_to_server(ws)

    else:
        # Bỏ qua STATUS event (không đo latency)
        if msg_type != "STATUS":
            print(f"{YELLOW}⚠️  Event không xác định: {data}{RESET}")


def on_open(ws):
    
    print(f"{GREEN}✅ WebSocket đã kết nối! Bắt đầu hội thoại bằng giọng nói...{RESET}\n")
    loop_speech_to_server(ws)


if __name__ == "__main__":
    token = login_and_get_token()
    if token:
        ws_url = f"{WS_URL}?token={token}"
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=lambda ws, err: print(f"{YELLOW}⚠️  Lỗi WS: {err}{RESET}"),
            on_close=lambda ws, c, m: print(f"{YELLOW}🔌 Kết nối WebSocket đã đóng.{RESET}")
        )
        ws.run_forever()