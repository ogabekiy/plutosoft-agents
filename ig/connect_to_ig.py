"""Instagram OAuth and DM webhook server for the PlutoSoft assistant.



Run from the project root:

    python ig/connect_to_ig.py



Configure /instagram/callback as the Instagram Login redirect and
/instagram/webhook as the Meta webhook callback.

"""

import os

import secrets

import hashlib

import hmac

import logging

import sys
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

from pathlib import Path



import requests

from dotenv import load_dotenv, set_key

from flask import Flask, redirect, request, session, jsonify
from cl import chat_store



PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)



IG_APP_ID = os.environ["IG_APP_ID"]
IG_APP_SECRET = os.environ["IG_APP_SECRET"]
IG_REDIRECT_URI = os.environ["IG_REDIRECT_URI"]
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_WEBHOOK_VERIFY_TOKEN = os.getenv("IG_WEBHOOK_VERIFY_TOKEN", "")
GRAPH_API_VERSION = "v25.0"
GRAPH_API_URL = f"https://graph.instagram.com/{GRAPH_API_VERSION}"

SCOPES = ",".join([
    "instagram_business_basic",
    "instagram_business_manage_messages",
    "instagram_business_manage_comments",
])
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

message_executor = ThreadPoolExecutor(max_workers=4)



app = Flask(__name__)

