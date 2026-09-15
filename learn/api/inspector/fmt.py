"""Exact number formatting. Integers are converted to decimal strings digit by digit, never through floats,
so a 27-decimal ray value is shown exactly as stored."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, localcontext

RAY_DECIMALS = 27
SECONDS_PER_YEAR = 365 * 24 * 60 * 60  # Aave MathUtils.SECONDS_PER_YEAR


def fixed(value: int, decimals: int) -> str:
    """value / 10**decimals as an exact decimal string."""
    sign = "-" if value < 0 else ""
    digits = str(abs(value))
    if decimals == 0:
        return sign + digits
    digits = digits.rjust(decimals + 1, "0")
    return f"{sign}{digits[:-decimals]}.{digits[-decimals:]}"


def grouped(n: int) -> str:
    return f"{n:,}"


def iso_utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ray_index(raw: int) -> dict:
    return {"raw": str(raw), "unit": "ray (27 implied decimals)", "value": fixed(raw, RAY_DECIMALS)}


def ray_rate(raw: int) -> dict:
    """A per-year rate stored in ray: raw integer -> fraction (/1e27) -> percent APR (/1e25).

    APY is NOT stored anywhere. It is derived here the way UIs do it (per-second compounding) and labelled so.
    """
    with localcontext() as ctx:
        ctx.prec = 80
        apr = Decimal(raw) / Decimal(10) ** RAY_DECIMALS
        apy = (Decimal(1) + apr / SECONDS_PER_YEAR) ** SECONDS_PER_YEAR - 1
        apy_percent = f"{(apy * 100):.6f}"
    return {
        "raw": str(raw),
        "unit": "ray (27 implied decimals) per year",
        "fraction": fixed(raw, RAY_DECIMALS),
        "percent_apr": fixed(raw, RAY_DECIMALS - 2),
        "percent_apy_derived": apy_percent,
        "apy_formula": f"(1 + APR / {SECONDS_PER_YEAR})^{SECONDS_PER_YEAR} - 1",
    }
