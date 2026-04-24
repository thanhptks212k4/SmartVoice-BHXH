"""
Script xoa va tao lai collection Qdrant de re-embed voi chunking moi.

Cach dung:
    # Xoa toan bo collection (re-embed tat ca)
    python3 reset_collection.py --mode all

    # Chi xoa data cua 1 group cu the
    python3 reset_collection.py --mode group --group-id <groupId>

    # Chi xoa data cua 1 user cu the
    python3 reset_collection.py --mode user --user-id <userId>

    # Xem thong tin collection hien tai
    python3 reset_collection.py --mode info
"""

import argparse
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PayloadSchemaType,
    Filter, FieldCondition, MatchValue,
)
from config.config import settings

COLLECTION_NAME = "thanhpt"

client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)


def show_info():
    if not client.collection_exists(COLLECTION_NAME):
        print(f"[INFO] Collection '{COLLECTION_NAME}' chua ton tai.")
        return
    info = client.get_collection(COLLECTION_NAME)
    count = client.count(COLLECTION_NAME)
    print(f"[INFO] Collection: {COLLECTION_NAME}")
    print(f"       Vectors   : {count.count}")
    print(f"       Vector dim: {info.config.params.vectors.size}")
    print(f"       Distance  : {info.config.params.vectors.distance}")


def delete_all():
    """Xoa toan bo collection va tao lai."""
    if client.collection_exists(COLLECTION_NAME):
        confirm = input(
            f"\n[WARN] Se XOA TOAN BO collection '{COLLECTION_NAME}'.\n"
            f"       Nhap 'yes' de xac nhan: "
        ).strip().lower()
        if confirm != "yes":
            print("[ABORT] Da huy.")
            return

        client.delete_collection(COLLECTION_NAME)
        print(f"[OK] Da xoa collection '{COLLECTION_NAME}'.")

    # Tao lai collection moi
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
    print(f"[OK] Da tao lai collection '{COLLECTION_NAME}' (rong).")
    print("[NEXT] Upload lai file de trigger re-embedding.")


def delete_by_group(group_id: str):
    """Xoa tat ca vectors cua 1 groupId."""
    if not client.collection_exists(COLLECTION_NAME):
        print(f"[ERROR] Collection '{COLLECTION_NAME}' chua ton tai.")
        return

    count_before = client.count(
        COLLECTION_NAME,
        count_filter=Filter(must=[
            FieldCondition(key="groupId", match=MatchValue(value=group_id))
        ])
    ).count

    if count_before == 0:
        print(f"[INFO] Khong co vector nao voi groupId='{group_id}'.")
        return

    confirm = input(
        f"\n[WARN] Se xoa {count_before} vectors cua groupId='{group_id}'.\n"
        f"       Nhap 'yes' de xac nhan: "
    ).strip().lower()
    if confirm != "yes":
        print("[ABORT] Da huy.")
        return

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(must=[
            FieldCondition(key="groupId", match=MatchValue(value=group_id))
        ]),
    )
    print(f"[OK] Da xoa {count_before} vectors cua groupId='{group_id}'.")
    print("[NEXT] Upload lai file voi token cua group nay de re-embed.")


def delete_by_user(user_id: str):
    """Xoa tat ca vectors cua 1 userId."""
    if not client.collection_exists(COLLECTION_NAME):
        print(f"[ERROR] Collection '{COLLECTION_NAME}' chua ton tai.")
        return

    count_before = client.count(
        COLLECTION_NAME,
        count_filter=Filter(must=[
            FieldCondition(key="userId", match=MatchValue(value=user_id))
        ])
    ).count

    if count_before == 0:
        print(f"[INFO] Khong co vector nao voi userId='{user_id}'.")
        return

    confirm = input(
        f"\n[WARN] Se xoa {count_before} vectors cua userId='{user_id}'.\n"
        f"       Nhap 'yes' de xac nhan: "
    ).strip().lower()
    if confirm != "yes":
        print("[ABORT] Da huy.")
        return

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(must=[
            FieldCondition(key="userId", match=MatchValue(value=user_id))
        ]),
    )
    print(f"[OK] Da xoa {count_before} vectors cua userId='{user_id}'.")
    print("[NEXT] Upload lai file de re-embed.")


def main():
    parser = argparse.ArgumentParser(description="Reset Qdrant collection cho re-embedding")
    parser.add_argument(
        "--mode", required=True,
        choices=["all", "group", "user", "info"],
        help="all=xoa toan bo | group=xoa theo group | user=xoa theo user | info=xem thong tin"
    )
    parser.add_argument("--group-id", help="groupId can xoa (dung voi --mode group)")
    parser.add_argument("--user-id",  help="userId can xoa (dung voi --mode user)")
    args = parser.parse_args()

    print(f"\n[Qdrant] {settings.QDRANT_HOST}:{settings.QDRANT_PORT} | Collection: {COLLECTION_NAME}")
    show_info()

    if args.mode == "info":
        return
    elif args.mode == "all":
        delete_all()
    elif args.mode == "group":
        if not args.group_id:
            print("[ERROR] Can truyen --group-id khi dung --mode group")
            sys.exit(1)
        delete_by_group(args.group_id)
    elif args.mode == "user":
        if not args.user_id:
            print("[ERROR] Can truyen --user-id khi dung --mode user")
            sys.exit(1)
        delete_by_user(args.user_id)


if __name__ == "__main__":
    main()
