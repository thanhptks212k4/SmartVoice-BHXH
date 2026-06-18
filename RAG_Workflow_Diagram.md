# 🔄 RAG WORKFLOW DIAGRAM - SmartVoice BHXH

## 📊 Sơ đồ Tổng Quan

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          RAG WORKFLOW - BHXH SYSTEM                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   CLIENT     │         │   BACKEND    │         │    REDIS     │
│  (Python)    │         │   (Node.js)  │         │    Queue     │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │ 1. Upload Files        │                        │
       │   POST /api/admin/     │                        │
       │   rag/uploadfile       │                        │
       ├───────────────────────>│                        │
       │                        │                        │
       │                        │ 2. Lưu files vào       │
       │                        │    uploads/{userId}/   │
       │                        │                        │
       │                        │ 3. Push Task           │
       │                        │    {userId, groupId,   │
       │                        │     base}              │
       │                        ├───────────────────────>│
       │                        │   embedding_tasks      │
       │                        │      (LPUSH)           │
       │                        │                        │
       │                        │<───200 OK──────────────│
       │<───────────────────────┤                        │
       │    Response            │                        │
       │                        │                        │
       │                        │                        │
┌──────▼───────┐         ┌──────▼───────┐         ┌──────▼───────┐
│ EMBEDDING    │         │   QDRANT     │         │ SENTENCE     │
│  WORKER      │         │  (Vector DB) │         │ TRANSFORMER  │
│  (Python)    │         │              │         │   (Model)    │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │ 4. Listen Queue        │                        │
       │    BRPOP               │                        │
       │    embedding_tasks     │                        │
       │<───────────────────────┤                        │
       │                        │                        │
       │ 5. Đọc files từ        │                        │
       │    uploads/{userId}/   │                        │
       │                        │                        │
       │ 6. Extract Text        │                        │
       │    (.txt, .docx, .doc) │                        │
       │                        │                        │
       │ 7. Legal-Aware         │                        │
       │    Chunking            │                        │
       │    - Nhận diện Chương  │                        │
       │    - Nhận diện Điều    │                        │
       │    - Nhận diện Khoản   │                        │
       │    - Nhận diện Điểm    │                        │
       │    - Max 512 chars     │                        │
       │    - Overlap 100 chars │                        │
       │                        │                        │
       │ 8. Encode Vectors      │                        │
       │    SentenceTransformer │                        │
       │    (384 dimensions)    │                        │
       │────────────────────────┼───────────────────────>│
       │                        │                        │
       │<───────────────────────┼────────────────────────│
       │    Vectors (384D)      │                        │
       │                        │                        │
       │ 9. Upsert to Qdrant    │                        │
       │    collection: thanhpt │                        │
       │    - userId            │                        │
       │    - groupId           │                        │
       │    - fileName          │                        │
       │    - so_hieu           │                        │
       │    - loai_vb           │                        │
       │    - text              │                        │
       │    - chuong, dieu,     │                        │
       │      khoan, diem       │                        │
       ├───────────────────────>│                        │
       │                        │                        │
       │                        │<───ACK──────────────   │
       │                        │                        │
       │ 10. Đổi tên file       │                        │
       │     → .completed       │                        │
       │                        │                        │
       └────────────────────────┴────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   USER       │         │   BACKEND    │         │    REDIS     │
│  (WebSocket) │         │   (Node.js)  │         │    Queue     │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │ 1. Gửi câu hỏi (STT)  │                        │
       │    WebSocket           │                        │
       ├───────────────────────>│                        │
       │                        │                        │
       │                        │ 2. Push AI Task        │
       │                        │    {userId, text,      │
       │                        │     groupId, voice}    │
       │                        ├───────────────────────>│
       │                        │    ai_tasks (LPUSH)    │
       │                        │                        │
       │                        │                        │
