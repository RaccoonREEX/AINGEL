import json

from django.core.management.base import BaseCommand

from care.models import SignFeedback


class Command(BaseCommand):
    help = "Sign corrections for the reviewers, as JSON lines: sign, animation, verdict, role, region, comment, date. No account data."

    def add_arguments(self, parser):
        parser.add_argument("--sign", default=None)

    def handle(self, *args, sign, **options):
        rows = SignFeedback.objects.order_by("sign", "created_at")
        if sign:
            rows = rows.filter(sign=sign)
        for row in rows:
            self.stdout.write(json.dumps({
                "sign": row.sign, "language": row.language, "fingerprint": row.fingerprint, "verdict": row.verdict,
                "role": row.role, "region": row.region, "comment": row.comment, "date": row.created_at.date().isoformat(),
            }, ensure_ascii=False))