app.secret_key = os.getenv("DASHBOARD_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

from ig.dashboard import dashboard

app.register_blueprint(dashboard)





@app.get("/")
def index():
    return (
        '<a href="/instagram/connect"><button>Instagram bilan davom etish</button></a> '
        '<a href="/dashboard">Inbox dashboard</a>'
    )


@app.get("/instagram/webhook")
def verify_webhook():
    if not IG_WEBHOOK_VERIFY_TOKEN:
        logger.error("IG_WEBHOOK_VERIFY_TOKEN is not configured.")
        return "Webhook verify token is not configured", 500

    if (
        request.args.get("hub.mode") == "subscribe"
        and hmac.compare_digest(
            request.args.get("hub.verify_token", ""),
            IG_WEBHOOK_VERIFY_TOKEN,
        )
    ):
        return request.args.get("hub.challenge", ""), 200

    return "Webhook verification failed", 403






@app.get("/instagram/connect")

def connect():

    state = secrets.token_urlsafe(16)

    session["ig_state"] = state  # CSRF himoyasi

    params = {

        "client_id": IG_APP_ID,

        "redirect_uri": IG_REDIRECT_URI,

        "response_type": "code",

        "scope": SCOPES,

        "state": state,

    }

    req = requests.Request(

        "GET", "https://www.instagram.com/oauth/authorize", params=params

    ).prepare()

    return redirect(req.url)





@app.get("/instagram/callback")

def callback():

    global IG_ACCESS_TOKEN, IG_USER_ID



    if request.args.get("error"):

        return jsonify(error=request.args.get("error"),

                       reason=request.args.get("error_description")), 400



    if request.args.get("state") != session.get("ig_state"):

        return "Noto'g'ri state", 400



    code = request.args["code"]



    # 1) code -> qisqa muddatli token

    short = requests.post(

        "https://api.instagram.com/oauth/access_token",

        data={

            "client_id": IG_APP_ID,

            "client_secret": IG_APP_SECRET,

            "grant_type": "authorization_code",

            "redirect_uri": IG_REDIRECT_URI,

            "code": code,

        },

        timeout=15,

    ).json()

    if "access_token" not in short:

        return jsonify(step="short_token", response=short), 400



    # 2) qisqa -> uzoq muddatli token (60 kun)

    long_ = requests.get(

        "https://graph.instagram.com/access_token",

        params={

            "grant_type": "ig_exchange_token",

            "client_secret": IG_APP_SECRET,

            "access_token": short["access_token"],

        },

        timeout=15,

    ).json()

    if "access_token" not in long_:

        return jsonify(step="long_token", response=long_), 400



    # 3) profil

    profile = requests.get(

        f"{GRAPH_API_URL}/me",

        params={

            "fields": "user_id,username,profile_picture_url",

            "access_token": long_["access_token"],

        },

        timeout=15,

    ).json()

    account_id = profile.get("user_id") or profile.get("id")

    if not account_id:

        return jsonify(step="profile", response=profile), 400



    IG_ACCESS_TOKEN = long_["access_token"]

    IG_USER_ID = str(account_id)
    set_key(str(ENV_FILE), "IG_ACCESS_TOKEN", IG_ACCESS_TOKEN)
    set_key(str(ENV_FILE), "IG_USER_ID", IG_USER_ID)

    subscription = subscribe_account_to_webhooks()

    return jsonify(
        profile=profile,
        expires_in_days=long_.get("expires_in", 0) // 86400,
        webhook_subscription=subscription,
    )





def subscribe_account_to_webhooks():

    """Enable message events for this Instagram account."""
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        raise RuntimeError("Instagram OAuth is not connected; visit /instagram/connect.")

    response = requests.post(

        f"{GRAPH_API_URL}/{IG_USER_ID}/subscribed_apps",

        params={"subscribed_fields": "messages"},

        headers={"Authorization": f"Bearer {IG_ACCESS_TOKEN}"},

        timeout=15,

    )

    response.raise_for_status()

    result = response.json()

    if not result.get("success"):

        raise RuntimeError(f"Instagram webhook subscription failed: {result}")

    logger.info("Instagram message webhook subscription enabled.")

    return result





def ensure_account_subscription():

    """Subscribe the saved Instagram account to message webhooks."""

    global IG_USER_ID



    if not IG_ACCESS_TOKEN:
        logger.warning("Instagram is not connected; visit /instagram/connect to authorize it.")
        return



    try:

        if not IG_USER_ID:
            response = requests.get(
                f"{GRAPH_API_URL}/me",
                params={"fields": "user_id", "access_token": IG_ACCESS_TOKEN},
                timeout=15,
            )
            response.raise_for_status()
            profile = response.json()
            IG_USER_ID = str(profile.get("user_id") or profile.get("id") or "")
            if not IG_USER_ID:
                raise RuntimeError("Instagram /me response did not include an account ID.")
            set_key(str(ENV_FILE), "IG_USER_ID", IG_USER_ID)

        subscribe_account_to_webhooks()
    except (requests.RequestException, RuntimeError, ValueError) as error:
        logger.error("Instagram webhook subscription could not be enabled: %s", error)



def verify_webhook_signature(raw_body: bytes) -> bool:

    signature = request.headers.get("X-Hub-Signature-256", "")

    if not signature.startswith("sha256="):

        return False



    expected = hmac.new(

        IG_APP_SECRET.encode("utf-8"),

        raw_body,

        hashlib.sha256,

    ).hexdigest()

    return hmac.compare_digest(signature.removeprefix("sha256="), expected)





def split_message(text: str, max_bytes: int = 1000) -> list[str]:

    """Split a reply at UTF-8 character boundaries to meet Instagram's text limit."""

    parts = []

    text = text.strip()

    while text:

        byte_count = 0

        end = 0

        for index, char in enumerate(text):

            char_bytes = len(char.encode("utf-8"))

            if byte_count + char_bytes > max_bytes:

                break

            byte_count += char_bytes

            end = index + 1



        if end == len(text):

            parts.append(text)

            break



        split_at = text.rfind(" ", 0, end)

        if split_at <= 0:

            split_at = end

        parts.append(text[:split_at].strip())

        text = text[split_at:].strip()



    return parts





def send_instagram_message(recipient_id: str, text: str) -> None:
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        raise RuntimeError("Instagram OAuth is not connected; visit /instagram/connect.")
    for part in split_message(text):
        response = requests.post(
            f"{GRAPH_API_URL}/{IG_USER_ID}/messages",
            headers={"Authorization": f"Bearer {IG_ACCESS_TOKEN}"},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": part},

            },

            timeout=20,

        )

        response.raise_for_status()


