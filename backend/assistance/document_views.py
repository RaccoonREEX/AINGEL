"""Document endpoints (assistance.documents). Opening a document needs the same authorization as describing a photo
of it; reading, the outline and search are local; transcription and explanations go to Meta and recheck the
person's consent every time, closing the document when it changed."""

import time

from rest_framework import serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from care.consent import capture_refusal, meta_account_denial, meta_allowed, private_media_allowed, still_current
from care.permissions import access

from . import documents, synthetic
from .persona import profile_preferences
from .views import basis_for
from .vision import VisionUnavailable

NO_STORE = {"Cache-Control": "no-store"}
# Free content and personal context: none of it may go with a server fixture.
DOCUMENT_FIELDS = ("file", "profile", "private_test", "question")


def refuse(error, status):
    return Response({"error": error}, status=status, headers=NO_STORE)


class OpenRequest(serializers.Serializer):
    file = serializers.FileField(required=False)
    fixture = serializers.CharField(required=False, max_length=40)
    locale = serializers.ChoiceField(choices=["en-US", "es-EC"])
    private_test = serializers.BooleanField(default=False)
    profile = serializers.UUIDField(required=False)


class AskRequest(serializers.Serializer):
    action = serializers.ChoiceField(choices=list(documents.ACTIONS))
    page = serializers.IntegerField(min_value=1, required=False)
    scope = serializers.ChoiceField(choices=["page", "document"], default="page")
    question = serializers.CharField(max_length=600, required=False)


def info(token, state):
    return {
        "document": token, "pages": state["pages"], "title": state["title"] or state["name"], "outline": state["outline"],
        "synthetic_fixture": state["fixture"], "expires_in": max(0, round(state["expires"] - time.time())),
    }


def chapter(state, number):
    current = None
    for row in state["outline"]:
        if row["page"] <= number:
            current = row["title"]
    return current


class DocumentsView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "documents"

    def post(self, request):
        if denial := meta_account_denial(request.user):
            return refuse(denial, 403)
        serializer = OpenRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        profile = access(request.user, values["profile"]) if "profile" in values else None
        # Documents have their own purpose (care.consent.meta_documents), not the camera's.
        if refusal := capture_refusal(profile, "document"):
            return refuse(refusal, 403)
        real = profile is not None and (
            private_media_allowed(profile, request.user, "document", values["private_test"]) or meta_allowed(profile, "document")
        )
        path, value = synthetic.route(request.data, "document", real, DOCUMENT_FIELDS)
        if path is None:
            return refuse(value, 400)
        if path != "fixture" and "file" not in values:
            return refuse("file_required", 400)
        try:
            if path == "fixture":
                data, name = synthetic.document(value), synthetic.DOCUMENTS[value]["es-EC"]
            else:
                upload = values["file"]
                if upload.size > documents.MAX_BYTES:
                    return refuse("document_too_large", 400)
                data, name = upload.read(documents.MAX_BYTES + 1), upload.name or ""
                if not documents.is_pdf(data):
                    data = documents.image_document(data)
            details = documents.describe_pdf(data)
        except documents.DocumentError as error:
            return refuse(str(error), 400)
        token = documents.open_session(
            request.user, data, basis_for(path), values["locale"], details, profile=profile if path == "real" else None,
            epoch=profile.consent_epoch if path == "real" else None, fixture=value if path == "fixture" else None,
            private_test=values["private_test"], name=name,
        )
        return Response(info(token, documents.load_session(token, request.user)), status=201, headers=NO_STORE)


