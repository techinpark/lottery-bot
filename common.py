import datetime
from datetime import timedelta

def get_search_date_range() -> dict:
    today = datetime.datetime.today()
    today_str = today.strftime("%Y%m%d")
    weekago = today - timedelta(days=7)
    weekago_str = weekago.strftime("%Y%m%d")
    return {
        "searchStartDate": weekago_str,
        "searchEndDate": today_str
    }

SLOTS = ["A", "B", "C", "D", "E"]
