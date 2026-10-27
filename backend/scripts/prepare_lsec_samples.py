"""Acquire two attributed LSEC research clips using bounded HTTP ranges.

This script does not activate clips in AINGEL or establish linguistic accuracy.
The publisher's metadata, individual hashes and EAF linkage are verified first.
"""

import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

import httpx

if __package__:
    from .prepare_lsec_metadata import PINNED_SHA256 as METADATA_SHA256
else:
    from prepare_lsec_metadata import PINNED_SHA256 as METADATA_SHA256

RECORD = "https://zenodo.org/api/records/21627229"
ARCHIVE_NAME = "lsec_sentence_level_1.0.0.zip"
ARCHIVE_URL = f"{RECORD}/files/{ARCHIVE_NAME}/content"
ARCHIVE_BYTES = 2_835_037_483
ARCHIVE_MD5 = "5e908994064ae848e4a88ba2f2a55367"
SAMPLES = {
    "fa1_000004": {
        "spanish": "Yo caminaré con una pelota en el parque.",
        "size": 31_026_506,
        "sha256": "74d0e4840ecdb410b1e69115d79aad01718f80e07b1e1b6c703b11eb26dd467c",
    },
    "fa1_000006": {
        "spanish": "Yo leeré un libro en mi casa.",
        "size": 27_871_698,
        "sha256": "3198b2203e84686a8db01dac7b757a5301e5a9712dfe1bab3053c39d0ae49b9c",
    },
}
MAX_METADATA_RANGE = 1024 * 1024
MIN_FREE_RESERVE = 16 * 1024 * 1024


def validate_range(response, start, end, total):
    expected = end - start + 1
    if response.status_code != 206:
        raise RuntimeError("Server did not honor the requested byte range")
    if response.headers.get("content-range") != f"bytes {start}-{end}/{total}":
        raise RuntimeError("Server returned an unexpected Content-Range")
    if response.headers.get("content-length") != str(expected):
        raise RuntimeError("Server returned an unexpected Content-Length")
    if response.headers.get("content-encoding", "identity").lower() != "identity":
        raise RuntimeError("Encoded range responses are not supported")


class RemoteZip(io.RawIOBase):
    def __init__(self, client, url=ARCHIVE_URL, size=ARCHIVE_BYTES):
        self.client, self.url, self.size, self.position = client, url, size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        base = {0: 0, 1: self.position, 2: self.size}[whence]
        target = base + offset
        if target < 0 or target > self.size:
            raise ValueError("Invalid seek")
        self.position = target
        return target

    def read(self, size=-1):
        requested = self.size - self.position if size < 0 else size
        count = min(requested, self.size - self.position)
        if not count:
            return b""
        if count < 0 or count > MAX_METADATA_RANGE:
            raise RuntimeError("Metadata read exceeds limit")
        start, end = self.position, self.position + count - 1
        with self.client.stream(
            "GET",
            self.url,
            headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"},
        ) as response:
            validate_range(response, start, end, self.size)
            raw = response.read()
        if len(raw) != count:
            raise RuntimeError("Incomplete metadata range")
        self.position += count
        return raw


def get_record(client):
    raw = bytearray()
    with client.stream("GET", RECORD) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw) > 2 * 1024 * 1024:
                raise RuntimeError("Record metadata too large")
    record = json.loads(raw)
    metadata = record.get("metadata", {})
    if (
        record.get("id") != 21627229
        or metadata.get("doi") != "10.5281/zenodo.21627229"
        or metadata.get("license", {}).get("id") != "cc-by-4.0"
    ):
        raise RuntimeError("Unexpected source DOI or license")
    entries = [x for x in record.get("files", []) if x.get("key") == ARCHIVE_NAME]
    if len(entries) != 1:
        raise RuntimeError("Source archive missing or ambiguous")
    item = entries[0]
    if (
        item.get("size") != ARCHIVE_BYTES
        or item.get("checksum") != f"md5:{ARCHIVE_MD5}"
        or item.get("links", {}).get("self") != ARCHIVE_URL
    ):
        raise RuntimeError("Source archive metadata has changed")
    return record


