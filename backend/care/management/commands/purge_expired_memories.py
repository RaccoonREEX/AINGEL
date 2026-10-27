from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from care.models import FamilyFace, Memory, MFADevice


class Command(BaseCommand):
    help = "Permanently purge expired memories and their private evidence. Configure daily execution before production."

    def handle(self, *args, **options):
        count = 0
        root = settings.PRIVATE_MEDIA_ROOT.resolve()
        for memory in Memory.objects.filter(expires_at__lte=timezone.now()).iterator():
            if memory.evidence_path:
                path = (root / memory.evidence_path).resolve()
                if path.parent != root:
                    raise CommandError("Unsafe evidence path; purge stopped.")
                path.unlink(missing_ok=True)
            memory.delete()
            count += 1
        faces, _ = FamilyFace.objects.filter(expires_at__lte=timezone.now()).delete()
        from datetime import timedelta

        pending = MFADevice.objects.filter(
            pending_at__lt=timezone.now() - timedelta(minutes=10)
        ).update(pending_encrypted="", pending_at=None)
        self.stdout.write(
            f"Purged {count} expired memories, {faces} expired facial templates; cleared {pending} expired MFA setups."
        )
