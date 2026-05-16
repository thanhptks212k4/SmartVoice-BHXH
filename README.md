<div align="center">

# ⚖️ SmartVoice BHXH

### Trợ lý ảo tiếng Việt tư vấn Bảo hiểm Xã hội

*Hỏi bằng giọng nói - Nhận câu trả lời tức thì*

[![Made with React](https://img.shields.io/badge/React-19.2-61DAFB?logo=react)](https://reactjs.org/)
[![Powered by Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=google)](https://ai.google.dev/)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python)](https://python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Demo](#-demo) • [Tính năng](#-tính-năng) • [Công nghệ](#-công-nghệ) • [Cài đặt](#-cài-đặt) • [Tác giả](#-tác-giả)

</div>

---

## 🎯 Giới thiệu

**SmartVoice BHXH** là trợ lý ảo thông minh giúp bạn tra cứu thông tin về Bảo hiểm Xã hội chỉ bằng giọng nói. Hệ thống sử dụng AI để hiểu câu hỏi, tìm kiếm trong văn bản pháp lý và trả lời bằng giọng nói tự nhiên - tất cả diễn ra trong vài giây.

### 💡 Tại sao chọn SmartVoice?

- 🎤 **Tương tác giọng nói**: Không cần gõ phím, chỉ cần nói
- ⚡ **Phản hồi nhanh**: Câu trả lời trong 1-2 giây
- 📚 **Chính xác**: Dựa trên văn bản pháp luật thực tế
- 🇻🇳 **Tiếng Việt tự nhiên**: Giọng nói như người thật
- 🔒 **Bảo mật**: Dữ liệu được lưu trữ nội bộ

---

## ✨ Tính năng

### 🗣️ Nhận dạng giọng nói (ASR)
- Nhận dạng tiếng Việt chính xác với Whisper AI
- Tự động phát hiện khi bạn bắt đầu/kết thúc nói
- Lọc nhiễu thông minh

### 🤖 Trả lời thông minh (RAG + LLM)
- Tìm kiếm trong hàng nghìn trang văn bản pháp lý
- Trả lời dựa trên Luật BHXH, Nghị định, Thông tư
- Powered by Google Gemini AI

### 🔊 Giọng nói tự nhiên (TTS)
- Giọng nữ Hà Nội chuẩn
- Phát âm số hiệu văn bản chính xác
- Streaming audio mượt mà

---

## 🛠️ Công nghệ

<table>
<tr>
<td width="50%">

**Frontend**
- React 19 + Vite
- Tailwind CSS
- WebSocket real-time

</td>
<td width="50%">

**Backend**
- Node.js + Express
- PostgreSQL
- Redis Queue

</td>
</tr>
<tr>
<td>

**AI Services**
- Google Gemini 2.5 Flash
- Whisper (Speech-to-Text)
- XTTS v2 (Text-to-Speech)

</td>
<td>

**Infrastructure**
- Docker Compose
- Qdrant Vector DB
- Microservices Architecture

</td>
</tr>
</table>

---

## 🚀 Cài đặt

### Yêu cầu hệ thống
- Ubuntu 22.04 / Windows 10+
- 8GB RAM (16GB khuyến nghị)
- Docker & Docker Compose
- Node.js 18+
- Python 3.10+

### Cài đặt nhanh

```bash
# 1. Clone repository
git clone https://github.com/yourusername/SmartVoice-BHXH.git
cd SmartVoice-BHXH

# 2. Cấu hình environment
cp .env.example .env
# Chỉnh sửa .env với API keys của bạn

# 3. Khởi động hệ thống
bash start.sh

# 4. Truy cập ứng dụng
# Frontend: http://localhost:5173
# Backend: http://localhost:3000
```

---

## 📸 Demo

### Giao diện đăng nhập
```
⚖️
TRỢ LÝ ẢO TIẾNG VIỆT
TƯ VẤN BẢO HIỂM XÃ HỘI
```

### Giao diện chat
```
🎤 Nói: "Điều kiện hưởng trợ cấp thất nghiệp?"
🤖 Trả lời: "Người lao động hưởng trợ cấp thất nghiệp khi..."
```

---

## 📖 Cách sử dụng

1. **Đăng nhập** vào hệ thống
2. **Nhấn giữ mic** hoặc để mic luôn bật
3. **Nói câu hỏi** về BHXH
4. **Nghe câu trả lời** bằng giọng nói

### Ví dụ câu hỏi

- "Mức đóng BHXH là bao nhiêu?"
- "Điều kiện hưởng thai sản?"
- "Thủ tục đăng ký BHYT như thế nào?"
- "So sánh BHXH bắt buộc và tự nguyện?"

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Browser   │◄────►│   Backend    │◄────►│  AI Worker  │
│  (React)    │ WS   │  (Node.js)   │ Redis│  (Python)   │
└─────────────┘      └──────────────┘      └─────────────┘
       │                     │                      │
       │                     ▼                      ▼
       │              ┌──────────────┐      ┌─────────────┐
       │              │  PostgreSQL  │      │   Qdrant    │
       │              │   Database   │      │  Vector DB  │
       │              └──────────────┘      └─────────────┘
       │
       ▼
┌─────────────┐      ┌──────────────┐
│ STT Server  │      │  TTS Worker  │
│  (Whisper)  │      │   (XTTS)     │
└─────────────┘      └──────────────┘
```

---

## 👨‍💻 Tác giả

**Phạm Tiến Thành**  
📧 Email: phamtienthanh21022004@gmail.com  
🎓 Đồ án tốt nghiệp - Trường Đại học Công nghệ Thông tin

---

## 📄 License

Dự án này được phát hành dưới giấy phép [MIT License](LICENSE).

---

## 🙏 Lời cảm ơn

- [Google Gemini](https://ai.google.dev/) - LLM API
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech Recognition
- [Coqui TTS](https://github.com/coqui-ai/TTS) - Text-to-Speech
- [Qdrant](https://qdrant.tech/) - Vector Database

---

<div align="center">

**⭐ Nếu bạn thấy dự án hữu ích, hãy cho một ngôi sao! ⭐**

Made with ❤️ in Vietnam

</div>
