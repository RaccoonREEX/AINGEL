import json

from django.core.management.base import BaseCommand

from assistance.usage import summary


class Command(BaseCommand):
    help = "Meta tokens and estimated cost per feature, and the remaining budget (AINGEL_META_BUDGET_USD). No content."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(summary(), indent=2, default=str))