┌──────▼───────┐         ┌──────▼───────┐         ┌──────▼───────┐
│  AI ENGINE   │         │   QDRANT     │         │   GEMINI     │
│  WORKER      │         │  (Vector DB) │         │     API      │
│  (Python)    │         │              │         │              │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │ 3. Listen Queue        │                        │
       │    BRPOP ai_tasks      │                        │
       │<───────────────────────┤                        │
       │                        │                        │
       │ 4. Encode Query        │                        │
       │    SentenceTransformer │                        │
       │                        │                        │
       │ 5. Query Qdrant        │                        │
       │    - Vector similarity │                        │
       │    - Filter: groupId   │                        │
       │    - Filter: userId    │                        │
       │      (base | userId)   │                        │
       │    - Limit: 5 results  │                        │
       ├───────────────────────>│                        │
       │                        │                        │
       │<───────────────────────┤                        │
       │  Top 5 Context Chunks  │                        │
       │                        │                        │
       │ 6. Build Prompt        │                        │
       │    THÔNG TIN HỖ TRỢ:   │                        │
       │    {context}           │                        │
       │    CÂU HỎI: {query}    │                        │
       │                        │                        │
       │ 7. Call Gemini API     │                        │
       │    + System Instruction│                        │
       │    + Context + Query   │                        │
       ├────────────────────────┼───────────────────────>│
       │                        │                        │
       │<───────────────────────┼────────────────────────│
       │    AI Response         │                        │
       │                        │                        │
       │ 8. Normalize Text      │                        │
       │    (chuẩn hóa cho TTS) │                        │
       │                        │                        │
       │ 9. Publish TTS Task    │                        │
       │    {userId, reply,     │                        │
       │     voice, status}     │                        │
       ├───────────────────────>│                        │
       │    tts_tasks (PUBLISH) │                        │
       │                        │                        │
       │                        │                        │
┌──────▼───────┐         ┌──────▼───────┐         ┌──────▼───────┐
│  TTS ENGINE  │         │   BACKEND    │         │     USER     │
│  (Python)    │         │   (Node.js)  │         │  (WebSocket) │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │ 10. Listen TTS Task    │                        │
       │     Subscribe          │                        │
       │<───────────────────────┤                        │
       │                        │                        │
       │ 11. Generate Audio     │                        │
       │     (TTS Model)        │                        │
       │                        │                        │
       │ 12. Publish Audio      │                        │
       │     voice_ready:{id}   │                        │
       ├───────────────────────>│                        │
       │                        │                        │
       │                        │ 13. Forward to Client  │
       │                        │     WebSocket          │
       │                        ├───────────────────────>│
       │                        │   {type, text, audio}  │
       │                        │                        │
       │                        │                        │
       └────────────────────────┴────────────────────────┘
