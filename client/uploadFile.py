import os
import sys
import requests

# --- CẤU HÌNH ---
API_URL = 'http://localhost:3000/api/admin/rag/uploadfile'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjVjMDI3ZTc1LTUyYTctNDAyNC05ZmQ0LTcxNDFmNWI1MDA1MyIsInVzZXJuYW1lIjoiYWRtaW4iLCJpYXQiOjE3NzQwMDc5ODcsImV4cCI6MTc3NjU5OTk4N30.cIjiFTeYpZIxm6oDfZqYfrF_jiaFCTThiqqpRxaiyNQ'  # Dán token của bạn vào đây
TARGET_DIR = r'\\wsl.localhost\Ubuntu-22.04\home\thanhserveice\data_BHXH'  # Thư mục chứa 1000 file (có folder con)
GROUP_ID = '028686bd-00d7-4def-a900-5f1aa97e2849' # Thêm GroupID của bạn vào đây
BATCH_SIZE = 20  # Số file gửi mỗi lần

def fix_long_path(path):
    """Thêm prefix \\\\?\\UNC\\ để Windows hỗ trợ đường dẫn dài hơn 260 ký tự"""
    if sys.platform == 'win32' and path.startswith('\\\\') and not path.startswith('\\\\?\\'):
        return '\\\\?\\UNC\\' + path[2:]
    return path

def get_all_files_recursive(directory):
    """Quét sạch mọi file trong mọi ngóc ngách thư mục con"""
    long_dir = fix_long_path(directory)
    file_list = []
    for root, dirs, files in os.walk(long_dir):
        for file in files:
            full_path = os.path.join(root, file)
            file_list.append(full_path)
    return file_list

def start_upload_all():
    # 1. Quét toàn bộ file
    print(f"🔍 Đang quét sạch thư mục: {TARGET_DIR}...")
    all_files = get_all_files_recursive(TARGET_DIR)
    total = len(all_files)
    
    if total == 0:
        print("❌ Không thấy file nào để upload!")
        return

    print(f"🚀 Tìm thấy {total} file. Đang gửi theo batch ({BATCH_SIZE} file/lần)...")

    headers = {'Authorization': f'Bearer {TOKEN}'}
    data_payload = {'groupId': GROUP_ID}

    success_count = 0
    fail_count = 0
    failed_files = []

    # Gửi theo batch
    for i in range(0, total, BATCH_SIZE):
        batch = all_files[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n📤 Batch {batch_num}/{total_batches} ({len(batch)} file)...")

        files_payload = []
        opened_files = []

        try:
            for file_path in batch:
                try:
                    f = open(file_path, 'rb')
                    opened_files.append(f)
                    files_payload.append(('files', (os.path.basename(file_path), f)))
                except Exception as e:
                    print(f"  ⚠️ Không mở được: {os.path.basename(file_path)} - {e}")
                    fail_count += 1
                    failed_files.append(file_path)

            if not files_payload:
                print("  ⏭️ Batch trống, bỏ qua...")
                continue

            response = requests.post(
                API_URL,
                headers=headers,
                data=data_payload,
                files=files_payload,
                timeout=1200
            )

            if response.status_code == 200:
                success_count += len(files_payload)
                print(f"  ✅ OK! ({success_count}/{total})")
            else:
                fail_count += len(files_payload)
                print(f"  ❌ Lỗi {response.status_code}: {response.text[:200]}")

        except Exception as e:
            fail_count += len(files_payload)
            print(f"  ⚠️ Lỗi batch: {e}")

        finally:
            for f in opened_files:
                f.close()

    # Tổng kết
    print(f"\n{'='*50}")
    print(f"🏁 Hoàn tất! ✅ {success_count} thành công | ❌ {fail_count} thất bại / {total} tổng")
    if failed_files:
        print(f"\n📋 File lỗi:")
        for fp in failed_files[:20]:
            print(f"  - {os.path.basename(fp)}")
        if len(failed_files) > 20:
            print(f"  ... và {len(failed_files) - 20} file nữa")

if __name__ == "__main__":
    start_upload_all()