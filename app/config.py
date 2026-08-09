"""
Central config, all overridable via environment variables so you don't
have to edit code to change thresholds per-deployment.
"""

import os

# Auto-decision thresholds for fraud_score (0-100):
#   score <  APPROVE_BELOW              -> "approved"
#   APPROVE_BELOW <= score < REJECT_ABOVE -> "needs_review"
#   score >= REJECT_ABOVE                -> "rejected"
#
# Set your own via env vars, e.g.:
#   APPROVE_BELOW_THRESHOLD=15 REJECT_ABOVE_THRESHOLD=70 uvicorn app.main:app
APPROVE_BELOW = float(os.getenv("APPROVE_BELOW_THRESHOLD", "20"))
REJECT_ABOVE = float(os.getenv("REJECT_ABOVE_THRESHOLD", "60"))

# Optional: a Slack Incoming Webhook URL. If set, submissions that aren't
# auto-approved will also be posted there. If unset, notifications just
# go to the server console/log.
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
DB_PATH = os.getenv("DB_PATH", "submissions.db")
