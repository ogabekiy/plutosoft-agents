"""Password-protected inbox dashboard for Instagram and Telegram conversations."""

import hmac
import os
import secrets
from functools import wraps
from pathlib import Path

import requests
from dotenv import set_key
from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from cl import chat_store


dashboard = Blueprint(
    "dashboard",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/dashboard/assets",
)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "").strip()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MODELS = (
    "claude-haiku-5-5",
    "claude-sonnet-5-5",
    "claude-opus-5-5",
)


@dashboard.after_request
def protect_dashboard_responses(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    return response


def _require_password_configured():
    if not DASHBOARD_PASSWORD:
        return (
            "Dashboard login sozlanmagan. .env fayliga DASHBOARD_PASSWORD qo'shing.",
            503,
        )
    return None


def _require_login(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        configured = _require_password_configured()
        if configured:
            return configured
        if not session.get("dashboard_authenticated"):
            if request.path.startswith("/dashboard/api/"):
                return jsonify(error="Authentication required."), 401
            return redirect(url_for("dashboard.login"))
        return function(*args, **kwargs)

    return decorated


def _csrf_token() -> str:
    if "dashboard_csrf" not in session:
        session["dashboard_csrf"] = secrets.token_urlsafe(32)
    return session["dashboard_csrf"]


@dashboard.get("/dashboard/login")
def login():
    configured = _require_password_configured()
    if configured:
        return configured
    if session.get("dashboard_authenticated"):
        return redirect(url_for("dashboard.home"))
    return render_template("dashboard_login.html", csrf_token=_csrf_token(), error=None)


@dashboard.post("/dashboard/login")
def login_submit():
    configured = _require_password_configured()
    if configured:
        return configured
    supplied_csrf = request.form.get("csrf_token", "")
    if not hmac.compare_digest(supplied_csrf, session.get("dashboard_csrf", "")):
        return render_template(
            "dashboard_login.html",
            csrf_token=_csrf_token(),
            error="Sessiya muddati tugadi. Qayta urinib ko'ring.",
        ), 400
    supplied_password = request.form.get("password", "")
    if not hmac.compare_digest(supplied_password, DASHBOARD_PASSWORD):
        return render_template(
            "dashboard_login.html",
            csrf_token=_csrf_token(),
            error="Parol noto'g'ri. Qayta urinib ko'ring.",
        ), 401
    session.clear()
    session["dashboard_authenticated"] = True
    session["dashboard_csrf"] = secrets.token_urlsafe(32)
    return redirect(url_for("dashboard.home"))


@dashboard.post("/dashboard/logout")
@_require_login
def logout():
    supplied_csrf = request.form.get("csrf_token", "")
    if not hmac.compare_digest(supplied_csrf, session.get("dashboard_csrf", "")):
        return "Invalid CSRF token.", 400
    session.clear()
    return redirect(url_for("dashboard.login"))


@dashboard.get("/dashboard")
@_require_login
def home():
    return render_template(
        "dashboard.html",
        csrf_token=_csrf_token(),
        db_path=Path(chat_store.DATABASE_PATH).name,
    )


@dashboard.get("/dashboard/api/conversations")
@_require_login
def conversations():
    platform = request.args.get("platform", "all")
    if platform not in {"all", "Instagram", "Telegram"}:
        return jsonify(error="Invalid platform."), 400
    search = request.args.get("q", "").strip()[:100]
    return jsonify(
        conversations=chat_store.list_conversations(platform=platform, search=search),
        stats=chat_store.get_stats(),
    )


@dashboard.get("/dashboard/api/leads")
@_require_login
def leads():
    search = request.args.get("q", "").strip()[:100]
    return jsonify(
        leads=chat_store.list_leads(search=search),
        total=chat_store.get_stats()["leads"],
    )


@dashboard.get("/dashboard/api/settings/model")
@_require_login
def get_model_setting():
    return jsonify(
        models=CLAUDE_MODELS,
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"),
    )


@dashboard.post("/dashboard/api/settings/model")
@_require_login
def update_model_setting():
    supplied_csrf = request.headers.get("X-CSRF-Token", "")
    if not hmac.compare_digest(supplied_csrf, session.get("dashboard_csrf", "")):
        return jsonify(error="Sessiya tekshiruvi muvaffaqiyatsiz. Sahifani yangilang."), 400
    payload = request.get_json(silent=True)
    model = payload.get("model") if isinstance(payload, dict) else None
    if model not in CLAUDE_MODELS:
        return jsonify(error="Tanlangan Claude modeli qo'llab-quvvatlanmaydi."), 400

    try:
        updated, _, _ = set_key(str(PROJECT_ROOT / ".env"), "CLAUDE_MODEL", model)
        if not updated:
            raise OSError(".env fayliga CLAUDE_MODEL yozilmadi.")
    except (OSError, ValueError):
        current_app.logger.exception("Claude modelini .env fayliga saqlab bo'lmadi.")
        return jsonify(error="Model sozlamasini .env fayliga saqlab bo'lmadi."), 500

    os.environ["CLAUDE_MODEL"] = model
    return jsonify(ok=True, model=model)


@dashboard.post("/dashboard/api/conversations/<platform>/<path:external_id>/messages")
@_require_login
def send_manual_message(platform: str, external_id: str):
    if platform not in {"Instagram", "Telegram"}:
        return jsonify(error="Noma'lum kanal."), 400
    supplied_csrf = request.headers.get("X-CSRF-Token", "")
    if not hmac.compare_digest(supplied_csrf, session.get("dashboard_csrf", "")):
        return jsonify(error="Sessiya tekshiruvi muvaffaqiyatsiz. Sahifani yangilang."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        return jsonify(error="Xabar matni yuborilmadi."), 400
    text = payload["text"].strip()
    if not text:
        return jsonify(error="Bo'sh xabar yuborib bo'lmaydi."), 400
    if len(text) > 4096:
        return jsonify(error="Xabar 4096 belgidan oshmasligi kerak."), 400
    if not chat_store.list_messages(platform, external_id, limit=1):
        return jsonify(error="Suhbat topilmadi."), 404

    try:
        if platform == "Instagram":
            from ig.connect_to_ig import send_instagram_message

            send_instagram_message(external_id, text)
        else:
            from tg.connect_to_tg import send_message

            send_message(int(external_id), text)
    except (requests.RequestException, RuntimeError, ValueError):
        current_app.logger.exception("Dashboard'dan %s ga manual xabar yuborilmadi.", platform)
        return jsonify(error="Xabar yuborilmadi. Kanal ulanishi va ruxsatlarini tekshiring."), 502

    chat_store.record_message(
        platform=platform,
        external_id=external_id,
        display_name="PlutoSoft Admin",
        role="assistant",
        text=text,
    )
    return jsonify(ok=True)


@dashboard.get("/dashboard/api/avatar/<platform>/<path:external_id>")
@_require_login
def conversation_avatar(platform: str, external_id: str):
    try:
        profile = chat_store.get_profile(platform, external_id)
    except ValueError:
        return "Invalid platform.", 400
    if not profile:
        return "Avatar not found.", 404

    if platform == "Telegram" and profile.get("avatar_file_id"):
        from tg.connect_to_tg import telegram_api

        try:
            file_info = telegram_api("getFile", {"file_id": profile["avatar_file_id"]})
            file_path = file_info.get("file_path") if isinstance(file_info, dict) else None
            if (
                not isinstance(file_path, str)
                or not file_path.startswith("photos/")
                or ".." in file_path.split("/")
                or not all(character.isalnum() or character in "/._-" for character in file_path)
            ):
                return "Avatar not found.", 404
            from tg.connect_to_tg import TELEGRAM_API_URL, TELEGRAM_BOT_TOKEN

            response = requests.get(
                f"{TELEGRAM_API_URL}/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}",
                timeout=10,
            )
            response.raise_for_status()
        except (requests.RequestException, RuntimeError, ValueError):
            current_app.logger.warning(
                "Telegram profil rasmini yuklab bo'lmadi (user ID: %s).",
                external_id,
            )
            return "Avatar unavailable.", 502
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        if not content_type.startswith("image/"):
            return "Avatar unavailable.", 502
        return Response(
            response.content,
            content_type=content_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    if platform == "Instagram" and profile.get("profile_url"):
        from urllib.parse import urlparse

        image_url = profile["profile_url"]
        parsed = urlparse(image_url)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not (host.endswith(".cdninstagram.com") or host.endswith(".fbcdn.net"))
        ):
            current_app.logger.warning("Instagram profile image host rejected.")
            return "Avatar unavailable.", 502
        try:
            response = requests.get(image_url, timeout=10, allow_redirects=False)
            response.raise_for_status()
        except requests.RequestException:
            current_app.logger.warning(
                "Instagram profil rasmini yuklab bo'lmadi (user ID: %s).",
                external_id,
            )
            return "Avatar unavailable.", 502
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        if not content_type.startswith("image/"):
            return "Avatar unavailable.", 502
        return Response(
            response.content,
            content_type=content_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    return "Avatar not found.", 404


@dashboard.get("/dashboard/api/conversations/<platform>/<path:external_id>")
@_require_login
def conversation_messages(platform: str, external_id: str):
    try:
        messages = chat_store.list_messages(platform, external_id)
    except ValueError:
        return jsonify(error="Invalid platform."), 400
    return jsonify(messages=messages)
