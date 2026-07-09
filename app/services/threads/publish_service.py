import logging
import os
import time

import requests

logger = logging.getLogger(__name__)


THREADS_API_BASE_URL = "https://graph.threads.net/v1.0"
PUBLISH_RETRY_DELAYS = [2, 4, 8]


def publish_thread_post(content: str) -> str:
    access_token = os.getenv("THREADS_ACCESS_TOKEN")
    user_id = os.getenv("THREADS_USER_ID")

    if not access_token or not user_id:
        raise ValueError("THREADS_ACCESS_TOKEN 또는 THREADS_USER_ID가 설정되어 있지 않습니다.")

    logger.info("Threads container 생성 시작: 글자수=%s user_id=%s", len(content), user_id)
    try:
        create_response = requests.post(
            f"{THREADS_API_BASE_URL}/{user_id}/threads",
            data={
                "media_type": "TEXT",
                "text": content,
                "access_token": access_token,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        logger.exception("Threads container 요청 실패: 오류=%s", e)
        raise RuntimeError(f"Threads container 요청 실패: {e}") from e

    if not create_response.ok:
        logger.error(
            "Threads container 생성 실패: 상태코드=%s 응답=%s",
            create_response.status_code,
            create_response.text,
        )
        raise RuntimeError(
            f"Threads container 생성 실패: {create_response.status_code} {create_response.text}"
        )

    creation_id = create_response.json().get("id")
    if not creation_id:
        raise RuntimeError("Threads container 생성 응답에 id가 없습니다.")
    logger.info("Threads container 생성 완료: creation_id=%s", creation_id)

    threads_post_id = publish_with_retry(user_id, access_token, creation_id)

    return str(threads_post_id)


def publish_with_retry(user_id: str, access_token: str, creation_id: str) -> str:
    last_error_message = ""
    attempt = 0

    for index, delay_seconds in enumerate(PUBLISH_RETRY_DELAYS):
        attempt += 1
        logger.info("Threads publish 시도: creation_id=%s 시도횟수=%s", creation_id, attempt)
        try:
            publish_response = requests.post(
                f"{THREADS_API_BASE_URL}/{user_id}/threads_publish",
                data={
                    "creation_id": creation_id,
                    "access_token": access_token,
                },
                timeout=30,
            )
        except requests.RequestException as e:
            logger.exception("Threads publish 요청 실패: creation_id=%s 시도횟수=%s 오류=%s", creation_id, attempt, e)
            raise RuntimeError(f"Threads 게시 요청 실패: {e}") from e

        if publish_response.ok:
            threads_post_id = publish_response.json().get("id")
            if not threads_post_id:
                raise RuntimeError("Threads 게시 응답에 id가 없습니다.")
            logger.info("Threads publish 성공: threads_post_id=%s 시도횟수=%s", threads_post_id, attempt)
            return str(threads_post_id)

        last_error_message = (
            f"Threads 게시 실패: {publish_response.status_code} {publish_response.text}"
        )

        if not is_transient_publish_error(publish_response):
            logger.error("Threads publish 실패: 재시도불가 시도횟수=%s 응답=%s", attempt, publish_response.text)
            raise RuntimeError(last_error_message)

        logger.warning(
            "Threads publish 일시적 실패: 시도횟수=%s 다음대기초=%s 응답=%s",
            attempt,
            delay_seconds if index < len(PUBLISH_RETRY_DELAYS) - 1 else 0,
            publish_response.text,
        )
        if index < len(PUBLISH_RETRY_DELAYS) - 1:
            time.sleep(delay_seconds)

    raise RuntimeError(last_error_message or "Threads 게시 실패: 알 수 없는 오류")


def is_transient_publish_error(response: requests.Response) -> bool:
    try:
        error = response.json().get("error", {})
    except ValueError:
        return False

    return bool(error.get("is_transient")) or error.get("code") == 2
