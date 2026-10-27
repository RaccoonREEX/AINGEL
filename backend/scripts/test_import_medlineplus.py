from unittest import TestCase

from scripts.import_medlineplus import SOURCE, parse_records


class ImportMedlinePlusTests(TestCase):
    def test_only_summary_from_approved_source_and_language_is_imported(self):
        source = b"""<health-topics date-generated="2026-10-27">
          <health-topic title="Example" url="https://medlineplus.gov/example.html" language="English">
            <full-summary>&lt;p&gt;Public &lt;b&gt;summary&lt;/b&gt;.&lt;/p&gt;</full-summary>
            <site>Copyrighted third-party site must not be imported</site>
          </health-topic>
          <health-topic title="Untrusted" url="https://example.org/" language="Spanish"><full-summary>No</full-summary></health-topic>
          <health-topic title="Credentials" url="https://user:pass@medlineplus.gov/" language="English"><full-summary>No</full-summary></health-topic>
          <health-topic title="Missing summary" url="https://medlineplus.gov/" language="English"/>
        </health-topics>"""
        generated, records = parse_records(source)
        self.assertEqual(generated, "2026-10-27")
        self.assertEqual(
            records,
            [
                {
                    "title": "Example",
                    "url": "https://medlineplus.gov/example.html",
                    "lang": "en",
                    "summary": "Public summary.",
                }
            ],
        )
        self.assertEqual(SOURCE, "MedlinePlus, National Library of Medicine")

    def test_invalid_source_format_is_not_written_as_knowledge(self):
        with self.assertRaises(ValueError):
            parse_records(b"<unrelated />")
