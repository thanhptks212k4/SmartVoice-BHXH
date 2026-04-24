import os
import re
import uuid
import docx
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType
from sentence_transformers import SentenceTransformer
from config.config import settings

client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
model = SentenceTransformer(settings.MODEL_QDRANT)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
COLLECTION_NAME = "thanhpt"
UPLOAD_BASE_DIR = BASE_DIR / "uploads"

# ── Chunking config ──────────────────────────────────────────
MAX_CHARS   = 512   # ~256-512 token (1 token ≈ 1 char tiếng Việt)
OVERLAP_CHARS = 100  # ~20% overlap


def init_storage():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        for field_name in ("userId", "groupId"):
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        print(f"Đã khởi tạo collection: {COLLECTION_NAME}")

init_storage()


# ============================================================
# LEGAL DOCUMENT METADATA PARSER
# ============================================================

@dataclass
class LegalMeta:
    """Metadata gắn kèm mỗi chunk."""
    chuong: Optional[str] = None   # Chương I, II...
    dieu:   Optional[str] = None   # Điều 1, 2...
    khoan:  Optional[str] = None   # Khoản 1, 2...
    diem:   Optional[str] = None   # Điểm a, b...

    def to_dict(self) -> dict:
        return {k: v for k, v in {
            "chuong": self.chuong,
            "dieu":   self.dieu,
            "khoan":  self.khoan,
            "diem":   self.diem,
        }.items() if v is not None}


# Regex nhận diện ranh giới pháp lý (hỗ trợ cả chữ hoa/thường)
_RE_CHUONG = re.compile(
    r"^(chương\s+[IVXLCDM\d]+[^\n]*)", re.IGNORECASE | re.MULTILINE
)
_RE_DIEU = re.compile(
    r"^(điều\s+\d+[^\n]*)", re.IGNORECASE | re.MULTILINE
)
_RE_KHOAN = re.compile(
    r"^(\d+\.\s)", re.MULTILINE
)
_RE_DIEM = re.compile(
    r"^([a-z]\)\s)", re.MULTILINE
)


def _parse_doc_number(file_name: str) -> dict:
    """
    Trích xuất số hiệu văn bản từ tên file.
    VD: "115_2015_ND-CP.txt" → {"so_hieu": "115/2015/ND-CP"}
    """
    name = Path(file_name).stem
    # Thử match pattern: số_năm_loại
    m = re.match(r"(\d+)[_\-](\d{4})[_\-](.+)", name)
    if m:
        return {"so_hieu": f"{m.group(1)}/{m.group(2)}/{m.group(3).replace('_', '-')}"}
    return {"so_hieu": name}


def _detect_doc_type(file_name: str) -> str:
    """Phát hiện loại văn bản từ tên file hoặc nội dung."""
    name = file_name.upper()
    if "LUAT" in name or "LUẬT" in name:
        return "Luật"
    if "ND" in name or "NGHI_DINH" in name:
        return "Nghị định"
    if "TT" in name or "THONG_TU" in name:
        return "Thông tư"
    if "QD" in name or "QUYET_DINH" in name:
        return "Quyết định"
    return "Văn bản"


# ============================================================
# LEGAL-AWARE CHUNKER
# ============================================================

@dataclass
class _Segment:
    """Đơn vị nội dung pháp lý (Điều/Khoản/đoạn văn)."""
    text: str
    meta: LegalMeta


def _split_into_legal_segments(text: str) -> List[_Segment]:
    """
    Tách văn bản thành các segment theo cấu trúc pháp lý:
    Chương → Điều → Khoản → Điểm → câu thường.
    Mỗi segment mang metadata về vị trí trong văn bản.
    """
    # Chuẩn hóa
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text.strip())

    segments: List[_Segment] = []
    current_meta = LegalMeta()
    current_lines: List[str] = []

    def flush(meta: LegalMeta):
        content = " ".join(current_lines).strip()
        if content:
            segments.append(_Segment(text=content, meta=LegalMeta(
                chuong=meta.chuong,
                dieu=meta.dieu,
                khoan=meta.khoan,
                diem=meta.diem,
            )))
        current_lines.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Phát hiện Chương
        if _RE_CHUONG.match(stripped):
            flush(current_meta)
            current_meta = LegalMeta(chuong=stripped)
            current_lines.append(stripped)
            continue

        # Phát hiện Điều → flush segment trước
        if _RE_DIEU.match(stripped):
            flush(current_meta)
            current_meta = LegalMeta(
                chuong=current_meta.chuong,
                dieu=stripped,
            )
            current_lines.append(stripped)
            continue

        # Phát hiện Khoản (số. nội dung)
        if _RE_KHOAN.match(stripped):
            flush(current_meta)
            current_meta = LegalMeta(
                chuong=current_meta.chuong,
                dieu=current_meta.dieu,
                khoan=stripped[:20].strip(),
            )
            current_lines.append(stripped)
            continue

        # Phát hiện Điểm (a) b) c)...)
        if _RE_DIEM.match(stripped):
            flush(current_meta)
            current_meta = LegalMeta(
                chuong=current_meta.chuong,
                dieu=current_meta.dieu,
                khoan=current_meta.khoan,
                diem=stripped[:10].strip(),
            )
            current_lines.append(stripped)
            continue

        current_lines.append(stripped)

    flush(current_meta)
    return segments


