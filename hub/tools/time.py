from datetime import datetime

def get_current_datetime() -> str:
    """
    Returns the current date and time in YYYY-MM-DD HH:MM:SS format.
    Useful for determining 'today', 'tomorrow', or checking if a task is overdue.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
