"""BR-02: расчёт цены с Decimal и ROUND_HALF_UP."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

TWOPLACES = Decimal("0.01")

def round_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def unit_price(weight_g: int, base_price_per_kg: Decimal, surcharge_per_kg: Decimal) -> Decimal:
    """ROUND_HALF_UP(вес_г / 1000 × (база + доплата), 2)."""
    per_kg = Decimal(base_price_per_kg) + Decimal(surcharge_per_kg)
    raw = (Decimal(weight_g) / Decimal(1000)) * per_kg
    return round_money(raw)

def line_total(unit: Decimal, quantity: int) -> Decimal:
    return round_money(Decimal(unit) * Decimal(quantity))

def money_str(value: Decimal) -> str:
    return f"{round_money(Decimal(value)):.2f}"
