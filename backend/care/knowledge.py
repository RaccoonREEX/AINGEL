"""Local educational index: source excerpts only, never diagnosis or inference."""

import json
import unicodedata
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .permissions import access, audit

MAX_INDEX_BYTES = 20 * 1024 * 1024


def search_key(text):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c)
    )


def index_path():
    return settings.BASE_DIR.parent / ".local" / "knowledge" / "medlineplus.json"


class KnowledgeUnavailable(Exception):
    pass


def load_index():
    try:
        with index_path().open("rb") as stream:
            raw = stream.read(MAX_INDEX_BYTES + 1)
        if len(raw) > MAX_INDEX_BYTES:
            raise ValueError("index_too_large")
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            raise ValueError("index_invalid")
        if data.get(
            "source"
        ) != "MedlinePlus, National Library of Medicine" or not isinstance(
            data.get("downloaded_at"), str
        ):
            raise ValueError("index_invalid")
        return data
    except FileNotFoundError:
        raise KnowledgeUnavailable("knowledge_not_installed") from None
    except (OSError, ValueError, TypeError, UnicodeError):
        raise KnowledgeUnavailable("knowledge_index_invalid") from None


def safe_record(item, language):
    if not isinstance(item, dict) or item.get("lang") != language:
        return None
    title, url, summary = item.get("title"), item.get("url"), item.get("summary")
    if (
        not all(isinstance(x, str) for x in (title, url, summary))
        or not title
        or len(title) > 300
        or len(summary) > 20000
    ):
        return None
    try:
        if any(char.isspace() for char in url) or "\\" in url:
            return None
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "medlineplus.gov"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            return None
    except ValueError:
        return None
    return {"title": title, "url": url, "lang": language, "summary": summary}


def exact_topic(title, language):
    index = load_index()
    for item in index["records"]:
        record = safe_record(item, language)
        if record and record["title"] == title:
            return {
                **record,
                "source": index["source"],
                "downloaded_at": index["downloaded_at"],
            }
    return None


@api_view(["POST"])
def resources(request, profile_id):
    profile = access(request.user, profile_id)
    data = request.data
    if not isinstance(data, dict) or set(data) - {"q", "lang"}:
        return Response({"error": "knowledge_query_invalid"}, status=400)
    query = data.get("q", "")
    language = data.get("lang", "es")
    if not isinstance(query, str) or not isinstance(language, str):
        return Response({"error": "knowledge_query_invalid"}, status=400)
    query = query.strip()
    if not 1 <= len(query) <= 100 or language not in {"es", "en"}:
        return Response({"error": "knowledge_query_invalid"}, status=400)
    needle = search_key(query)
    if not needle.strip():
        return Response({"error": "knowledge_query_invalid"}, status=400)
    audit(profile, request.user, "knowledge.searched")
    try:
        data = load_index()
    except KnowledgeUnavailable as error:
        return Response({"error": str(error)}, status=503)

    matches = []
    for item in data["records"]:
        record = safe_record(item, language)
        if not record:
            continue
        if needle in search_key(record["title"]):
            matches.append(
                {
                    **record,
                    "source": data["source"],
                    "downloaded_at": data["downloaded_at"],
                }
            )
            if len(matches) == 5:
                break
    # Neither the query nor the returned content belongs in the audit trail.
    return Response(matches)
