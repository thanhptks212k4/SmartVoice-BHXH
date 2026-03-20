import json
import requests
import numpy as np
import sounddevice as sd
import time

# Cấu hình âm thanh
SAMPLE_RATE = 24000
CHANNELS = 1

def start_client():
    url = "http://localhost:8000"
    stream = sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16')
    stream.start()

    try:
        while True:
            text = input("\n✍️ Nhập văn bản: ").strip()
            if not text:
                continue
            if text.lower() == 'exit':
                break

            print("⏳ Gửi yêu cầu và chờ nhận âm thanh đầu tiên...")

            start_total = time.time()
            first_chunk_time = None

            with requests.post(url, json={"text": text}, stream=True) as r:
                for chunk in r.iter_content(chunk_size=4096):
                    if chunk:
                        # Ghi nhận thời điểm nhận được chunk đầu tiên
                        if first_chunk_time is None:
                            first_chunk_time = time.time()
                            print(f"🎧 Nhận âm thanh đầu tiên sau {first_chunk_time - start_total:.2f} giây")

                        # Ghi âm thanh ra loa
                        audio_array = np.frombuffer(chunk, dtype='int16')
                        stream.write(audio_array)

            end_total = time.time()
            print(f"✅ Đã phát xong (tổng {end_total - start_total:.2f} giây)\n")

    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        stream.stop()
        stream.close()

if __name__ == "__main__":
    start_client()