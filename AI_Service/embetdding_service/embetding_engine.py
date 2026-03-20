import os
import uuid
import docx
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType
from sentence_transformers import SentenceTransformer
from config.config import settings
client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
model = SentenceTransformer(settings.MODEL_QDRANT)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
COLLECTION_NAME = "thanhpt"
UPLOAD_BASE_DIR = BASE_DIR / "uploads"

def init_storage():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="userId",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="groupId",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        print(f" Đã khởi tạo thành công collection: {COLLECTION_NAME}")

init_storage()

def extract_text(file_path):
    ext = file_path.suffix.lower()
    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8-sig") as f:
                return f.read()
        elif ext == ".docx":
            doc = docx.Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print(f" Lỗi đọc file {file_path.name}: {e}")
    return ""


def process_embedding_for_user(user_id, group_id, base):
    user_dir = Path(UPLOAD_BASE_DIR) / user_id
    if not user_dir.exists():
        print(f"Thư mục {user_id} không tồn tại")
        return

    # Xác định userId lưu vào payload
    userIdBase = "base" if base == 'yes' else user_id

    # Duyệt từng file trong thư mục
    for file_path in user_dir.glob("*"):
        if file_path.suffix.lower() in [".txt", ".docx"]:
            print(f"\n[🔄 ĐANG XỬ LÝ] Bắt đầu trích xuất và embedding file: {file_path.name}")
            content = extract_text(file_path)
            
            if not content.strip():
                continue

            # Chia nhỏ văn bản của file hiện tại
            chunks = [content[i:i+600] for i in range(0, len(content), 600)]
            
            # Tạo vector cho file hiện tại
            vectors = model.encode(chunks).tolist()
            
            # Gom points của RIÊNG file này vào một danh sách tạm
            current_file_points = []
            for idx, vector in enumerate(vectors):
                current_file_points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "groupId": group_id,
                        "userId": userIdBase,                        
                        "fileName": file_path.name,
                        "text": chunks[idx]
                    }
                ))

            # --- SỬA ĐỔI CHÍNH: LƯU VÀO QDRANT NGAY SAU MỖI FILE ---
            if current_file_points:
                try:
                    client.upsert(
                        collection_name=COLLECTION_NAME, 
                        points=current_file_points
                    )
                    print(f"    [💾 LƯU DB THÀNH CÔNG] Đã lưu {len(current_file_points)} vector của file: {file_path.name} vào Qdrant.")
                    
                    # Đổi tên file để cập nhật trạng thái "hoàn thành", tránh script khác quét lại
                    completed_path = file_path.with_suffix(file_path.suffix + ".completed")
                    file_path.rename(completed_path)
                    print(f"    [🏷️ CẬP NHẬT TRẠNG THÁI] Đã đổi tên file thành '{completed_path.name}' để đánh dấu completed.")
                except Exception as e:
                    print(f"    [❌ LỖI] Lỗi khi đẩy file {file_path.name} lên Qdrant hoặc khi đổi tên: {e}")
            else:
                 # Đổi tên file rỗng/không hợp lệ để không bị kẹt ở các vòng lặp sau
                 try:
                     completed_path = file_path.with_suffix(file_path.suffix + ".completed")
                     file_path.rename(completed_path)
                     print(f"    [🏷️ BỎ QUA] File rỗng hoặc không thể trích xuất text. Đã đổi tên file thành '{completed_path.name}'.")
                 except Exception as e:
                     print(f"    [❌ LỖI] Không thể đổi tên file rỗng {file_path.name}: {e}")
            # -----------------------------------------------------

    print(f"\n[✅ COMPLETE] Hoàn thành xử lý toàn bộ file cho User: {user_id}")
