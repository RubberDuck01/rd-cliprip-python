from datetime import datetime


def format_dt_short(value: str) -> str:
    """Convert an ISO date string to 'DD/MM/YYYY HH:mm'.

    Seconds are dropped. If the value can't be parsed it is returned unchanged
    (so callers can show '' for missing dates instead).
    """
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return value
    return dt.strftime("%d/%m/%Y %H:%M")
