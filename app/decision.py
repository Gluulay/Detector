from . import config


def decide_status(fraud_score: float) -> str:
    """
    Turns a fraud_score into one of three outcomes using the thresholds
    in config.py. 'needs_review' is deliberately the default middle
    ground — anything not confidently genuine or confidently fake gets
    a human to look at it rather than an automatic call either way.
    """
    if fraud_score < config.APPROVE_BELOW:
        return "approved"
    if fraud_score >= config.REJECT_ABOVE:
        return "rejected"
    return "needs_review"
