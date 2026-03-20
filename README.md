# ⚙️ Chatbot Backend Microservice

Dự án **Chatbot Backend Microservice** được thiết kế theo kiến trúc **microservice**, cho phép xử lý **song song các luồng dữ liệu** và mở rộng linh hoạt.  
Hệ thống hỗ trợ **đa người dùng**, **WebSocket**, và **AI Worker** hoạt động song song.

---

## 🧠 Thành phần hệ thống

| Thành phần | Công nghệ | Mô tả |
|-------------|------------|--------|
| **Backend** | Node.js | Quản lý API, WebSocket, người dùng, giao tiếp với Redis |
| **AI Service** | Python | Xử lý logic AI, có thể mở rộng bằng nhiều worker song song |
| **PostgreSQL** | Database | Lưu người dùng và lịch sử chat |
| **Redis** | Cache/Message Queue | Giao tiếp giữa các service |
| **Qdrant** | Vector DB | Lưu embedding và tìm kiếm ngữ nghĩa |

---

## 🚀 Cài đặt & Chạy hệ thống

### 🪜 Bước 1: Khởi chạy các service nền tảng

```bash
cd chatbot
docker compose up -d
```

➡️ Lệnh này sẽ chạy ngầm các service:
- **PostgreSQL**
- **Redis**
- **Qdrant**

---

### 🪜 Bước 2: Cài đặt & khởi chạy Backend

```bash
npm install
npm start
```

➡️ Backend chạy tại địa chỉ:  
👉 **http://localhost:3000**

---

### 🪜 Bước 3: Chạy AI Service (Python)

```bash
cd AI_Service
docker compose up --scale ai_worker=5
```

> 🔧 Thay đổi số lượng `ai_worker` tùy theo cấu hình máy để tối ưu hiệu năng.  
Ví dụ: `--scale ai_worker=2` cho máy yếu hoặc `--scale ai_worker=10` cho máy mạnh.

➡️ AI service chạy tại:  
👉 **http://localhost:5000**

---

### 🪜 Bước 4: Kiểm thử hệ thống

Chạy script kiểm thử mẫu:

```bash
python3 client/test.py
```

✅ Nếu kết nối thành công, bạn sẽ thấy:
```
 Đang đăng nhập tài khoản: <username>...
 Lấy Token thành công!
 WebSocket đã thông! Bạn có thể bắt đầu chat.
```

---

## ⚙️ Cấu hình môi trường

Tạo file `.env` tại thư mục gốc:

```bash
PORT=3000
JWT_SECRET=supersecret

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=chatbot

REDIS_HOST=redis
REDIS_PORT=6379

AI_API_URL=http://ai_service:5000
```

---

## 📁 Cấu trúc dự án

```
chatbot/
├── backend/              # Node.js service
│   ├── src/
│   ├── routes/
│   └── server.js
│
├── AI_Service/           # Python service
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── client/               # Script kiểm thử
│   └── test.py
│
├── docker-compose.yml
├── .env
└── README.md
```

---

## 🧩 Công nghệ sử dụng
- **Node.js / Express**
- **Python / FastAPI**
- **Redis**
- **PostgreSQL**
- **Qdrant**
- **Docker Compose**

---

## 💡 Ghi chú
- Có thể mở rộng thêm **AI worker** khi cần tăng khả năng xử lý song song.  
- Tất cả các container có thể theo dõi bằng lệnh:
  ```bash
  docker ps
  docker logs -f <container_name>
  ```
- Để dừng toàn bộ hệ thống:
  ```bash
  docker compose down
  ```


kiemr tra redis
docker exec -it redis_ai_service redis-cli MONITORdocker exec -it redis_ai_service redis-cli MONITOR
---

## 👨‍💻 Tác giả
**Duy Đỗ (doduy-AI)**  
📧 [dev.dinhduy@gmail.com](mailto:dev.dinhduy@gmail.com)

---

> ⭐ *Nếu bạn thấy dự án hữu ích, hãy để lại một star để ủng hộ nhé!*
