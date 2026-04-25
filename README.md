# SmartVoice BHXH

Chatbot giọng nói hỗ trợ nghiệp vụ **Bảo hiểm Xã hội** theo kiến trúc microservice. Người dùng nói — hệ thống nhận dạng giọng nói, truy vấn tài liệu pháp lý (RAG), sinh câu trả lời bằng AI và đọc lại bằng giọng tổng hợp tiếng Việt, toàn bộ real-time.

**Tác giả:** Phạm Tiến Thành  
**Email:** phamtienthanh21022004@gmail.com

---

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | Node.js / Express / WebSocket |
| AI Chat | Gemini API + Qdrant RAG |
| Text-to-Speech | XTTS v2 (fine-tuned tiếng Việt) |
| Speech-to-Text | Silero VAD + Whisper / Google STT |
| Embedding | SentenceTransformer + Qdrant |
| Hạ tầng | Docker, PostgreSQL, Redis |

---

## Luồng hoạt động

```
Mic → STT → Backend → AI Worker (Gemini + RAG) → TTS → Audio phát lại
```

1. Người dùng nói vào mic, browser stream PCM đến STT server
2. STT nhận dạng, gửi text về backend qua WebSocket
3. Backend đẩy task vào Redis queue
4. AI Worker truy vấn Qdrant (RAG) + gọi Gemini sinh câu trả lời
5. TTS Worker tổng hợp giọng nói, stream audio về browser
