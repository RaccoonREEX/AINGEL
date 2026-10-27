import json
from pathlib import Path
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from care.models import Membership, Message, Profile, Routine


class Command(BaseCommand):
    help = "Create synthetic local test accounts. Passwords go only in ignored .local/demo-accounts.json."

    def handle(self, *args, **options):
        output = settings.BASE_DIR.parent / ".local" / "demo-accounts.json"
        if output.exists():
            self.stdout.write(
                "Demo credentials already exist in ignored .local/demo-accounts.json; no accounts changed."
            )
            return
        names = ["aingel.demo", "familia.demo", "externo.demo"]
        if get_user_model().objects.filter(username__in=names).exists():
            raise CommandError(
                "Demo accounts already exist without their credential file; refusing to reset passwords."
            )
        accounts = [
            {"username": name, "password": secrets.token_urlsafe(18)} for name in names
        ]
        with transaction.atomic():
            users = [
                get_user_model().objects.create_user(**account) for account in accounts
            ]
            profile = Profile.objects.create(
                owner=users[0],
                display_name="Persona de prueba",
                support_notes="Datos sintéticos de demostración. Prefiero instrucciones cortas.",
                preferences={
                    "memory_assistance": True,
                    "visual_assistance": True,
                    "simple_instructions": True,
                },
            )
            Membership.objects.create(
                profile=profile,
                user=users[1],
                relationship="Familiar de prueba",
                can_configure=True,
                can_view_memories=False,
            )
            for category, title, at, instructions in [
                (
                    "sleep",
                    "Prepararme para dormir",
                    "22:00",
                    "Rutina sintética de prueba.",
                ),
                (
                    "bathroom",
                    "Recordatorio personal de baño",
                    "09:00",
                    "Preferencia de ejemplo; ajustar con la persona.",
                ),
                (
                    "meal",
                    "Desayuno",
                    "08:00",
                    "Ejemplo de horario, no prueba de que haya comido.",
                ),
                (
                    "medicine",
                    "Tratamiento — ejemplo sin medicamento",
                    "12:00",
                    "Completar solo con indicaciones ya verificadas. No representa una prescripción.",
                ),
            ]:
                Routine.objects.create(
                    profile=profile,
                    category=category,
                    title=title,
                    at=at,
                    weekdays=list(range(7)),
                    instructions=instructions,
                    created_by=users[1],
                )
            Message.objects.create(
                profile=profile,
                author=users[1],
                body="Mensaje sintético: pasaré a visitarte a las cinco.",
                locale="es-EC",
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps({"synthetic": True, "accounts": accounts}, indent=2) + "\n",
                encoding="utf-8",
            )
        self.stdout.write(
            "Created 3 synthetic accounts and 1 linked caregiver. Credentials: .local/demo-accounts.json (ignored)."
        )
