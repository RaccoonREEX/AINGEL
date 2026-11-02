"""Meta usage ledger and credit budget. Billed units and latency only: no content is stored or logged.

Prices are Meta's Standard pay-as-you-go list prices (dev.meta.ai/docs/pricing-rate-limits, checked 2026-10-31):
- muse-spark-1.3: per million tokens (input, cached input, output; reasoning tokens are billed as output), plus
  web search grounding per 1,000 queries;
- sam-3.1: per image segmented (AINGEL sends one image per request);
- muse-voice-transcribe-1.0: per hour of audio processed, in whole seconds rounded down.

This is AINGEL's own estimate, not Meta's invoice. It counts what a response reports (tokens, web searches) and what
AINGEL itself sent (images, seconds of audio forwarded). A request that fails before Meta returns a response (network
error, timeout) cannot be counted, so the limits below are partial protection; Meta's billing console is the
authority. The budget (AINGEL_META_BUDGET_USD) is a stop only when set: the ledger starts empty, so calls made before
it existed are not counted, and quality is never lowered to save credits.
"""

import os
from decimal import Decimal

from django.db.models import Count, Sum

PRICES = {"muse-spark-1.3": {"input": Decimal("1.25"), "cached": Decimal("0.15"), "output": Decimal("4.25")}}
WEB_SEARCH = Decimal("2.50") / 1000  # per query, on top of the request's tokens
SAM_IMAGE = Decimal("2.50") / 1000  # sam-3.1, per image segmented
VOICE_SECOND = Decimal("0.18") / 3600  # muse-voice-transcribe-1.0, per second of audio processed
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


def cost(model, counts, images=0, audio_seconds=0, web_searches=0):
    """USD for one call: tokens for Spark (plus its web searches), images for SAM, seconds of audio for Voice. A model
    without a known price costs 0 here; test_meta_modality keeps the models in use to the priced ones."""
    total = Decimal(0)
    if price := PRICES.get(model):
        fresh = max(counts["input_tokens"] - counts["cached_tokens"], 0)
        billed = fresh * price["input"] + counts["cached_tokens"] * price["cached"] + counts["output_tokens"] * price["output"]
        total = billed / MILLION + web_searches * WEB_SEARCH
    elif model == "sam-3.1":
        total = images * SAM_IMAGE
    elif model == "muse-voice-transcribe-1.0":
        total = audio_seconds * VOICE_SECOND
    return total.quantize(Decimal("0.000001"))


def billed_account(user=None):
    """The account a Meta call is billed to: [user] when the server passes the authenticated request user, otherwise
    the account bound for this request by care.consent.meta_account_denial from request.user. Never an ID sent by the
    client."""
    from .meta_quota import bound_account

    return user.pk if getattr(user, "is_authenticated", False) else bound_account()


def record(feature, model, effort, usage, latency_ms=None, basis="", status="", user=None, images=0, audio_seconds=0,
           web_searches=0):
    """Store one call's billed units for its account (billed_account); returns its counters and cost. Never raises:
    losing a ledger row must not lose the answer the person is waiting for."""
    from .models import MetaUsage

    counts = tokens(usage)
    units = {"images": max(int(images), 0), "audio_seconds": max(int(audio_seconds), 0),
             "web_searches": max(int(web_searches), 0)}
    price = cost(model, counts, **units)
    try:
        MetaUsage.objects.create(
            feature=feature, model=model, effort=effort or "", basis=basis or "", status=status or "",
            latency_ms=latency_ms, cost_usd=price, user_id=billed_account(user), **counts, **units,
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


def account_budget():
    value = os.environ.get("AINGEL_META_USER_DAILY_USD", "").strip()
    try:
        return Decimal(value) if value else None
    except ArithmeticError:
        return None


def admit(account=None):
    """Raises BudgetExhausted when the platform's budget is reached, or, when AINGEL_META_USER_DAILY_USD is set,
    [account] (by default the request's bound account) spent that much today (UTC): one account cannot use up the
    credits everyone shares. Partial protection: see the module docstring."""
    from django.utils import timezone

    from .meta_quota import bound_account
    from .models import MetaUsage

    limit = budget()
    if limit is not None and spent() >= limit:
        raise BudgetExhausted("meta_budget_exhausted")
    daily, account = account_budget(), account if account is not None else bound_account()
    if daily is not None and account is not None:
        since = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today = MetaUsage.objects.filter(user_id=account, created_at__gte=since).aggregate(total=Sum("cost_usd"))["total"] or Decimal(0)
        if today >= daily:
            raise BudgetExhausted("meta_account_budget_exhausted")


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
