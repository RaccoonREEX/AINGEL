"""Import only NLM's public-domain health-topic summaries, locally and with provenance.

This index is an educational source, not a medical advice model or training corpus.
No patient, care profile, or query data are sent to the publisher.
"""

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import httpx

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / ".local" / "knowledge" / "medlineplus.json"
LISTING = "https://medlineplus.gov/xml.html"
MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_XML = 64 * 1024 * 1024
SOURCE = "MedlinePlus, National Library of Medicine"


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "li", "br", "h2", "h3", "h4"}:
            self.parts.append(" ")

    def text(self):
        return re.sub(r"\s+", " ", "".join(self.parts)).strip()


def parse_records(xml_bytes):
    root = ET.fromstring(xml_bytes)
    if root.tag != "health-topics":
        raise ValueError("unexpected_medlineplus_format")
    records = []
    for topic in root.findall("health-topic"):
        language = {"English": "en", "Spanish": "es"}.get(topic.get("language"))
        title, url = topic.get("title", ""), topic.get("url", "")
        parsed_url = urlparse(url)
        summary = topic.find("full-summary")
        if (
            not language
            or not title
            or parsed_url.scheme != "https"
            or parsed_url.hostname != "medlineplus.gov"
            or parsed_url.username is not None
            or parsed_url.password is not None
            or summary is None
        ):
            continue
        plain = TextOnly()
        plain.feed("".join(summary.itertext()))
        text = plain.text()
        if text:
            records.append(
                {"title": title, "url": url, "lang": language, "summary": text}
            )
    if not records:
        raise ValueError("no_health_topic_summaries")
    return root.get("date-generated", ""), records


def download_limited(client, url, limit):
    with client.stream("GET", url) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > limit:
                raise ValueError("download_too_large")
        return bytes(content)


def main():
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        listing = download_limited(client, LISTING, 1024 * 1024).decode("utf-8")
        links = re.findall(
            r'href=["\']([^"\']*mplus_topics_compressed_\d{4}-\d{2}-\d{2}\.zip)["\']',
            listing,
        )
        if not links:
            raise ValueError("official_archive_link_missing")
        archive_url = urljoin(LISTING, links[0])
        parsed = urlparse(archive_url)
        if parsed.scheme != "https" or parsed.hostname != "medlineplus.gov":
            raise ValueError("archive_origin_invalid")
        archive = download_limited(client, archive_url, MAX_DOWNLOAD)
    with ZipFile(BytesIO(archive)) as z:
        files = z.infolist()
        if (
            len(files) != 1
            or files[0].file_size > MAX_XML
            or not files[0].filename.endswith(".xml")
        ):
            raise ValueError("archive_contents_invalid")
        xml_bytes = z.read(files[0])
    generated, records = parse_records(xml_bytes)
    index = {
        "source": SOURCE,
        "source_url": LISTING,
        "archive_url": archive_url,
        "archive_sha256": sha256(archive).hexdigest(),
        "generated_at_source": generated,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    temporary = DESTINATION.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    temporary.replace(DESTINATION)
    print(
        f"Imported {len(records)} public health-topic summaries into the ignored local index."
    )
    print(
        "Source: MedlinePlus, National Library of Medicine. No external links or images imported."
    )


if __name__ == "__main__":
    main()
