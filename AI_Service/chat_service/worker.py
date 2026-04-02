import json , os , sys
from redis_manager import redis_manager
from normalize_text import normalize_text

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import settings


from concurrent.futures import ThreadPoolExecutor
from ai_engine import AIEngine 
executor = ThreadPoolExecutor(max_workers=10)
ai = AIEngine() 


def handle_task(data):
    print("check2")
    user_id = data.get("userId")
    text = data.get("text")
    group_id = data.get("groupId")
    voice = data.get("voice")
    if text == "disconectuser":
        ai.delete_session(user_id)
        return

    reply = ai.generate_respone(text, user_id, group_id)
    print("[BHXH]", reply)

    reply_tts = normalize_text(reply)
    print("[TTS TEXT]", reply_tts)

    redis_manager.publish("tts_tasks", {
        "userId": user_id,
        "reply": reply_tts,
        "voice": voice,
        "status": "success"
    })

    # redis_manager.publish(f"voice_ready:{user_id}", {
    #             "type": "AI_VOICE_REPLY",
    #             "text": text,
    #             "audioUrl": "http://192.168.1.35:3001/giongnuhanoi6s.wav"
    #         })
    # print(f" Đã trả lời {user_id}")



def main():
    print(" sẵn sàng")
    print('[MODEL]', settings.MODEL_NAME)

    while True:
        task_data = redis_manager.listen_tasks("ai_tasks")
        print(task_data)
            
        if task_data:
            data = json.loads(task_data[1])
            executor.submit(handle_task, data)


if __name__ == "__main__":
    main()
