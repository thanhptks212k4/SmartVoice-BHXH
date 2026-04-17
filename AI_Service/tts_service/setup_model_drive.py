"""
Script chay 1 LAN DUY NHAT de tai toan bo model + checkpoint ve Google Drive.

Sau do moi lan chay wordker.py se load tu Drive, khong can tai lai.

Cach dung tren Colab:
    from google.colab import drive
    drive.mount('/content/drive')
    !python3 AI_Service/tts_service/setup_model_drive.py
"""

import os
import urllib.request
from huggingface_hub import snapshot_download
from TTS.utils.manage import ModelManager

# ============================================================
# CAU HINH - chinh duong dan nay cho dung voi Drive cua ban
# ============================================================
DRIVE_BASE = "/content/drive/MyDrive/DATN_PhamTienThanh/sourse_code/TTS_service"

DRIVE_MODEL_DIR      = os.path.join(DRIVE_BASE, "model")        # fine-tuned vnTTS
DRIVE_CHECKPOINT_DIR = os.path.join(DRIVE_BASE, "checkpoints",  # XTTS v2.0 goc
                                    "XTTS_v2.0_original_model_files")
# ============================================================


# ---------- Phan 1: Fine-tuned model (anhnh2002/vnTTS) ----------

def setup_finetuned_model():
    print("\n[1/2] FINE-TUNED MODEL (anhnh2002/vnTTS)")
    print("-" * 50)

    required = ["model.pth", "config.json", "vocab.json"]
    all_exist = all(
        os.path.isfile(os.path.join(DRIVE_MODEL_DIR, f)) for f in required
    )

    if all_exist:
        print(f"[OK] Da co day du tai: {DRIVE_MODEL_DIR}")
        for f in required:
            size_mb = os.path.getsize(os.path.join(DRIVE_MODEL_DIR, f)) / (1024 * 1024)
            print(f"     {f} ({size_mb:.1f} MB)")
        return True

    os.makedirs(DRIVE_MODEL_DIR, exist_ok=True)
    print(f"[DOWNLOAD] Dang tai tu HuggingFace: anhnh2002/vnTTS")
    print("Co the mat 10-20 phut...")

    try:
        snapshot_download(
            repo_id="anhnh2002/vnTTS",
            repo_type="model",
            local_dir=DRIVE_MODEL_DIR,
        )
        print(f"[SUCCESS] Fine-tuned model da luu tai: {DRIVE_MODEL_DIR}")
        for f in required:
            path = os.path.join(DRIVE_MODEL_DIR, f)
            if os.path.isfile(path):
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"  [OK] {f} ({size_mb:.1f} MB)")
            else:
                print(f"  [WARN] Khong tim thay: {f}")
        return True
    except Exception as e:
        print(f"[ERROR] Tai fine-tuned model that bai: {e}")
        return False


# ---------- Phan 2: XTTS v2.0 original checkpoint ----------

CHECKPOINT_FILES = {
    "dvae.pth":       "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/dvae.pth",
    "mel_stats.pth":  "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/mel_stats.pth",
    "vocab.json":     "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/vocab.json",
    "model.pth":      "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/model.pth",
    "config.json":    "https://coqui.gateway.scarf.sh/hf-coqui/XTTS-v2/main/config.json",
}

def setup_checkpoint():
    print("\n[2/2] XTTS v2.0 ORIGINAL CHECKPOINT")
    print("-" * 50)

    all_exist = all(
        os.path.isfile(os.path.join(DRIVE_CHECKPOINT_DIR, f))
        for f in CHECKPOINT_FILES
    )

    if all_exist:
        print(f"[OK] Da co day du tai: {DRIVE_CHECKPOINT_DIR}")
        for f in CHECKPOINT_FILES:
            size_mb = os.path.getsize(os.path.join(DRIVE_CHECKPOINT_DIR, f)) / (1024 * 1024)
            print(f"     {f} ({size_mb:.1f} MB)")
        return True

    os.makedirs(DRIVE_CHECKPOINT_DIR, exist_ok=True)
    print(f"[DOWNLOAD] Dang tai XTTS v2.0 checkpoint...")
    print("Co the mat 5-15 phut...")

    try:
        links_to_download = []
        for fname, url in CHECKPOINT_FILES.items():
            dest = os.path.join(DRIVE_CHECKPOINT_DIR, fname)
            if not os.path.isfile(dest):
                links_to_download.append(url)
            else:
                size_mb = os.path.getsize(dest) / (1024 * 1024)
                print(f"  [SKIP] {fname} da co ({size_mb:.1f} MB)")

        if links_to_download:
            ModelManager._download_model_files(
                links_to_download,
                DRIVE_CHECKPOINT_DIR,
                progress_bar=True
            )

        print(f"[SUCCESS] Checkpoint da luu tai: {DRIVE_CHECKPOINT_DIR}")
        for f in CHECKPOINT_FILES:
            path = os.path.join(DRIVE_CHECKPOINT_DIR, f)
            if os.path.isfile(path):
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"  [OK] {f} ({size_mb:.1f} MB)")
            else:
                print(f"  [WARN] Khong tim thay: {f}")
        return True
    except Exception as e:
        print(f"[ERROR] Tai checkpoint that bai: {e}")
        return False


# ---------- Main ----------

if __name__ == "__main__":
    print("=" * 60)
    print("SETUP MODEL + CHECKPOINT - Chi chay 1 lan")
    print("=" * 60)

    # Kiem tra Drive da mount chua
    if not os.path.exists("/content/drive/MyDrive"):
        print("\n[ERROR] Google Drive chua duoc mount!")
        print("Hay chay truoc:")
        print("  from google.colab import drive")
        print("  drive.mount('/content/drive')")
        exit(1)

    ok1 = setup_finetuned_model()
    ok2 = setup_checkpoint()

    print("\n" + "=" * 60)
    if ok1 and ok2:
        print("[DONE] Tat ca da san sang!")
        print(f"  Fine-tuned model : {DRIVE_MODEL_DIR}")
        print(f"  Checkpoint       : {DRIVE_CHECKPOINT_DIR}")
        print("\nTu nay chi can:")
        print("  from google.colab import drive")
        print("  drive.mount('/content/drive')")
        print("  !python3 AI_Service/tts_service/wordker.py")
    else:
        print("[WARN] Mot so file tai that bai, kiem tra lai loi o tren.")
    print("=" * 60)