def _split_sentences(text: str) -> List[str]:
    """Tách câu theo dấu câu tiếng Việt."""
    parts = re.split(r"(?<=[.!?;])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def legal_chunk(text: str, max_chars: int = MAX_CHARS,
                overlap_chars: int = OVERLAP_CHARS) -> List[dict]:
    """
    Chunking theo cấu trúc pháp lý:
    1. Tách thành segment theo Chương/Điều/Khoản/Điểm
    2. Nếu segment <= max_chars → giữ nguyên
    3. Nếu segment > max_chars → tách theo câu với overlap
    4. Mỗi chunk mang metadata pháp lý

    Returns: list of {"text": str, "meta": dict}
    """
    segments = _split_into_legal_segments(text)
    result: List[dict] = []

    for seg in segments:
        meta_dict = seg.meta.to_dict()

        if len(seg.text) <= max_chars:
            # Segment nhỏ → giữ nguyên
            result.append({"text": seg.text, "meta": meta_dict})
            continue

        # Segment lớn → tách theo câu với overlap
        sentences = _split_sentences(seg.text)
        current: List[str] = []
        current_len = 0

        for sent in sentences:
            sent_len = len(sent)

            if current_len + sent_len > max_chars and current:
                # Flush chunk hiện tại
                result.append({
                    "text": " ".join(current),
                    "meta": meta_dict,
                })
                # Giữ overlap
                overlap: List[str] = []
                overlap_len = 0
                for s in reversed(current):
                    if overlap_len + len(s) > overlap_chars:
                        break
                    overlap.insert(0, s)
                    overlap_len += len(s)
                current = overlap
                current_len = overlap_len

            current.append(sent)
            current_len += sent_len

        if current:
            result.append({
                "text": " ".join(current),
                "meta": meta_dict,
            })

    # Merge các chunk quá nhỏ (< 40% max) với chunk trước
    merged: List[dict] = []
    for chunk in result:
        if (merged and
                len(chunk["text"]) < max_chars * 0.4 and
                chunk["meta"] == merged[-1]["meta"]):
            merged[-1]["text"] += " " + chunk["text"]
        else:
            merged.append(chunk)

    return [c for c in merged if c["text"].strip()]


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_text(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8-sig") as f:
                return f.read()
        elif ext == ".docx":
            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        elif ext == ".doc":
            import subprocess
            result = subprocess.run(
                ["antiword", str(file_path)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
            print(f"  [WARN] antiword thất bại: {result.stderr.strip()}")
            with open(file_path, "rb") as f:
                return f.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [LỖI] Đọc file {file_path.name}: {e}")
    return ""


# ============================================================
# MAIN EMBEDDING PIPELINE
# ============================================================

def process_embedding_for_user(user_id: str, group_id: str, base: str):
    user_dir = Path(UPLOAD_BASE_DIR) / user_id
    if not user_dir.exists():
        print(f"Thư mục {user_id} không tồn tại")
        return

    user_id_payload = "base" if base == "yes" else user_id
    doc_type_default = "Văn bản"

    for file_path in user_dir.glob("*"):
        if file_path.suffix.lower() not in (".txt", ".docx", ".doc"):
            continue

        print(f"\n[🔄] Xử lý: {file_path.name}")
        content = extract_text(file_path)
        if not content.strip():
            print(f"  [SKIP] File rỗng: {file_path.name}")
            _mark_completed(file_path)
            continue

        # Chunking theo cấu trúc pháp lý
        chunks = legal_chunk(content, max_chars=MAX_CHARS, overlap_chars=OVERLAP_CHARS)
        print(f"  [INFO] {len(chunks)} chunks từ {len(content)} ký tự")

        # Encode vectors
        texts = [c["text"] for c in chunks]
        vectors = model.encode(texts, show_progress_bar=False).tolist()

        # Metadata văn bản
        doc_info = _parse_doc_number(file_path.name)
        doc_type = _detect_doc_type(file_path.name)

        # Build Qdrant points
        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            payload = {
                "groupId":    group_id,
                "userId":     user_id_payload,
                "fileName":   file_path.name,
                "so_hieu":    doc_info.get("so_hieu", ""),
                "loai_vb":    doc_type,
                "text":       chunk["text"],
                **chunk["meta"],   # chuong, dieu, khoan, diem nếu có
            }
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload,
            ))

        # Upsert vào Qdrant
        try:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"  [✅] Đã lưu {len(points)} vectors: {file_path.name}")
            _mark_completed(file_path)
        except Exception as e:
            print(f"  [❌] Lỗi upsert {file_path.name}: {e}")

    print(f"\n[DONE] Hoàn thành embedding cho user: {user_id}")


def _mark_completed(file_path: Path):
    try:
        completed = file_path.with_suffix(file_path.suffix + ".completed")
        file_path.rename(completed)
    except Exception as e:
        print(f"  [WARN] Không đổi tên file: {e}")
