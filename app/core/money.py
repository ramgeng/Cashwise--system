from datetime import date


def inr(x) -> str:
    """Rupees in Indian style for text the LLM reads: 'Rs 1.94 L' for lakhs, 'Rs 45,000' below."""
    if x is None:
        return "n/a"
    sign = "-" if x < 0 else ""
    x = abs(x)
    return f"{sign}Rs {x / 100000:.2f} L" if x >= 100000 else f"{sign}Rs {x:,.0f}"


def as_date(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])