def handle_incoming_message(
    recipient_id: str,
    text: str,
    message_key: str | None = None,
) -> None:

    if str(PROJECT_ROOT) not in sys.path:

        sys.path.insert(0, str(PROJECT_ROOT))

    cached_profile = chat_store.get_profile("Instagram", recipient_id)
    profile_name = (
        cached_profile["display_name"]
        if cached_profile
        else f"Instagram user {recipient_id}"
    )
    username = cached_profile.get("username") if cached_profile else None
    profile_url = cached_profile.get("profile_url") if cached_profile else None
    profile_is_stale = (
        cached_profile is None
        or datetime.now(timezone.utc)
        - datetime.fromisoformat(cached_profile["updated_at"])
        > timedelta(days=3)
    )
    profile_lookup_succeeded = False
    if IG_ACCESS_TOKEN and profile_is_stale:
        try:
            profile_response = requests.get(
                f"{GRAPH_API_URL}/{recipient_id}",
                params={
                    "fields": "name,username,profile_pic",
                },
                headers={"Authorization": f"Bearer {IG_ACCESS_TOKEN}"},
                timeout=10,
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
            if isinstance(profile, dict) and any(
                field in profile for field in ("name", "username", "profile_pic")
            ):
                profile_lookup_succeeded = True
                username = profile.get("username") or username
                profile_name = (
                    profile.get("name")
                    or (f"@{username}" if username else None)
                    or profile_name
                )
                profile_url = profile.get("profile_pic") or profile_url
        except (requests.RequestException, ValueError):
            logger.warning(
                "Instagram profile details were unavailable for user %s.",
                recipient_id,
                exc_info=True,
            )
    if cached_profile is None or profile_lookup_succeeded:
        chat_store.update_profile(
            platform="Instagram",
            external_id=recipient_id,
            display_name=profile_name,
            username=username if isinstance(username, str) else None,
            profile_url=profile_url if isinstance(profile_url, str) else None,
        )

    chat_store.record_message(
        platform="Instagram",
        external_id=recipient_id,
        display_name=profile_name,
        role="customer",
        text=text,
        message_key=message_key,
    )

    from cl.send_leads import LEAD_PROMPT, handle_lead_message

    handled, started, lead_reply = handle_lead_message(
        "Instagram",
        recipient_id,
        text,
    )
    if handled:
        if lead_reply:
            send_instagram_message(recipient_id, lead_reply)
            chat_store.record_message(
                platform="Instagram",
                external_id=recipient_id,
                display_name="PlutoSoft AI",
                role="assistant",
                text=lead_reply,
            )
        return

    from chat_with_claude import generate_answer

    answer = generate_answer(text)
    reply_parts = [part for part in (answer, LEAD_PROMPT if started else "") if part]
    if reply_parts:
        reply = "\n\n".join(reply_parts)
        send_instagram_message(recipient_id, reply)
        chat_store.record_message(
            platform="Instagram",
            external_id=recipient_id,
            display_name="PlutoSoft AI",
            role="assistant",
            text=reply,
        )





def log_message_task_error(future) -> None:

    error = future.exception()

    if error is not None:

        logger.error(

            "Could not generate or send an Instagram DM reply.",

            exc_info=(type(error), error, error.__traceback__),

        )





@app.post("/instagram/webhook")
def receive_instagram_webhook():

    logger.info("Instagram webhook POST received.")
    raw_body = request.get_data(cache=True)

    if not verify_webhook_signature(raw_body):
        logger.warning("Instagram webhook rejected: invalid X-Hub-Signature-256.")
        return "Invalid webhook signature", 401


    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        logger.warning("Instagram webhook rejected: request body is not a JSON object.")
        return "Invalid JSON payload", 400

    if payload.get("object") != "instagram":
        logger.warning("Instagram webhook ignored: unexpected object type.")
        return "Unsupported webhook object", 404


    accepted_messages = 0
    for entry in payload.get("entry", []):
        if IG_USER_ID and str(entry.get("id", "")) != IG_USER_ID:
            logger.warning("Instagram webhook entry ignored: account ID does not match IG_USER_ID.")
            continue
        for event in entry.get("messaging", []):

            message = event.get("message", {})

            sender_id = event.get("sender", {}).get("id")

            text = message.get("text")
            message_key = message.get("mid")



            if (
                sender_id
                and text
                and not message.get("is_echo")
                and str(sender_id) != IG_USER_ID

            ):
                logger.info("Instagram DM from %s: %s", sender_id, text)
                accepted_messages += 1

                future = message_executor.submit(

                    handle_incoming_message,

                    str(sender_id),

                    text,
                    f"{sender_id}:{message_key}" if message_key else None,

                )

                future.add_done_callback(log_message_task_error)
    if accepted_messages == 0:
        logger.info(
            "Instagram webhook contained no new text DMs for this account. "
            "Check Meta's messages field subscription and webhook payload."
        )

    return "EVENT_RECEIVED", 200





if __name__ == "__main__":

    ensure_account_subscription()

    app.run(port=5000, debug=False)