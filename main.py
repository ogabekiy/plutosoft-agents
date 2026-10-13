"""Start the Instagram webhook server and Telegram bot together."""

import logging
import threading
import time
from collections.abc import Callable

from ig import connect_to_ig
from tg import connect_to_tg


logger = logging.getLogger(__name__)


def run_instagram() -> None:
    connect_to_ig.ensure_account_subscription()
    connect_to_ig.app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
    )


def run_service(name: str, target: Callable[[], None], errors: list[Exception]) -> None:
    try:
        target()
    except Exception as error:
        errors.append(error)
        logger.exception("%s xizmati to'xtadi.", name)


def main() -> None:
    errors: list[Exception] = []
    services = (
        ("Instagram", run_instagram),
        ("Telegram", connect_to_tg.main),
    )
    threads = [
        threading.Thread(
            target=run_service,
            args=(name, target, errors),
            name=f"{name.lower()}-service",
            daemon=True,
        )
        for name, target in services
    ]

    for thread in threads:
        thread.start()

    logger.info("Instagram va Telegram xizmatlari ishga tushirildi.")
    try:
        while any(thread.is_alive() for thread in threads):
            if errors:
                raise RuntimeError("Xizmatlardan biri ishga tushmadi yoki to'xtadi.") from errors[0]
            time.sleep(0.5)
        raise RuntimeError("Instagram yoki Telegram xizmati kutilmaganda to'xtadi.")
    except KeyboardInterrupt:
        logger.info("Xizmatlar to'xtatilmoqda.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
