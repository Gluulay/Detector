"""
Fires whenever a submission isn't auto-approved. Always logs to the
console (visible in your server logs / hosting platform's log viewer),
and additionally posts to Slack if SLACK_WEBHOOK_URL is set in config.

To wire this up to email, SMS, or an internal admin dashboard instead,
this is the one function to edit — nothing else in the app needs to
change.
"""

import json
import urllib.request

from . import config


def notify_admin(submission: dict) -> None:
    message = (
        f"[Receipt needs review] id={submission['id']} "
        f"reference={submission.get('reference_id')} "
        f"status={submission['status']} "
        f"fraud_score={submission['fraud_score']}"
    )
    print(message)

    if config.SLACK_WEBHOOK_URL:
        try:
            payload = json.dumps({"text": message}).encode("utf-8")
            req = urllib.request.Request(
                config.SLACK_WEBHOOK_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as exc:  # noqa: BLE001 - never let a notification failure break the request
            print(f"Slack notification failed: {exc}")
