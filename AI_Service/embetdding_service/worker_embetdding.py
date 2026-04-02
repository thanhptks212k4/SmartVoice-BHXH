import json
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from embetdding_service.redis_manager import redis_manager
from embetding_engine import process_embedding_for_user


def main():
  
    while True:
        
        task_data = redis_manager.listen_tasks("embedding_tasks")
        print(task_data)
        if task_data:
            try:
                topic, message = task_data
                data = json.loads(message)
                base = data.get("base")
                u_id = data.get("userId")
                groupId = data.get("groupId")
                


                # print(u_id)
                if u_id:
                    print(f"\n[🚀 START] Bắt đầu nhận task cho User: {u_id}")
                    

                    process_embedding_for_user(u_id ,groupId,base)
                    
                    print(f"[✅ DONE] Lưu DB và cập nhật trạng thái file hoàn tất.")
                    print(f"[🧹 CLEANUP] Đã xóa message khỏi queue. Hoàn thành toàn bộ quy trình cho {u_id}\n")
                else:
                    print(" Task không hợp lệ (thiếu userId)")

            except Exception as e : 
                print(f"Lỗi khi xử lý task",e)
       

if __name__ == "__main__":
    main()