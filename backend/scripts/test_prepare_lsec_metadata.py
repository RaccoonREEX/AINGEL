"""Offline validation of the LSEC metadata importer safety checks."""

import hashlib
import io
import unittest
from unittest import mock
import zipfile

from scripts import prepare_lsec_metadata as prepare


def fixture(extra=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in [
            "LICENSE.md",
            "CONSENT_STATUS.md",
            "ACCESS_AND_ETHICS.md",
            "DATA_DICTIONARY.md",
            "schemas/lexical_level_manifest.schema.json",
            "schemas/sentence_level_manifest.schema.json",
        ]:
            archive.writestr(name, "synthetic")
        if extra:
            archive.writestr(extra, "synthetic")
    return output.getvalue()


class LsecMetadataTests(unittest.TestCase):
    def setUp(self):
        self.raw = fixture()
        self.md5 = hashlib.md5(self.raw, usedforsecurity=False).hexdigest()
        self.sha256 = hashlib.sha256(self.raw).hexdigest()
        self.record = {
            "id": 21627229,
            "metadata": {
                "doi": "10.5281/zenodo.21627229",
                "license": {"id": "cc-by-4.0"},
            },
            "files": [
                {
                    "key": prepare.ARCHIVE,
                    "size": len(self.raw),
                    "checksum": "md5:" + self.md5,
                    "links": {"self": prepare.ARCHIVE_URL},
                }
            ],
        }

    def verify(self, raw, record):
        with (
            mock.patch.object(prepare, "PUBLISHED_MD5", self.md5),
            mock.patch.object(prepare, "PINNED_SHA256", self.sha256),
        ):
            prepare.verify_archive(raw, record)

    def test_valid_metadata_and_checksum(self):
        self.verify(self.raw, self.record)
        self.assertEqual(prepare.inspect_archive(self.raw)["files"], 6)

    def test_corrupted_archive_fails_even_at_same_size(self):
        damaged = bytearray(self.raw)
        damaged[-1] ^= 1
        with self.assertRaises(RuntimeError):
            self.verify(bytes(damaged), self.record)

    def test_wrong_license_and_unexpected_url_fail_closed(self):
        self.record["metadata"]["license"]["id"] = "unknown"
        with self.assertRaises(RuntimeError):
            self.verify(self.raw, self.record)
        self.record["metadata"]["license"]["id"] = "cc-by-4.0"
        self.record["files"][0]["links"]["self"] = "https://example.test/archive.zip"
        with self.assertRaises(RuntimeError):
            self.verify(self.raw, self.record)

    def test_media_is_rejected_even_when_required_docs_exist(self):
        with self.assertRaises(RuntimeError):
            prepare.inspect_archive(fixture("example.mp4"))

    def test_missing_required_docs_are_rejected(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("LICENSE.md", "synthetic")
        with self.assertRaises(RuntimeError):
            prepare.inspect_archive(output.getvalue())


if __name__ == "__main__":
    unittest.main()
