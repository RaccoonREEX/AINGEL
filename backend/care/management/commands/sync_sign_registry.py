import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from care import sign_registry

SOURCE = "Diseño propio de AINGEL (AINGEL_Manos_y_Senas v1.0.0, catálogo de señas v1.5.0)"
LICENSE = "Obra propia de AINGEL; sin validación lingüística"


class Command(BaseCommand):
    help = ("Adds every sign of the animation fingerprints file (npm run export:android-hands) to the registry as "
            "«pending», keeping existing entries and reviews. Never marks anything as validated.")

    def add_arguments(self, parser):
        default = Path(__file__).resolve().parents[4] / "web" / "src" / "components" / "aingel" / "signFingerprints.json"
        parser.add_argument("--fingerprints", default=str(default))

    def handle(self, *args, fingerprints, **options):
        try:
            prints = json.loads(Path(fingerprints).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CommandError(f"fingerprints: {error}") from None
        path = sign_registry.REGISTRY
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "version": 1, "language": "lsec", "grammar_rules": [], "signs": {},
        }
        added = 0
        for sign_id in sorted(prints):
            if sign_id not in data["signs"]:
                data["signs"][sign_id] = {
                    "kind": sign_registry.kind_of(sign_id), "source": SOURCE, "license": LICENSE, "region": None,
                    "non_manual": None, "reviews": [],
                }
                added += 1
        missing = sorted(set(data["signs"]) - set(prints))
        sign_registry.validate(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(data['signs'])} signs ({added} added). Not animated any more: {missing or 'none'}")