def read_checksums(metadata_zip):
    raw = metadata_zip.read_bytes()
    if hashlib.sha256(raw).hexdigest() != METADATA_SHA256:
        raise RuntimeError("Run prepare_lsec_metadata.py to obtain verified metadata")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        info = archive.getinfo("checksums.sha256")
        if info.file_size > MAX_METADATA_RANGE:
            raise RuntimeError("Checksum listing too large")
        text = archive.read(info).decode("utf-8")
    checksums = {}
    for line in text.splitlines():
        digest, separator, path = line.partition("  ")
        if not separator or len(digest) != 64 or path in checksums:
            raise RuntimeError("Invalid checksum listing")
        checksums[path] = digest
    return checksums


def linked_samples(remote, checksums):
    with zipfile.ZipFile(remote) as archive:
        csv_path = "sentence_level/manifests/sentence_level_manifest.csv"
        info = archive.getinfo(csv_path)
        if info.file_size > MAX_METADATA_RANGE:
            raise RuntimeError("Sentence manifest exceeds limit")
        csv_bytes = archive.read(info)
        if hashlib.sha256(csv_bytes).hexdigest() != checksums.get(csv_path):
            raise RuntimeError("Sentence manifest failed source checksum")
        rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
        found = {}
        for sample_id, expected in SAMPLES.items():
            matches = [row for row in rows if row.get("sample_id") == sample_id]
            if len(matches) != 1:
                raise RuntimeError("Sample row missing or ambiguous")
            row = matches[0]
            video_path = f"sentence_level/videos/{sample_id}.mp4"
            eaf_path = f"sentence_level/annotations/eaf/{sample_id}.eaf"
            if (
                row.get("video_path") != video_path
                or row.get("eaf_path") != eaf_path
                or row.get("spanish_text_index") != expected["spanish"]
                or row.get("spanish_text_eaf") != expected["spanish"]
                or row.get("spanish_match_status") != "match"
                or row.get("gloss_match_status") != "match"
                or row.get("video_sha256") != expected["sha256"]
                or checksums.get(video_path) != expected["sha256"]
            ):
                raise RuntimeError("Sample metadata or phrase does not match")
            eaf_info = archive.getinfo(eaf_path)
            if eaf_info.file_size > MAX_METADATA_RANGE:
                raise RuntimeError("Annotation exceeds size limit")
            eaf = archive.read(eaf_info)
            eaf_sha = hashlib.sha256(eaf).hexdigest()
            if eaf_sha != row.get("eaf_sha256") or eaf_sha != checksums.get(eaf_path):
                raise RuntimeError("Annotation checksum mismatch")
            if b"<!DOCTYPE" in eaf.upper() or b"<!ENTITY" in eaf.upper():
                raise RuntimeError("Unexpected annotation XML declaration")
            annotation = ET.fromstring(eaf)
            texts = [x.text or "" for x in annotation.iter("ANNOTATION_VALUE")]
            references = [
                node.attrib.get(key, "")
                for node in annotation.iter("MEDIA_DESCRIPTOR")
                for key in ("MEDIA_URL", "RELATIVE_MEDIA_URL")
                if node.attrib.get(key)
            ]

            def basename(value):
                return PurePosixPath(unquote(value).replace("\\", "/")).name.casefold()

            if expected["spanish"] not in texts or basename(
                row["original_filename"]
            ) not in [basename(ref) for ref in references]:
                raise RuntimeError("Annotation does not link the expected phrase/video")
            video = archive.getinfo(video_path)
            if (
                video.compress_type != zipfile.ZIP_STORED
                or video.flag_bits & 1
                or video.file_size != expected["size"]
                or video.compress_size != expected["size"]
            ):
                raise RuntimeError("Video ZIP entry is unsupported or changed")
            remote.seek(video.header_offset)
            header = struct.unpack(
                zipfile.structFileHeader, remote.read(zipfile.sizeFileHeader)
            )
            if header[zipfile._FH_SIGNATURE] != zipfile.stringFileHeader:
                raise RuntimeError("Invalid video ZIP header")
            raw_name = remote.read(header[zipfile._FH_FILENAME_LENGTH])
            remote.read(header[zipfile._FH_EXTRA_FIELD_LENGTH])
            if raw_name.decode("utf-8") != video_path:
                raise RuntimeError("Video ZIP local name mismatch")
            start = remote.tell()
            end = start + video.compress_size - 1
            if end >= remote.size:
                raise RuntimeError("Video range exceeds source archive")
            found[sample_id] = {
                "start": start,
                "end": end,
                "annotation_sha256": eaf_sha,
                "historical_media_reference": row.get(
                    "eaf_media_reference_status", "unknown"
                ),
            }
        return found