class Session(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "documents"

    def state(self, request, token):
        state = documents.load_session(token, request.user)
        return state, (None if state else refuse("document_expired", 404))

    def gate(self, request, token, state):
        """(basis, profile, preferences, None) for a call to Meta, or (…, refusal) when it may not happen now."""
        if denial := meta_account_denial(request.user):
            return None, None, None, refuse(denial, 403)
        if state["fixture"]:
            if not synthetic.enabled():
                documents.close_session(token)
                return None, None, None, refuse("synthetic_tests_disabled", 403)
            return synthetic.FIXTURE, None, synthetic.FICTIONAL_PREFERENCES, None
        if state["profile"] is None:
            return state["basis"], None, None, None  # local test mode: only the test answer, never Meta
        profile = access(request.user, state["profile"])
        refusal = capture_refusal(profile, "document")
        if refusal or not still_current(profile, state["epoch"]):
            documents.close_session(token)
            return None, None, None, refuse(refusal or "consent_changed", 403 if refusal else 409)
        if not (private_media_allowed(profile, request.user, "document", state["private_test"]) or meta_allowed(profile, "document")):
            return None, None, None, refuse("privacy_review_required", 403)
        preferences = profile_preferences(profile.communication, meta_allowed(profile, "personalization"))
        return state["basis"], profile, preferences, None

    def changed(self, token, state, profile):
        """Revoked while Meta was reading: the answer is dropped and the document closed."""
        if profile is not None and not still_current(profile, state["epoch"]):
            documents.close_session(token)
            return refuse("consent_changed", 409)
        return None


class DocumentView(Session):
    def get(self, request, token):
        state, missing = self.state(request, token)
        return missing or Response(info(token, state), headers=NO_STORE)

    def delete(self, request, token):
        if documents.load_session(token, request.user) is not None:
            documents.close_session(token)
        return Response(status=204, headers=NO_STORE)


class PageView(Session):
    def get(self, request, token, number):
        """The page's own text, read locally; a scanned page returns its transcription once made."""
        state, missing = self.state(request, token)
        if missing:
            return missing
        if not 1 <= number <= state["pages"]:
            return refuse("page_not_found", 404)
        transcribed = state["transcribed"].get(str(number))
        try:
            raw = transcribed or documents.page_text(documents.pdf_bytes(state), number)
        except documents.DocumentError as error:
            return refuse(str(error), 400)
        text, paragraphs = documents.readable(raw)
        return Response({
            "page": number, "pages": state["pages"], "chapter": chapter(state, number), "text": text,
            "paragraphs": paragraphs, "has_text": transcribed is not None or documents.has_text(raw),
            "transcribed": transcribed is not None,
        }, headers=NO_STORE)


class TranscribeView(Session):
    def post(self, request, token, number):
        """A scanned page read by Meta from its picture, marked as a transcription and kept for this document."""
        state, missing = self.state(request, token)
        if missing:
            return missing
        if not 1 <= number <= state["pages"]:
            return refuse("page_not_found", 404)
        basis, profile, preferences, refusal = self.gate(request, token, state)
        if refusal:
            return refusal
        try:
            picture = documents.render(documents.pdf_bytes(state), number)
            result = documents.transcribe(picture, state["locale"], basis, preferences, request.user)
        except documents.DocumentError as error:
            return refuse(str(error), 400)
        except VisionUnavailable as error:
            return refuse(str(error), 503)
        if refusal := self.changed(token, state, profile):
            return refusal
        if result["mode"] == "meta":
            state["transcribed"][str(number)] = result["text"]
            documents.save_session(token, state)
        return Response({**result, "page": number, "pages": state["pages"], "chapter": chapter(state, number)}, headers=NO_STORE)


class SearchView(Session):
    def get(self, request, token):
        state, missing = self.state(request, token)
        if missing:
            return missing
        query = (request.query_params.get("q") or "").strip()[:100]
        try:
            hits = documents.search(documents.pdf_bytes(state), query, state["transcribed"])
        except documents.DocumentError as error:
            return refuse(str(error), 400)
        return Response({"query": query, "results": hits}, headers=NO_STORE)


class AskView(Session):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def post(self, request, token):
        """Explain, summarize, describe figures or answer a question, about a page or (when short) the document."""
        state, missing = self.state(request, token)
        if missing:
            return missing
        serializer = AskRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        question = (values.get("question") or "").strip()
        if values["action"] == "question" and not question:
            return refuse("question_required", 400)
        if state["fixture"] and question:
            return refuse("synthetic_fixture_only", 400)  # typed text is free content: never next to a fixture
        number = values.get("page", 1)
        if not 1 <= number <= state["pages"]:
            return refuse("page_not_found", 404)
        basis, profile, preferences, refusal = self.gate(request, token, state)
        if refusal:
            return refusal
        try:
            data = documents.pdf_bytes(state)
            if values["scope"] == "document":
                pages = [(n, state["transcribed"].get(str(n)) or documents.page_text(data, n)) for n in range(1, state["pages"] + 1)]
                if sum(len(text) for _, text in pages) > documents.WHOLE_TEXT_LIMIT:
                    return refuse("document_too_long_for_question", 400)
                picture = None
            else:
                pages = [(number, state["transcribed"].get(str(number)) or documents.page_text(data, number))]
                picture = documents.render(data, number)
            result = documents.ask(values["action"], state["locale"], basis, pages, picture, question, preferences, request.user)
        except documents.DocumentError as error:
            return refuse(str(error), 400)
        except VisionUnavailable as error:
            return refuse(str(error), 503)
        if refusal := self.changed(token, state, profile):
            return refusal
        return Response({**result, "page": number, "scope": values["scope"]}, headers=NO_STORE)
