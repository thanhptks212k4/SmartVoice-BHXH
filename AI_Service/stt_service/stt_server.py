"""
STT Service — Whisper
POST /stt  multipart/form-data  field: audio (wav file)
Returns: {"text": "..."}
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import whisper, tempfile, os, uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
print(f"Loading Whisper [{MODEL_NAME}]...")
model = whisper.load_model(MODEL_NAME)
print("Whisper ready!")

@app.post("/stt")
async def stt(audio: UploadFile = File(...)):
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(400, "File phải là audio")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        result = model.transcribe(tmp_path, language="vi", fp16=False)
        return {"text": result["text"].strip()}
    finally:
        os.unlink(tmp_path)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("STT_PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)
