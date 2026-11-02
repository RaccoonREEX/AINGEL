import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from care import sign_registry


class Command(BaseCommand):
    help = ("Records one person's review of one sign's current animation in care/data/sign_registry.json. Run it "
            "with the reviewer present, then commit the file through a reviewed change. Validation needs two "
            "approvals of the same animation, at least one by a Deaf signer (care.sign_registry).")

    def add_arguments(self, parser):
        default = Path(__file__).resolve().parents[4] / "web" / "src" / "components" / "aingel" / "signFingerprints.json"
        parser.add_argument("sign")
        parser.add_argument("--reviewer", required=True, help="Name or pseudonym the reviewer agreed to be credited with")
        parser.add_argument("--role", required=True, choices=sign_registry.ROLES)
        parser.add_argument("--region", required=True, help="Regional variant the review applies to, e.g. «Sierra (Quito)»")
        parser.add_argument("--decision", required=True, choices=sign_registry.DECISIONS)
        parser.add_argument("--notes", default=None)
        parser.add_argument("--date", default=date.today().isoformat())
        parser.add_argument("--fingerprints", default=str(default))

    def handle(self, *args, sign, reviewer, role, region, decision, notes, date, fingerprints, **options):
        prints = json.loads(Path(fingerprints).read_text(encoding="utf-8"))
        if sign not in prints:
            raise CommandError(f"{sign}: not an animated sign (run npm run export:android-hands first)")
        data = json.loads(sign_registry.REGISTRY.read_text(encoding="utf-8"))
        if sign not in data["signs"]:
            raise CommandError(f"{sign}: not in the registry (run manage.py sync_sign_registry first)")
        data["signs"][sign]["reviews"].append({
            "reviewer": reviewer.strip(), "role": role, "region": region.strip(), "decision": decision,
            "date": date, "fingerprint": prints[sign], "notes": notes.strip() if notes else None,
        })
        sign_registry.validate(data)
        sign_registry.REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        sign_registry.load.cache_clear()
        state, _, _ = sign_registry.status(data["signs"][sign])
        self.stdout.write(f"{sign}: {decision} by {role} recorded; status now «{state}»")