```

---

## 📋 Chi Tiết Các Bước

### 🔵 PHASE 1: DOCUMENT INDEXING (Embedding)

#### **Bước 1-3: Upload & Queue**
- **Client** (`uploadFile.py`): Gửi batch files (max 20 files/lần) đến API
- **Backend** (`rag.controller.js`): 
  - Nhận files qua Multer
  - Lưu vào `uploads/{userId}/`
  - Push task `{userId, groupId, base}` vào Redis queue `embedding_tasks`
  - Response 200 OK

#### **Bước 4-7: Document Processing**
- **Embedding Worker** (`worker_embetdding.py`):
  - Listen queue `embedding_tasks` (BRPOP - blocking pop)
  - Scan thư mục `uploads/{userId}/`
  - Extract text từ `.txt`, `.docx`, `.doc` (sử dụng `docx`, `antiword`)
  - **Legal-Aware Chunking** (`embetding_engine.py`):
    - Phân tích cấu trúc văn bản pháp luật
    - Nhận diện: **Chương** → **Điều** → **Khoản** → **Điểm**
    - Chunking thông minh:
      - Max: 512 chars
      - Overlap: 100 chars
      - Giữ nguyên metadata pháp lý cho mỗi chunk

#### **Bước 8-10: Vector Storage**
- **Encode**: Sử dụng `SentenceTransformer` (384 dimensions)
- **Qdrant Upsert**:
  ```python
  Collection: "thanhpt"
  Distance: COSINE
  Payload: {
    userId: "xxx" | "base",
    groupId: "xxx",
    fileName: "115_2015_ND-CP.txt",
    so_hieu: "115/2015/ND-CP",
    loai_vb: "Nghị định",
    text: "chunk content...",
    chuong: "Chương I",
    dieu: "Điều 5",
    khoan: "1.",
    diem: "a)"
  }
  ```
- Đổi tên file → `.completed` để tránh xử lý lại

---

### 🟢 PHASE 2: QUERY & RETRIEVAL (RAG Pipeline)

#### **Bước 1-3: User Query**
- **User**: Gửi câu hỏi qua WebSocket (từ STT)
- **Backend**: Push task `{userId, text, groupId, voice}` vào `ai_tasks`

#### **Bước 4-6: Semantic Search**
- **AI Worker** (`worker.py`):
  - Listen queue `ai_tasks`
  - **Encode query** thành vector (384D)
  - **Query Qdrant**:
    ```python
    query_vector = encode(query_text)
    filter = {
      groupId: "xxx",
      userId: ["base", user_id]  # Search cả base + user data
    }
    limit = 5
    ```
  - Nhận top 5 chunks có similarity cao nhất

#### **Bước 7-8: AI Generation**
- **Gemini API** (`ai_engine.py`):
  - Build prompt:
    ```
    THÔNG TIN HỖ TRỢ:
    {context từ 5 chunks}
    
    CÂU HỎI: {user query}
    ```
  - System Instruction:
    - Vai trò: Chuyên gia BHXH
    - Quy tắc: Ngắn gọn, 3-7 câu, có số liệu cụ thể
    - Phạm vi: Chỉ tư vấn BHXH
  - **Normalize text** (`normalize_text.py`): Chuẩn hóa cho TTS

#### **Bước 9-13: Voice Response**
- Publish task `{userId, reply, voice}` vào `tts_tasks`
- **TTS Worker** xử lý và generate audio
- Publish audio ready → `voice_ready:{userId}`
- **Backend** forward audio về client qua WebSocket

---

## 🏗️ Kiến Trúc Hệ Thống

```
┌─────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE LAYERS                       │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                          │
│  • Client Upload Script (Python)                            │
│  • WebSocket Client (Voice Chat)                            │
└─────────────────────┬────────────────────────────────────────┘
                      │
                      │ HTTP / WebSocket
                      │
┌─────────────────────▼────────────────────────────────────────┐
│  APPLICATION LAYER                                           │
│  • Express.js Backend                                        │
│  • Multer (File Upload)                                      │
│  • JWT Authentication                                        │
│  • WebSocket Server                                          │
└─────────────────────┬────────────────────────────────────────┘
                      │
                      │ Redis Queue
                      │
┌─────────────────────▼────────────────────────────────────────┐
│  PROCESSING LAYER                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Embedding   │  │  AI Engine   │  │  TTS Engine  │       │
│  │  Worker      │  │  Worker      │  │  Worker      │       │
│  │  (Python)    │  │  (Python)    │  │  (Python)    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────┬────────────────────────────────────────┘
                      │
                      │ Vector/Audio Processing
                      │
┌─────────────────────▼────────────────────────────────────────┐
│  DATA LAYER                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Qdrant     │  │    Redis     │  │  File Store  │       │
│  │  Vector DB   │  │  Queue/Cache │  │  uploads/    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  EXTERNAL SERVICES                                           │
│  • Gemini API (Google AI)                                    │
│  • SentenceTransformer Model                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔑 Các Thành Phần Chính

