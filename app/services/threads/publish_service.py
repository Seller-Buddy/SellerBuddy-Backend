import os

import requests


THREADS_API_BASE_URL = "https://graph.threads.net/v1.0"


def publish_thread_post(content: str) -> str:
    access_token = os.getenv("THREADS_ACCESS_TOKEN")
    user_id = os.getenv("THREADS_USER_ID")

    if not access_token or not user_id:
        raise ValueError("THREADS_ACCESS_TOKEN 또는 THREADS_USER_ID가 설정되어 있지 않습니다.")

    create_response = requests.post(
        f"{THREADS_API_BASE_URL}/{user_id}/threads",
        data={
            "media_type": "TEXT",
            "text": content,
            "access_token": access_token,
        },
        timeout=30,
    )

    if not create_response.ok:
        raise RuntimeError(
            f"Threads container 생성 실패: {create_response.status_code} {create_response.text}"
        )

    creation_id = create_response.json().get("id")
    if not creation_id:
        raise RuntimeError("Threads container 생성 응답에 id가 없습니다.")

    publish_response = requests.post(
        f"{THREADS_API_BASE_URL}/{user_id}/threads_publish",
        data={
            "creation_id": creation_id,
            "access_token": access_token,
        },
        timeout=30,
    )

    if not publish_response.ok:
        raise RuntimeError(
            f"Threads 게시 실패: {publish_response.status_code} {publish_response.text}"
        )

    threads_post_id = publish_response.json().get("id")
    if not threads_post_id:
        raise RuntimeError("Threads 게시 응답에 id가 없습니다.")

    return str(threads_post_id)
