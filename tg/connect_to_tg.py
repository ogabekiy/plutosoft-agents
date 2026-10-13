"""Telegram long-polling bot that replies with the PlutoSoft AI assistant."""

import logging
import os
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API_URL = "https://api.telegram.org"
TELEGRAM_MESSAGE_LIMIT = 4096
POLL_TIMEOUT_SECONDS = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
message_executor = ThreadPoolExecutor(max_workers=4)


def telegram_api(method: str, payload: dict[str, Any], timeout: int = 40) -> Any:
    """Call Telegram Bot API and raise an error for unsuccessful responses."""
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/bot{TELEGRAM_BOT_TOKEN}/{method}",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException:
        raise RuntimeError(
            f"Telegram {method} request failed with an HTTP or network error."
        ) from None

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram {method} request failed: {result}")
    return result.get("result")


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split long replies into Telegram-sized chunks, preferring word boundaries."""
    parts = []
    remaining = text.strip()

    while len(remaining) > limit:
        split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at <= 0:
            split_at = limit
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        parts.append(remaining)
    return parts


def send_message(chat_id: int, text: str) -> None:
    for part in split_message(text):
        telegram_api("sendMessage", {"chat_id": chat_id, "text": part})


def send_and_record(
    chat_id: int,
    display_name: str,
    text: str,
) -> None:
    send_message(chat_id, text)
    from cl.chat_store import record_message

    record_message(
        platform="Telegram",
        external_id=str(chat_id),
        display_name=display_name,
        role="assistant",
        text=text,
    )


def handle_message(
    chat_id: int,
    sender_id: int,
    display_name: str,
    text: str,
) -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from cl.send_leads import LEAD_PROMPT, handle_lead_message

    handled, started, lead_reply = handle_lead_message(
        "Telegram",
        str(sender_id),
        text,
    )
    if handled:
        if lead_reply:
            send_and_record(chat_id, display_name, lead_reply)
        return

    from chat_with_claude import generate_answer

    answer = generate_answer(text)
    reply_parts = [part for part in (answer, LEAD_PROMPT if started else "") if part]
    if reply_parts:
        send_and_record(chat_id, display_name, "\n\n".join(reply_parts))


def handle_update(update: dict[str, Any]) -> None:
    message = update.get("message")
    if not isinstance(message, dict):
        return

    sender = message.get("from")
    chat = message.get("chat")
    text = message.get("text")
    if (
        not isinstance(sender, dict)
        or sender.get("is_bot")
        or not isinstance(sender.get("id"), int)
        or not isinstance(chat, dict)
        or not isinstance(chat.get("id"), int)
        or not isinstance(text, str)
        or not text.strip()
    ):
        return

    chat_id = chat["id"]
    from cl.chat_store import get_profile, record_message, update_profile

    cached_profile = get_profile("Telegram", str(chat_id))
    display_name = " ".join(
        part
        for part in (sender.get("first_name"), sender.get("last_name"))
        if isinstance(part, str) and part
    )
    if not display_name:
        display_name = (
            (f"@{sender['username']}" if isinstance(sender.get("username"), str) else None)
            or (cached_profile.get("display_name") if cached_profile else None)
            or str(sender["id"])
        )

    username = sender.get("username") or (
        cached_profile.get("username") if cached_profile else None
    )
    avatar_file_id = (
        cached_profile.get("avatar_file_id")
        if cached_profile
        else None
    )
    if not avatar_file_id:
        try:
            photo_result = telegram_api(
                "getUserProfilePhotos",
                {"user_id": sender["id"], "limit": 1},
                timeout=15,
            )
            photos = photo_result.get("photos", []) if isinstance(photo_result, dict) else []
            if photos and photos[0]:
                photo = max(
                    (item for item in photos[0] if isinstance(item, dict)),
                    key=lambda item: item.get("width", 0) * item.get("height", 0),
                    default={},
                )
                avatar_file_id = photo.get("file_id")
        except (requests.RequestException, RuntimeError, ValueError):
            logger.warning(
                "Telegram profile photo is unavailable for user %s.",
                sender["id"],
                exc_info=True,
            )
    update_profile(
        platform="Telegram",
        external_id=str(chat_id),
        display_name=display_name,
        username=username,
        avatar_file_id=avatar_file_id,
    )

    record_message(
        platform="Telegram",
        external_id=str(chat_id),
        display_name=display_name,
        role="customer",
        text=text.strip(),
        message_key=(
            f"{chat_id}:{message['message_id']}"
            if message.get("message_id") is not None
            else None
        ),
    )

    command = text.split(maxsplit=1)[0].split("@", maxsplit=1)[0]
    if command in {"/start", "/help"}:
        send_and_record(
            chat_id,
            display_name,
            "Salom! PlutoSoft AI yordamchisiga xush kelibsiz. Savolingizni yozing.",
        )
        return

    message_executor.submit(
        handle_message,
        chat_id,
        sender["id"],
        display_name,
        text.strip(),
    ).add_done_callback(
        log_message_error
    )


def log_message_error(future: Future[None]) -> None:
    error = future.exception()
    if error is not None:
        logger.error(
            "Could not generate or send a Telegram reply.",
            exc_info=(type(error), error, error.__traceback__),
        )


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN topilmadi. Uni loyiha ildizidagi .env fayliga kiriting."
        )

    telegram_api("deleteWebhook", {"drop_pending_updates": False}, timeout=15)
    me = telegram_api("getMe", {}, timeout=15)
    logger.info("Telegram bot @%s ishga tushdi.", me.get("username", ""))
    offset = 0

    while True:
        try:
            updates = telegram_api(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": POLL_TIMEOUT_SECONDS,
                    "allowed_updates": ["message"],
                },
                timeout=POLL_TIMEOUT_SECONDS + 10,
            )
            for update in updates:
                offset = max(offset, update["update_id"] + 1)
                handle_update(update)
        except (requests.RequestException, RuntimeError, ValueError, KeyError):
            logger.exception("Telegram bilan aloqa yoki update'ni qayta ishlashda xatolik.")
            time.sleep(3)


if __name__ == "__main__":
    main()