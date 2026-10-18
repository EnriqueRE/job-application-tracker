from datetime import date


def get_today() -> date:
    """Dependency for "today", so tests can pin the date the request sees."""
    return date.today()