### **1. Document Processing Pipeline**
- **Input**: .txt, .docx, .doc files
- **Chunking Strategy**: Legal-aware (Chương → Điều → Khoản → Điểm)
- **Embedding Model**: SentenceTransformer (384D)
- **Storage**: Qdrant Vector DB (COSINE distance)

### **2. RAG Query Pipeline**
- **Retrieval**: Top-K similarity search (K=5)
- **Filter**: groupId + (base OR userId)
- **Generation**: Gemini AI với context augmentation
- **Output**: Normalized text cho TTS

### **3. Redis Queue Architecture**
- **embedding_tasks**: Hàng đợi xử lý embedding
- **ai_tasks**: Hàng đợi xử lý chat
- **tts_tasks**: Hàng đợi xử lý TTS
- **voice_ready:{userId}**: Pattern cho audio response

### **4. Metadata Structure**
```python
{
  "userId": "xxx" | "base",        # base = văn bản chung
  "groupId": "xxx",                # Nhóm người dùng
  "fileName": "115_2015_ND-CP.txt",
  "so_hieu": "115/2015/ND-CP",     # Số hiệu văn bản
  "loai_vb": "Nghị định",          # Loại văn bản
  "text": "...",                   # Nội dung chunk
  "chuong": "Chương I",            # Metadata pháp lý
  "dieu": "Điều 5",
  "khoan": "1.",
  "diem": "a)"
}
```

---

## 🔧 Công Nghệ Sử Dụng

| Component | Technology |
|-----------|-----------|
| **Backend API** | Node.js + Express.js |
| **Vector Database** | Qdrant |
| **Message Queue** | Redis (LPUSH/BRPOP/PubSub) |
| **Embedding Model** | SentenceTransformer |
| **LLM** | Google Gemini AI |
| **File Upload** | Multer |
| **Document Parser** | python-docx, antiword |
| **WebSocket** | Socket.io |
| **STT/TTS** | Custom services |

---

## ⚡ Đặc Điểm Nổi Bật

### **1. Legal-Aware Chunking**
- Tự động nhận diện cấu trúc văn bản pháp luật
- Giữ nguyên context pháp lý cho mỗi chunk
- Không cắt ngang Điều/Khoản/Điểm

### **2. Multi-Tenant Support**
- Base knowledge: Văn bản chung cho tất cả
- User knowledge: Văn bản riêng theo userId
- Group knowledge: Phân quyền theo groupId

### **3. Async Processing**
- Upload batch: 20 files/lần
- Worker pattern: Xử lý async qua Redis queue
- Non-blocking: Backend trả response ngay

### **4. Smart Retrieval**
- Hybrid filter: groupId + (base OR userId)
- Top-5 context chunks
- COSINE similarity matching

### **5. Context-Aware AI**
- System instruction: Chuyên gia BHXH
- Response rules: Ngắn gọn, có số liệu
- Anti-repetition: Không lặp lại lời chào

---

## 📊 Luồng Dữ Liệu (Data Flow)

```
Files → Backend → uploads/{userId}/ → Redis Queue
                                         ↓
                                    Embedding Worker
                                         ↓
                          Text Extraction + Chunking
                                         ↓
                               SentenceTransformer
                                         ↓
                                  Qdrant Vector DB
                                         ↑
User Query → Backend → Redis Queue → AI Worker
                                    ↓
                              Query Qdrant (Top-5)
                                    ↓
                         Context + Gemini AI
                                    ↓
                            Normalized Response
                                    ↓
                           TTS Worker → Audio
                                    ↓
                            WebSocket → User
```

---

## 🎯 Kết Luận

Hệ thống RAG này được thiết kế cho **tư vấn BHXH** với:
- ✅ **Chunking thông minh** theo cấu trúc pháp luật
- ✅ **Retrieval chính xác** với vector search
- ✅ **Multi-tenant** hỗ trợ nhiều nhóm người dùng
- ✅ **Async processing** với Redis queue
- ✅ **Voice interface** tích hợp STT/TTS
- ✅ **Context-aware AI** với Gemini

