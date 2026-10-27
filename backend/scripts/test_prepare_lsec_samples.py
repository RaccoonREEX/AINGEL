"""Offline tests for exact range and integrity enforcement; no real media."""

import hashlib
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import httpx

from scripts import prepare_lsec_samples as samples


class RangeTests(unittest.TestCase):
    def setUp(self):
        self.raw = b"synthetic data"
        self.sha256 = hashlib.sha256(self.raw).hexdigest()
        self.local_root = Path(__file__).resolve().parents[2] / ".local"
        self.local_root.mkdir(exist_ok=True)

    def client(self, mode="ok"):
        def handler(request):
            raw_range = request.headers["Range"].removeprefix("bytes=")
            start, end = (int(x) for x in raw_range.split("-"))
            body = self.raw[start : end + 1]
            headers = {
                "content-range": f"bytes {start}-{end}/{len(self.raw)}",
                "content-length": str(len(body)),
            }
            status = 206
            if mode == "full_response":
                status = 200
            if mode == "wrong_range":
                headers["content-range"] = f"bytes 0-{end}/{len(self.raw)}"
            if mode == "wrong_size":
                headers["content-length"] = str(len(body) + 1)
            if mode == "wrong_hash":
                body = bytes([body[0] ^ 1]) + body[1:]
            if mode == "short":
                body = body[:-1]
            return httpx.Response(
                status, headers=headers, stream=httpx.ByteStream(body)
            )

        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_seek_reads_exact_range(self):
        with self.client() as client:
            remote = samples.RemoteZip(
                client, url="https://test.invalid", size=len(self.raw)
            )
            self.assertEqual(remote.read(4), b"synt")
            remote.seek(-4, 2)
            self.assertEqual(remote.read(4), b"data")
            self.assertEqual(remote.read(4), b"")

    def test_full_or_wrong_range_is_rejected_before_read(self):
        for mode in ("full_response", "wrong_range", "wrong_size"):
            with self.subTest(mode=mode), self.client(mode) as client:
                remote = samples.RemoteZip(
                    client, url="https://test.invalid", size=len(self.raw)
                )
                remote.seek(1)
                with self.assertRaises(RuntimeError):
                    remote.read(4)

    def test_exact_clip_is_saved_and_verified(self):
        with tempfile.TemporaryDirectory(dir=self.local_root) as temp:
            self.assertTrue(
                Path(temp).resolve().is_relative_to(self.local_root.resolve())
            )
            path = Path(temp) / "synthetic.mp4"
            with self.client() as client:
                samples.download_sample(
                    client,
                    0,
                    len(self.raw) - 1,
                    self.sha256,
                    path,
                    len(self.raw),
                    "https://test.invalid",
                )
            self.assertEqual(path.read_bytes(), self.raw)

    def test_bad_hash_and_incomplete_body_leave_no_file(self):
        for mode in ("wrong_hash", "short", "full_response"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(
                dir=self.local_root
            ) as temp:
                self.assertTrue(
                    Path(temp).resolve().is_relative_to(self.local_root.resolve())
                )
                path = Path(temp) / "synthetic.mp4"
                with self.client(mode) as client, self.assertRaises(RuntimeError):
                    samples.download_sample(
                        client,
                        0,
                        len(self.raw) - 1,
                        self.sha256,
                        path,
                        len(self.raw),
                        "https://test.invalid",
                    )
                self.assertFalse(path.exists())
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_mismatched_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=self.local_root) as temp:
            self.assertTrue(
                Path(temp).resolve().is_relative_to(self.local_root.resolve())
            )
            path = Path(temp) / "synthetic.mp4"
            path.write_bytes(b"existing")
            with self.client() as client, self.assertRaises(RuntimeError):
                samples.download_sample(
                    client,
                    0,
                    len(self.raw) - 1,
                    self.sha256,
                    path,
                    len(self.raw),
                    "https://test.invalid",
                )
            self.assertEqual(path.read_bytes(), b"existing")


class ProvenanceTests(unittest.TestCase):
    def archive(self, annotation_phrase="Synthetic phrase.", media="original.mp4"):
        sample_id = "fa1_000004"
        video_path = f"sentence_level/videos/{sample_id}.mp4"
        eaf_path = f"sentence_level/annotations/eaf/{sample_id}.eaf"
        csv_path = "sentence_level/manifests/sentence_level_manifest.csv"
        video = b"fake"
        eaf = (
            '<ANNOTATION_DOCUMENT><HEADER><MEDIA_DESCRIPTOR MEDIA_URL="file:///'
            + media
            + '" /></HEADER><TIER><ANNOTATION><ALIGNABLE_ANNOTATION><ANNOTATION_VALUE>'
            + annotation_phrase
            + "</ANNOTATION_VALUE></ALIGNABLE_ANNOTATION></ANNOTATION></TIER></ANNOTATION_DOCUMENT>"
        ).encode()
        video_sha = hashlib.sha256(video).hexdigest()
        eaf_sha = hashlib.sha256(eaf).hexdigest()
        record = {
            "sample_id": sample_id,
            "video_path": video_path,
            "eaf_path": eaf_path,
            "spanish_text_index": "Synthetic phrase.",
            "spanish_text_eaf": "Synthetic phrase.",
            "spanish_match_status": "match",
            "gloss_match_status": "match",
            "video_sha256": video_sha,
            "eaf_sha256": eaf_sha,
            "original_filename": "original.mp4",
        }
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=record.keys())
        writer.writeheader()
        writer.writerow(record)
        manifest = output.getvalue().encode()
        output_zip = io.BytesIO()
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr(csv_path, manifest)
            archive.writestr(eaf_path, eaf)
            archive.writestr(video_path, video)
        checksums = {
            csv_path: hashlib.sha256(manifest).hexdigest(),
            eaf_path: eaf_sha,
            video_path: video_sha,
        }
        config = {
            sample_id: {
                "spanish": "Synthetic phrase.",
                "size": len(video),
                "sha256": video_sha,
            }
        }

        class MemoryRemote(io.BytesIO):
            @property
            def size(self):
                return len(self.getbuffer())

        return MemoryRemote(output_zip.getvalue()), checksums, config

    def test_eaf_and_manifest_establish_the_expected_link(self):
        remote, checksums, config = self.archive()
        with mock.patch.object(samples, "SAMPLES", config):
            linked = samples.linked_samples(remote, checksums)
        span = linked["fa1_000004"]
        self.assertEqual(remote.getvalue()[span["start"] : span["end"] + 1], b"fake")

    def test_wrong_eaf_phrase_or_media_reference_are_rejected(self):
        for args in ({"annotation_phrase": "Different."}, {"media": "different.mp4"}):
            with self.subTest(args=args):
                remote, checksums, config = self.archive(**args)
                with mock.patch.object(samples, "SAMPLES", config), self.assertRaises(
                    RuntimeError
                ):
                    samples.linked_samples(remote, checksums)


if __name__ == "__main__":
    unittest.main()
