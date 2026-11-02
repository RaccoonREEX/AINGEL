"""Only Meta «Standard» models may receive people's content (docs/META_MODEL_API_TERMS.md): Meta's terms forbid
sending personal, confidential or sensitive information to Contributor/Discounted models (§6.2), and use their
content for training. This scans the code that builds requests so a Contributor model ID cannot slip in."""

import re
from pathlib import Path

from django.test import SimpleTestCase

ASSISTANCE = Path(__file__).resolve().parent
# Standard models per Meta's Model Designation Policy (2026-10-12) that AINGEL calls.
STANDARD = {"muse-spark-1.3", "muse-voice-transcribe-1.0", "sam-3.1"}


class MetaModalityTests(SimpleTestCase):
    def test_no_contributor_model_in_request_code(self):
        for source in ASSISTANCE.glob("*.py"):
            if source.name.startswith("test_"):
                continue
            text = source.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"muse-spark-[\d.]+-contributor", source.name)

    def test_every_model_id_used_is_a_standard_model(self):
        found = set()
        for source in ASSISTANCE.glob("*.py"):
            if not source.name.startswith("test_"):
                found |= set(re.findall(r'"((?:muse|sam)-[a-z0-9.-]+)"', source.read_text(encoding="utf-8")))
        self.assertTrue(found)
        self.assertLessEqual(found, STANDARD, found - STANDARD)
