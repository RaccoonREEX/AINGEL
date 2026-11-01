from django.conf import settings
from django.db import models


class MetaUsage(models.Model):
    """One Meta call's token usage and latency, to follow the credit budget (assistance.usage). Never holds the
    request, the image, the answer or anything else the person sent or received."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    feature = models.CharField(max_length=32)
    model = models.CharField(max_length=40)
    effort = models.CharField(max_length=12, blank=True)
    basis = models.CharField(max_length=24, blank=True)
    status = models.CharField(max_length=16, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    cached_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    reasoning_tokens = models.PositiveIntegerField(default=0)
    # Units Meta bills outside tokens (dev.meta.ai pricing): SAM images, Voice seconds of audio, web searches.
    images = models.PositiveIntegerField(default=0)
    audio_seconds = models.PositiveIntegerField(default=0)
    web_searches = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
