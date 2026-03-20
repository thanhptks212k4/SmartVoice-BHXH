import requests
import websocket
import threading
import json

# --- CẤU HÌNH ---
BASE_URL = "http://localhost:3000"
WS_URL = "ws://localhost:3000"
USER_DATA = {
    "username": "bytehome2",
    "password": "123456" 
}

def login_and_get_token():
    try:
        print(f"🔑 Đang đăng nhập tài khoản: {USER_DATA['username']}...")
        # Gọi API Login (Thay đổi đường dẫn '/api/login' cho đúng với router của bạn)
        response = requests.post(f"{BASE_URL}/auth/login", json=USER_DATA)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('token')
            print("✅ Lấy Token thành công!")
            return token
        else:
            print(f"❌ Đăng nhập thất bại: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Lỗi kết nối API: {e}")
        return None

def on_message(ws, message):
    print(f"\n🤖 [Gemini]: {message}")
    print(">> Bạn: ", end="", flush=True)

def on_open(ws):
    print("🚀 WebSocket đã thông! Bạn có thể bắt đầu chat.")
    def send_loop():
        while True:
            msg = input(">> Bạn: ")
            if msg.lower() in ['exit', 'quit']:
                ws.close()
                break
            if msg.strip():
                ws.send(msg)
    threading.Thread(target=send_loop, daemon=True).start()

# --- LUỒNG CHÍNH ---
token = login_and_get_token()

if token:
    # Gắn token vào URL để kết nối WS
    full_ws_url = f"{WS_URL}?token={token}"
    
    ws = websocket.WebSocketApp(
        full_ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=lambda ws, err: print(f"\n❌ Lỗi WS: {err}"),
        on_close=lambda ws, c, m: print("\n🔌 Đã đóng kết nối.")
    )
    ws.run_forever()