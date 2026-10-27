"""Fetch only the pinned, public LSEC metadata archive; do not download videos.

The source record declares CC BY 4.0. The small archive contains public
documentation and schemas, not the video corpus or a trained model. A
separate rights and linguistic review is required for any later application.
"""

from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile

import httpx

RECORD_URL = "https://zenodo.org/api/records/21627229"
RECORD_PAGE = "https://zenodo.org/records/21627229"
ARCHIVE = "lsec_metadata_1.0.0.zip"
ARCHIVE_URL = f"{RECORD_URL}/files/{ARCHIVE}/content"
PUBLISHED_MD5 = "564bef6c17b21371e5a5f77b3657fe1a"
PINNED_SHA256 = "568bb5f1ea8322fdc563b3cc37bb748e48f0725b8f2d803abee46acf3d4f17b6"
MAX_RECORD_SIZE = 2 * 1024 * 1024
MAX_ARCHIVE_SIZE = 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 2 * 1024 * 1024


def fetch_limited(client, url, limit):
    data = bytearray()
    with client.stream("GET", url) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > limit:
                raise RuntimeError("Public source exceeds its size limit")
    return bytes(data)


def verify_archive(raw, record):
    """Validate both the provider's recorded checksum and our immutable pin."""
    if record.get("id") != 21627229:
        raise RuntimeError("Unexpected Zenodo record")
    metadata = record.get("metadata", {})
    if metadata.get("license", {}).get("id") != "cc-by-4.0":
        raise RuntimeError("The record license changed or is unavailable")
    if metadata.get("doi") != "10.5281/zenodo.21627229":
        raise RuntimeError("Unexpected Zenodo DOI")
    matches = [x for x in record.get("files", []) if x.get("key") == ARCHIVE]
    if len(matches) != 1:
        raise RuntimeError("The metadata archive is missing or ambiguous")
    item = matches[0]
    if item.get("links", {}).get("self") != ARCHIVE_URL:
        raise RuntimeError("Unexpected metadata archive URL")
    if item.get("checksum") != "md5:" + PUBLISHED_MD5:
        raise RuntimeError("The published archive checksum changed")
    if item.get("size") != len(raw) or len(raw) > MAX_ARCHIVE_SIZE:
        raise RuntimeError("The downloaded archive size does not match")
    # MD5 here checks the provider's published checksum, not password security.
    if hashlib.md5(raw, usedforsecurity=False).hexdigest() != PUBLISHED_MD5:
        raise RuntimeError("The downloaded archive failed the published checksum")
    if hashlib.sha256(raw).hexdigest() != PINNED_SHA256:
        raise RuntimeError("The downloaded archive failed the local SHA-256 pin")


def inspect_archive(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in members]
        if len(members) > 100 or len(set(names)) != len(names):
            raise RuntimeError("Unexpected metadata archive entries")
        if sum(item.file_size for item in members) > MAX_UNCOMPRESSED_SIZE:
            raise RuntimeError("Metadata archive expands beyond its limit")
        required = {
            "LICENSE.md",
            "CONSENT_STATUS.md",
            "ACCESS_AND_ETHICS.md",
            "DATA_DICTIONARY.md",
            "schemas/lexical_level_manifest.schema.json",
            "schemas/sentence_level_manifest.schema.json",
        }
        if not required.issubset(names):
            raise RuntimeError("Required provenance documents are missing")
        # Inventory file types only; never emit per-person names, paths or content.
        extensions = Counter(
            Path(name).suffix.lower() or "no_extension" for name in names
        )
        allowed = {".md", "no_extension", ".cff", ".jsonld", ".json", ".py", ".sha256"}
        if set(extensions) - allowed:
            raise RuntimeError("This preparation accepts metadata files only")
        return {
            "files": len(members),
            "total_uncompressed_bytes": sum(item.file_size for item in members),
            "file_type_counts": dict(sorted(extensions.items())),
        }


def write_atomic(destination, raw):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        temporary.replace(destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main():
    project = Path(__file__).resolve().parents[2]
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        record = json.loads(fetch_limited(client, RECORD_URL, MAX_RECORD_SIZE))
        raw = fetch_limited(client, ARCHIVE_URL, MAX_ARCHIVE_SIZE)
    verify_archive(raw, record)
    inventory = inspect_archive(raw)
    manifest = {
        "dataset": "AI-Ready Ecuadorian Sign Language Corpus",
        "source": RECORD_PAGE,
        "record_api": RECORD_URL,
        "doi": "10.5281/zenodo.21627229",
        "record_version": record["metadata"].get("version"),
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_archive": ARCHIVE_URL,
        "archive_bytes": len(raw),
        "published_md5": PUBLISHED_MD5,
        "sha256_pin": PINNED_SHA256,
        "archive_inventory": inventory,
        "contains_video_or_image_files": False,
        "large_corpus_archives_downloaded": False,
        "videos_activated_in_app": False,
        "training_performed": False,
        "translation_model_available": False,
        "consent_note": "The provider's public metadata states signed consent was verified for two participants and covers AI/ML and redistribution. Review the scope and personality/privacy rights before any specific use.",
    }
    write_atomic(project / ".local" / "datasets" / ARCHIVE, raw)
    write_atomic(
        project / "docs" / "LSEC_DATASET_MANIFEST.json",
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    print(
        json.dumps(
            {
                "archive_verified": True,
                "archive_bytes": len(raw),
                "metadata_files": inventory["files"],
                "large_archives_downloaded": False,
                "videos_activated": False,
            }
        )
    )


if __name__ == "__main__":
    main()
