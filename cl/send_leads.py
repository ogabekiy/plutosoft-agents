"""Collect interested customers' contact details and notify the owner on Telegram."""

import logging
import os
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from cl import chat_store


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN2", "").strip()
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID", "").strip()
TELEGRAM_API_URL = "https://api.telegram.org"

LEAD_PROMPT = "Xizmat bo'yicha bog'lanishimiz uchun ismingizni yuboring."
LEAD_INTENT_TERMS = (
    "narx",
    "qancha",
    "buyurtma",
    "buyurtma bermoq",
    "qiziqaman",
    "xizmat kerak",
    "xizmatga",
    "xizmatlaringiz",
    "sayt kerak",
    "sayt yasab",
    "veb-sayt",
    "web sayt",
    "telegram bot kerak",
    "bot kerak",
    "mobil ilova",
    "ilova kerak",
    "dastur kerak",
    "ishlab ber",
    "создать сайт",
    "разработка",
    "bog'lan",
    "boglan",
    "aloqa",
    "taklif",
    "zakaz",
    "цена",
    "заказ",
)

logger = logging.getLogger(__name__)
_lead_sessions: dict[tuple[str, str], dict[str, Any]] = {}
_lead_sessions_lock = threading.Lock()


def is_lead_intent(text: str) -> bool:
    normalized = text.casefold()
    return any(term in normalized for term in LEAD_INTENT_TERMS)


def send_lead(
    *,
    name: str,
    phone: str,
    note: str,
    summary: str,
    source: str,
    source_user_id: str,
) -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN2 .env faylida sozlanmagan.")
    if not TELEGRAM_USER_ID:
        raise RuntimeError("TELEGRAM_USER_ID .env faylida sozlanmagan.")
    try:
        recipient_id = int(TELEGRAM_USER_ID)
    except ValueError:
        raise RuntimeError("TELEGRAM_USER_ID sonli Telegram chat ID bo'lishi kerak.") from None

    message = (
        "Yangi mijoz murojaati\n"
        f"Manba: {source}\n"
        f"Ism: {name}\n"
        f"Telefon: {phone}\n"
        f"Qo'shimcha xabar: {note or 'yo‘q'}\n"
        f"Suhbat xulosasi: {summary or 'AI xulosasi tayyorlanmadi.'}\n"
        f"Manba foydalanuvchi ID: {source_user_id}"
    )
    try:
        response = requests.post(
            f"{TELEGRAM_API_URL}/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": recipient_id, "text": message},
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError("Telegram'ga lead yuborilmadi; token, chat ID yoki ulanishni tekshiring.") from None

    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError("Telegram Bot API lead yuborishni qabul qilmadi.")


def _valid_phone(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return bool(re.fullmatch(r"\+?[\d\s().-]{7,25}", text.strip())) and 9 <= len(digits) <= 15


def handle_lead_message(
    source: str,
    source_user_id: str,
    text: str,
) -> tuple[bool, bool, str | None]:
    """Return (handled, started, reply); active leads are collected before AI handling."""
    key = (source, str(source_user_id))
    normalized = text.strip()
    with _lead_sessions_lock:
        lead = _lead_sessions.get(key)
        if lead is None:
            if not is_lead_intent(normalized):
                return False, False, None
            _lead_sessions[key] = {"stage": "name", "lead_id": uuid.uuid4().hex}
            return False, True, None

        command = normalized.casefold()
        if command in {"/cancel", "bekor", "bekor qilish"}:
            del _lead_sessions[key]
            return True, False, "Mayli, murojaat qoldirish bekor qilindi."

        if lead["stage"] == "name":
            if len(normalized) < 2 or len(normalized) > 100:
                return True, False, "Ismni qaytadan yuboring (kamida 2 ta belgi)."
            lead["name"] = normalized
            lead["stage"] = "phone"
            return True, False, "Rahmat. Telefon raqamingizni xalqaro formatda yuboring."

        if lead["stage"] == "phone":
            if not _valid_phone(normalized):
                return True, False, "Telefon raqami noto'g'ri ko'rinadi. Masalan: +998901234567"
            lead["phone"] = normalized
            lead["stage"] = "note"
            return (
                True,
                False,
                "Qo'shimcha xabaringiz bo'lsa yuboring, bo'lmasa /skip deb yozing. "
                "Bekor qilish uchun /cancel.",
            )

        if lead["stage"] == "sending":
            return True, False, "Murojaatingiz yuborilmoqda, biroz kuting."

        if lead["stage"] == "pending":
            if command != "/retry":
                return True, False, "Murojaatni yuborishda xatolik bo'ldi. Qayta yuborish uchun /retry yozing."
            note = lead["note"]
        else:
            note = "" if command == "/skip" else normalized
            if len(note) > 1000:
                return True, False, "Qo'shimcha xabar 1000 belgidan oshmasin. Qisqartiring yoki /skip yozing."
            lead["note"] = note
        lead["stage"] = "sending"
        lead_copy = lead.copy()

    summary = ""
    try:
        conversation = chat_store.list_messages(
            source,
            str(source_user_id),
            limit=100,
        )
        if conversation:
            from chat_with_claude import summarize_conversation

            summary = summarize_conversation(conversation)
        else:
            logger.warning(
                "No conversation history found for lead %s; storing it without an AI summary.",
                lead_copy["lead_id"],
            )
    except Exception:
        logger.exception(
            "AI summary generation failed for lead %s; saving the lead without a summary.",
            lead_copy["lead_id"],
        )

    try:
        notification_configured = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID)
        chat_store.save_lead(
            lead_id=lead_copy["lead_id"],
            platform=source,
            source_user_id=str(source_user_id),
            name=lead_copy["name"],
            phone=lead_copy["phone"],
            note=lead_copy["note"],
            summary=summary,
            notification_status="pending" if notification_configured else "not_configured",
        )
        if notification_configured:
            try:
                send_lead(
                    name=lead_copy["name"],
                    phone=lead_copy["phone"],
                    note=lead_copy["note"],
                    summary=summary,
                    source=source,
                    source_user_id=str(source_user_id),
                )
            except (RuntimeError, sqlite3.Error):
                chat_store.update_lead_notification(lead_copy["lead_id"], "failed")
                raise
            chat_store.update_lead_notification(lead_copy["lead_id"], "sent")
        else:
            logger.info("Lead %s saved without Telegram notification credentials.", lead_copy["lead_id"])
    except RuntimeError:
        with _lead_sessions_lock:
            if key in _lead_sessions:
                _lead_sessions[key]["stage"] = "pending"
        logger.exception("Lead notification failed; lead remains available for retry.")
        return (
            True,
            False,
            "Murojaat saqlandi, lekin Telegram'ga yuborishda xatolik bo'ldi. "
            "Birozdan keyin /retry yozing.",
        )

    with _lead_sessions_lock:
        _lead_sessions.pop(key, None)
    return True, False, "Rahmat! Murojaatingiz yuborildi, tez orada siz bilan bog'lanamiz."