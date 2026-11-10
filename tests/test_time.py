"""Проверка BR-03."""
from datetime import date, timedelta

from app.core.time import earliest_pickup_date, is_pickup_date_valid

def test_earliest_is_plus_two_days():
    today = earliest_pickup_date()
    assert is_pickup_date_valid(today)
    assert is_pickup_date_valid(today + timedelta(days=1))
    assert not is_pickup_date_valid(today - timedelta(days=1))
