from fastapi import FastAPI , HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
import json , os , struct  , time  , asyncio
import struct
import time
import asyncio
from redis_manager import redis_manager
from tts_service import generate_tts 
from config import settings

EXTERNAL_HOST = settings.EXTERNAL_HOST
EXTERNAL_PORT = settings.EXTERNAL_PORT
QUEUE_MAXSIZE = settings.QUEUE_MAXSIZE
STREAM_GET_TIMEOUT = settings.STREAM_GET_TIMEOUT


app = FastAPI()

audio_buffers = {}



def create_wav_header(sample_rate=24000, bits_per_sample=16, channels=1):
    o = bytes("RIFF", "ascii")
    o += struct.pack("<I", 0)  # Sửa từ 0xFFFFFFFF thành 0
    o += bytes("WAVE", "ascii")
    o += bytes("fmt ", "ascii")
    o += struct.pack("<I", 16)
    o += struct.pack("<H", 1)
    o += struct.pack("<H", channels)
    o += struct.pack("<I", sample_rate)
    o += struct.pack("<I", sample_rate * channels * bits_per_sample // 8)
    o += struct.pack("<H", channels * bits_per_sample // 8)
    o += struct.pack("<H", bits_per_sample)
    o += bytes("data", "ascii")
    o += struct.pack("<I", 0)  # Sửa từ 0xFFFFFFFF thành 0
    return o

@app.get("/stream-voice/{task_id}")
async def stream_voice(task_id: str):
    async def stream_generator():
        q = audio_buffers.get(task_id)
        if not q:
            raise HTTPException(status_code=404, detail="task not found")
        
        # --- BƯỚC QUAN TRỌNG: GOM DỮ LIỆU ĐẦU TIÊN ---
        # Đợi cho đến khi nhận được ít nhất 1 chunk dữ liệu thực sự
        # Việc này giúp khi Header gửi đi, trình phát có dữ liệu "lót" ngay lập tức
        first_chunk = None
        while first_chunk is None:
            try:
                # Lấy chunk đầu tiên
                chunk = await asyncio.wait_for(q.get(), timeout=STREAM_GET_TIMEOUT)
                if chunk == "DONE": return
                if isinstance(chunk, bytes):
                    first_chunk = chunk
            except:
                return # Timeout hoặc lỗi
        
        # Bây giờ mới bắt đầu gửi Header + Chunk đầu tiên
        yield create_wav_header()
        yield first_chunk
        
        # --- TIẾP TỤC STREAM NHƯ BÌNH THƯỜNG ---
        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=STREAM_GET_TIMEOUT)
                if chunk == "DONE": break
                if isinstance(chunk, bytes):
                    yield chunk
            except:
                break
        audio_buffers.pop(task_id, None)

    return StreamingResponse(stream_generator(), media_type="audio/wav")

async def process_tts_task(user_id, text, task_id, q: asyncio.Queue, voice):
    """Chạy generate_tts trong executor, đẩy chunk vào asyncio.Queue"""
    loop = asyncio.get_event_loop()
    start_time = time.time()
    print(f"[TTS] Bắt đầu task {task_id} cho user {user_id}")

    try:
        first_chunk = True
        # generate_tts là sync → chạy trong thread pool
        def run_tts():
            nonlocal first_chunk
            for chuck in generate_tts(text, voice):
                if first_chunk:
                    print(f" Task {task_id}: chunk đầu sau {time.time() - start_time:.2f}s")
                    first_chunk = False
                future = asyncio.run_coroutine_threadsafe(q.put(chuck), loop)
                future.result(timeout=30)

        await loop.run_in_executor(None, run_tts)
        await q.put("DONE")
        redis_manager.publish(
            f"voice_ready:{user_id}",
            json.dumps({"type": "AI_VOICE_DONE", "taskId": task_id}),
        )

    except Exception as e:
        print(f"[ERR] Task {task_id}: {e}")
        await q.put("DONE")


async def redis_listener():
    print(" Worker đang lắng nghe kênh tts_tasks...")
    loop = asyncio.get_event_loop()

    while True:
        try:
            task_data = await loop.run_in_executor(
                None, lambda: redis_manager.listen_tasks("tts_tasks")
            )
            if not task_data:
                continue

            data = json.loads(task_data[1])
            user_id = data.get("userId")
            text = data.get("reply", "")
            voice = data.get("voice")
            task_id = f"task_{int(time.time() * 1000)}"

            # Tạo queue cho task và lưu vào audio_buffers trước khi publish URL
            q = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
            audio_buffers[task_id] = q

            voice_url = f"http://{EXTERNAL_HOST}:{EXTERNAL_PORT}/stream-voice/{task_id}"
            print(voice_url)
            # Gửi thông báo cho client
            redis_manager.publish(f"voice_ready:{user_id}", {
                "type": "AI_VOICE_REPLY",
                "text": text,
                "audioUrl": voice_url
            })

            # Submit task cho thread pool
            await process_tts_task(user_id, text, task_id, q,voice)

        except Exception as e:
            print(f"[ERR] Redis listener: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8123)