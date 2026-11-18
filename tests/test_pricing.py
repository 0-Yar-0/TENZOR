"""Unit-тесты BR-02."""
from decimal import Decimal

from app.services.pricing import line_total, round_money, unit_price

def test_round_half_up():
    assert round_money(Decimal("1.005")) == Decimal("1.01")
    assert round_money(Decimal("1.004")) == Decimal("1.00")

def test_unit_price_example():
    # 1500 г × (1200 + 200) руб./кг = 2100.00
    assert unit_price(1500, Decimal("1200.00"), Decimal("200.00")) == Decimal("2100.00")

def test_line_total_example():
    up = unit_price(1500, Decimal("1200.00"), Decimal("200.00"))
    assert line_total(up, 2) == Decimal("4200.00")

def test_rounding_100g():
    # 100 г × 10.05 / 1000 = 1.005 → 1.01; ×3 → 3.03
    up = unit_price(100, Decimal("10.05"), Decimal("0.00"))
    assert up == Decimal("1.01")
    assert line_total(up, 3) == Decimal("3.03")
