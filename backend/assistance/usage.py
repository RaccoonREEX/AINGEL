"""Meta usage ledger and credit budget. Tokens and latency only: no content is stored or logged.

Prices are Meta's published list prices for muse-spark-1.3 (docs/META_MODELS.md), in USD per million tokens;
reasoning tokens are billed as output. The budget (AINGEL_META_BUDGET_USD) is a stop only when set: the ledger
starts empty, so calls made before it existed are not counted, and quality is never lowered to save credits.
"""

import os
from decimal import Decimal

from django.db.models import Count, Sum

PRICES = {"muse-spark-1.3": {"input": Decimal("1.25"), "cached": Decimal("0.15"), "output": Decimal("4.25")}}
MILLION = Decimal(1_000_000)


class BudgetExhausted(Exception):
    pass


def tokens(usage):
    """The four counters of a Responses API usage object, as non-negative integers."""
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}

    def number(value):
        return value if isinstance(value, int) and value > 0 else 0

    return {
        "input_tokens": number(usage.get("input_tokens")),
        "cached_tokens": number(details.get("cached_tokens")),
        "output_tokens": number(usage.get("output_tokens")),
        "reasoning_tokens": number(output_details.get("reasoning_tokens")),
    }


def cost(model, counts):
    price = PRICES.get(model)
    if price is None:
        return Decimal(0)
    fresh = max(counts["input_tokens"] - counts["cached_tokens"], 0)
    total = fresh * price["input"] + counts["cached_tokens"] * price["cached"] + counts["output_tokens"] * price["output"]
    return (total / MILLION).quantize(Decimal("0.000001"))


def record(feature, model, effort, usage, latency_ms=None, basis="", status="", user=None):
    """Store one call's usage; returns its counters and cost. Never raises: losing a ledger row must not lose the
    answer the person is waiting for."""
    from .models import MetaUsage

    counts = tokens(usage)
    price = cost(model, counts)
    try:
        MetaUsage.objects.create(
            feature=feature, model=model, effort=effort or "", basis=basis or "", status=status or "",
            latency_ms=latency_ms, cost_usd=price, user=user if getattr(user, "is_authenticated", False) else None,
            **counts,
        )
    except Exception:
        pass
    return {**counts, "cost_usd": float(price)}


def budget():
    value = os.environ.get("AINGEL_META_BUDGET_USD", "").strip()
    try:
        return Decimal(value) if value else None
    except ArithmeticError:
        return None


def spent():
    from .models import MetaUsage

    return MetaUsage.objects.aggregate(total=Sum("cost_usd"))["total"] or Decimal(0)


def admit():
    """Raises BudgetExhausted when a budget is set and the recorded spending reached it."""
    limit = budget()
    if limit is not None and spent() >= limit:
        raise BudgetExhausted("meta_budget_exhausted")


def summary():
    from .models import MetaUsage

    rows = MetaUsage.objects.values("feature").annotate(
        calls=Count("id"), input=Sum("input_tokens"), output=Sum("output_tokens"), reasoning=Sum("reasoning_tokens"),
        cost=Sum("cost_usd"),
    )
    limit = budget()
    total = spent()
    return {
        "budget_usd": float(limit) if limit is not None else None,
        "spent_usd": float(total),
        "remaining_usd": float(limit - total) if limit is not None else None,
        "features": [{**row, "cost": float(row["cost"] or 0)} for row in rows.order_by("feature")],
    }
