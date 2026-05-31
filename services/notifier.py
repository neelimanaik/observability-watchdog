import logging
import httpx
from models.alert import Alert
from config import settings

logger = logging.getLogger("watchdog.notifier")


def dispatch(alert: Alert) -> None:
    logger.warning(
        "[ALERT][%s][%s] %s — %s",
        alert.severity.upper(),
        alert.rule,
        alert.source,
        alert.message,
    )
    if settings.alert_webhook_url:
        try:
            payload = {
                "text": f"*[{alert.severity.upper()}]* `{alert.rule}` on `{alert.source}`\n{alert.message}",
            }
            httpx.post(settings.alert_webhook_url, json=payload, timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.error("Webhook dispatch failed: %s", exc)