def download_sample(
    client, start, end, expected_hash, destination, total=ARCHIVE_BYTES, url=ARCHIVE_URL
):
    expected_size = end - start + 1
    if destination.exists():
        with destination.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if destination.stat().st_size != expected_size or digest != expected_hash:
            raise RuntimeError("Existing research clip has a different checksum")
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, prefix=".lsec-", suffix=".part", delete=False
        ) as stream:
            temporary = Path(stream.name)
            digest, received = hashlib.sha256(), 0
            with client.stream(
                "GET",
                url,
                headers={
                    "Range": f"bytes={start}-{end}",
                    "Accept-Encoding": "identity",
                },
            ) as response:
                validate_range(response, start, end, total)
                for chunk in response.iter_raw():
                    received += len(chunk)
                    if received > expected_size:
                        raise RuntimeError("Range response too large")
                    digest.update(chunk)
                    stream.write(chunk)
            if received != expected_size or digest.hexdigest() != expected_hash:
                raise RuntimeError("Video failed length or SHA-256 validation")
        if destination.exists():
            raise RuntimeError("Research clip appeared during download")
        temporary.replace(destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main():
    project = Path(__file__).resolve().parents[2]
    output = project / ".local" / "datasets" / "lsec-research"
    output.mkdir(parents=True, exist_ok=True)
    required = sum(
        item["size"]
        for sample_id, item in SAMPLES.items()
        if not (output / f"{sample_id}.mp4").exists()
    )
    if shutil.disk_usage(output).free < required + MIN_FREE_RESERVE:
        raise RuntimeError("Insufficient local disk space")
    checksums = read_checksums(
        project / ".local" / "datasets" / "lsec_metadata_1.0.0.zip"
    )
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        record = get_record(client)
        links = linked_samples(RemoteZip(client), checksums)
        for sample_id, item in SAMPLES.items():
            print(f"Preparing {sample_id}: {item['size']} bytes", flush=True)
            download_sample(
                client,
                links[sample_id]["start"],
                links[sample_id]["end"],
                item["sha256"],
                output / f"{sample_id}.mp4",
            )
    manifest = {
        "dataset": "AI-Ready Ecuadorian Sign Language Corpus",
        "source": "https://zenodo.org/records/21627229",
        "doi": "10.5281/zenodo.21627229",
        "version": record["metadata"].get("version"),
        "authors": [
            creator.get("name") for creator in record["metadata"].get("creators", [])
        ],
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Cite the dataset authors, title, DOI and CC BY 4.0; indicate any changes.",
        "storage": ".local/datasets/lsec-research/ (ignored by Git)",
        "purpose": "Private local research and future community review only; clips are not enabled in the application.",
        "linguistically_validated": False,
        "limitations": [
            "No independent LSEC comprehension assessment has been performed.",
            "EAF media references use historical paths marked unresolved; the manifest and source original filename establish the file mapping.",
            "Source metadata describes verified participant consent for publication, redistribution and AI/ML, while copyright licensing does not itself waive personality or privacy rights.",
            "These two fixed phrases are not a general or real-time sign-language translation system.",
        ],
        "samples": [
            {
                "id": sample_id,
                "spanish": item["spanish"],
                "video_path_in_source": f"sentence_level/videos/{sample_id}.mp4",
                "local_file": f"{sample_id}.mp4",
                "bytes": item["size"],
                "sha256": item["sha256"],
                "annotation_sha256": links[sample_id]["annotation_sha256"],
                "historical_media_reference": links[sample_id][
                    "historical_media_reference"
                ],
            }
            for sample_id, item in SAMPLES.items()
        ],
    }
    target = project / "docs" / "LSEC_RESEARCH_SAMPLES.json"
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Two research-only clips verified and saved locally; no app content activated."
    )


if __name__ == "__main__":
    main()
