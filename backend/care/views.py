from datetime import timedelta
import hashlib
from pathlib import Path
import secrets
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from assistance.scene import normalize_image
from .models import (
    AuditEvent,
    Invitation,
    Membership,
    Memory,
    Message,
    Profile,
    Routine,
    RoutineCheck,
)
from .permissions import access, audit, profiles_for
from .serializers import (
    COMMUNICATION_DEFAULTS,
    CommunicationSerializer,
    MemorySerializer,
    MessageSerializer,
    ProfileSerializer,
    RoutineSerializer,
)


@api_view(["GET", "POST"])
def profiles(request):
    if request.method == "GET":
        items = list(profiles_for(request.user).order_by("created_at"))
        for item in items:
            audit(item, request.user, "profile.read", item.id)
        return Response(
            ProfileSerializer(items, many=True, context={"request": request}).data
        )
    if Profile.objects.filter(owner=request.user).exists():
        raise ValidationError("owner_profile_exists")
    serializer = ProfileSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        # Serialize per-owner creation as well as the database uniqueness constraint.
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if Profile.objects.filter(owner=request.user).exists():
            raise ValidationError("owner_profile_exists")
        obj = serializer.save(owner=request.user)
        audit(obj, request.user, "profile.created", obj.id)
    return Response(serializer.data, status=201)


@api_view(["GET", "PATCH"])
def profile_detail(request, profile_id):
    obj = access(
        request.user, profile_id, "configure" if request.method == "PATCH" else "read"
    )
    if request.method == "PATCH":
        # Authorizations to send camera, microphone and data to Meta are only the owner's decision.
        if "consents" in request.data and obj.owner_id != request.user.id:
            return Response({"error": "consents_owner_only"}, status=403)
        serializer = ProfileSerializer(
            obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit(obj, request.user, "profile.updated", obj.id)
    else:
        serializer = ProfileSerializer(obj, context={"request": request})
        audit(obj, request.user, "profile.read", obj.id)
    return Response(serializer.data)


@api_view(["GET", "PATCH"])
def communication(request, profile_id):
    obj = access(
        request.user, profile_id, "configure" if request.method == "PATCH" else "read"
    )
    if request.method == "PATCH":
        serializer = CommunicationSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            # Updates by different caregivers must not overwrite one another.
            obj = Profile.objects.select_for_update().get(pk=obj.pk)
            access(request.user, profile_id, "configure")
            current = {**COMMUNICATION_DEFAULTS, **obj.communication}
            current.update(serializer.validated_data)
            obj.communication = current
            obj.save(update_fields=["communication", "updated_at"])
            audit(obj, request.user, "communication.updated", obj.id)
    return Response({**COMMUNICATION_DEFAULTS, **obj.communication})


def member_data(member):
    return {
        "id": member.id,
        "username": member.user.username,
        "relationship": member.relationship,
        "can_configure": member.can_configure,
        "can_view_memories": member.can_view_memories,
    }


class InviteRequest(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    relationship = serializers.CharField(max_length=80)
    can_configure = serializers.BooleanField(default=True)
    can_view_memories = serializers.BooleanField(default=False)


@api_view(["GET", "POST"])
def circle(request, profile_id):
    obj = access(
        request.user, profile_id, "owner" if request.method == "POST" else "read"
    )
    if request.method == "GET":
        pending = (
            obj.invitations.filter(expires_at__gt=timezone.now()).select_related(
                "target"
            )
            if obj.owner_id == request.user.id
            else []
        )
        return Response(
            {
                "members": [member_data(x) for x in obj.members.select_related("user")],
                "pending": [
                    {
                        "id": x.id,
                        "username": x.target.username,
                        "relationship": x.relationship,
                        "expires_at": x.expires_at,
                    }
                    for x in pending
                ],
                "maximum": 4,
            }
        )
    serializer = InviteRequest(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    # Invite an existing account; do not grant access before intended recipient accepts.
    target = get_object_or_404(
        get_user_model(), username=values["username"].strip().lower(), is_active=True
    )
    with transaction.atomic():
        obj = Profile.objects.select_for_update().get(pk=obj.pk)
        pending = obj.invitations.filter(expires_at__gt=timezone.now())
        if (
            target.pk == obj.owner_id
            or obj.members.filter(user=target).exists()
            or pending.filter(target=target).exists()
        ):
            raise ValidationError("caregiver_already_linked")
        if obj.members.count() + pending.count() >= 4:
            raise ValidationError("care_circle_full")
        token = secrets.token_urlsafe(32)
        invitation = Invitation.objects.create(
            profile=obj,
            target=target,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            relationship=values["relationship"],
            can_configure=values["can_configure"],
            can_view_memories=values["can_view_memories"],
            expires_at=timezone.now() + timedelta(days=7),
        )
        audit(obj, request.user, "circle.invited", invitation.id)
    return Response(
        {"id": invitation.id, "code": token, "expires_at": invitation.expires_at},
        status=201,
    )


@api_view(["POST"])
def accept_invite(request):
    code = request.data.get("code", "")
    if not isinstance(code, str) or not 20 <= len(code) <= 100:
        raise ValidationError("invitation_invalid")
    with transaction.atomic():
        invitation = get_object_or_404(
            Invitation,
            token_hash=hashlib.sha256(code.encode()).hexdigest(),
            target=request.user,
            expires_at__gt=timezone.now(),
        )
        obj = Profile.objects.select_for_update().get(pk=invitation.profile_id)
        # Recheck after locking: a cancelled/expired invitation must never regain access.
        invitation = get_object_or_404(
            obj.invitations,
            pk=invitation.pk,
            token_hash=hashlib.sha256(code.encode()).hexdigest(),
            target=request.user,
            expires_at__gt=timezone.now(),
        )
        if obj.members.count() >= 4:
            raise ValidationError("care_circle_full")
        if obj.members.filter(user=request.user).exists():
            raise ValidationError("caregiver_already_linked")
        member = Membership.objects.create(
            profile=obj,
            user=request.user,
            relationship=invitation.relationship,
            can_configure=invitation.can_configure,
            can_view_memories=invitation.can_view_memories,
        )
        invitation.delete()
        audit(obj, request.user, "circle.accepted", member.id)
    return Response({"profile_id": obj.id}, status=201)


@api_view(["DELETE"])
def cancel_invite(request, profile_id, invitation_id):
    obj = access(request.user, profile_id, "owner")
    with transaction.atomic():
        obj = Profile.objects.select_for_update().get(pk=obj.pk)
        invitation = get_object_or_404(obj.invitations, pk=invitation_id)
        invitation.delete()
        audit(obj, request.user, "circle.invitation_cancelled", invitation_id)
    return Response(status=204)


@api_view(["PATCH", "DELETE"])
def membership(request, profile_id, member_id):
    obj = access(request.user, profile_id)
    with transaction.atomic():
        obj = Profile.objects.select_for_update().get(pk=obj.pk)
        member = get_object_or_404(obj.members, pk=member_id)
        if obj.owner_id != request.user.id and not (
            request.method == "DELETE" and member.user_id == request.user.id
        ):
            raise PermissionDenied("permission_denied")
        if request.method == "DELETE":
            # Revocation must always work, including the last member: readiness returns to draft.
            member.delete()
            audit(obj, request.user, "circle.revoked", member_id)
            return Response(status=204)
        for field in ["can_configure", "can_view_memories"]:
            if field in request.data:
                if type(request.data[field]) is not bool:
                    raise ValidationError("permissions_invalid")
                setattr(member, field, request.data[field])
        member.save()
        audit(obj, request.user, "circle.permissions_updated", member.id)
    return Response(member_data(member))


@api_view(["GET", "POST"])
def routines(request, profile_id):
    obj = access(
        request.user, profile_id, "configure" if request.method == "POST" else "read"
    )
    if request.method == "GET":
        return Response(
            RoutineSerializer(
                obj.routines.select_related("profile", "created_by").order_by("at"),
                many=True,
            ).data
        )
    serializer = RoutineSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    routine = serializer.save(profile=obj, created_by=request.user)
    audit(obj, request.user, "routine.created", routine.id)
    return Response(serializer.data, status=201)


@api_view(["PATCH", "DELETE"])
def routine_detail(request, profile_id, routine_id):
    obj = access(request.user, profile_id, "configure")
    routine = get_object_or_404(obj.routines, pk=routine_id)
    if request.method == "DELETE":
        routine.delete()
        audit(obj, request.user, "routine.deleted", routine_id)
        return Response(status=204)
    serializer = RoutineSerializer(routine, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    audit(obj, request.user, "routine.updated", routine.id)
    return Response(serializer.data)


@api_view(["POST", "DELETE"])
def routine_confirm(request, profile_id, routine_id):
    obj = access(request.user, profile_id, "configure")
    routine = get_object_or_404(obj.routines, pk=routine_id)
    today = timezone.now().astimezone(ZoneInfo(obj.timezone)).date()
    if request.method == "POST":
        if not routine.active or today.weekday() not in routine.weekdays:
            raise ValidationError("routine_not_scheduled_today")
        RoutineCheck.objects.get_or_create(
            routine=routine, date=today, defaults={"actor": request.user}
        )
    else:
        routine.checks.filter(date=today).delete()
    audit(obj, request.user, "routine.confirmation_changed", routine.id)
    return Response(RoutineSerializer(routine).data)


@api_view(["GET", "POST"])
def messages(request, profile_id):
    obj = access(request.user, profile_id)
    if request.method == "GET":
        return Response(
            MessageSerializer(
                obj.messages.select_related("author").order_by("-created_at")[:100],
                many=True,
            ).data
        )
    serializer = MessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    msg = serializer.save(profile=obj, author=request.user)
    audit(obj, request.user, "message.created", msg.id)
    return Response(serializer.data, status=201)


@api_view(["DELETE"])
def message_delete(request, profile_id, message_id):
    obj = access(request.user, profile_id)
    msg = get_object_or_404(obj.messages, pk=message_id)
    if obj.owner_id != request.user.id and msg.author_id != request.user.id:
        raise PermissionDenied("permission_denied")
    msg.delete()
    audit(obj, request.user, "message.deleted", message_id)
    return Response(status=204)


@api_view(["GET", "POST"])
def memories(request, profile_id):
    obj = access(request.user, profile_id, "memory")
    if request.method == "GET":
        items = (
            obj.memories.filter(expires_at__gt=timezone.now())
            .select_related("recorded_by")
            .order_by("-observed_at")[:100]
        )
        audit(obj, request.user, "memory.list_read")
        return Response(MemorySerializer(items, many=True).data)
    # Caregiver read grant never grants the right to create assertions about another person's memory.
    if obj.owner_id != request.user.id:
        raise PermissionDenied("owner_required_for_memory")
    if request.data.get("confirmed") not in [True, "true"]:
        raise ValidationError("memory_confirmation_required")
    serializer = MemorySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    evidence = request.FILES.get("evidence")
    path = ""
    normalized = None
    if evidence:
        try:
            normalized = normalize_image(evidence)
        except ValueError as error:
            raise ValidationError(str(error)) from None
        path = str(uuid.uuid4()) + ".jpg"
    try:
        with transaction.atomic():
            if normalized:
                settings.PRIVATE_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
                (settings.PRIVATE_MEDIA_ROOT / path).write_bytes(normalized)
            memory = serializer.save(
                profile=obj,
                recorded_by=request.user,
                expires_at=timezone.now() + timedelta(days=7),
                evidence_path=path,
            )
            audit(obj, request.user, "memory.confirmed_saved", memory.id)
    except Exception:
        if path:
            (settings.PRIVATE_MEDIA_ROOT / path).unlink(missing_ok=True)
        raise
    return Response(serializer.data, status=201)


@api_view(["GET", "DELETE"])
def memory_detail(request, profile_id, memory_id):
    obj = access(request.user, profile_id, "memory")
    memory = get_object_or_404(
        obj.memories, pk=memory_id, expires_at__gt=timezone.now()
    )
    if request.method == "DELETE":
        if obj.owner_id != request.user.id:
            raise PermissionDenied("owner_required_for_memory")
        # Delete file first: failure must not leave a successful deletion claim.
        if memory.evidence_path:
            (settings.PRIVATE_MEDIA_ROOT / memory.evidence_path).unlink(missing_ok=True)
        memory.delete()
        audit(obj, request.user, "memory.deleted", memory_id)
        return Response(status=204)
    if not memory.evidence_path:
        return Response({"error": "evidence_missing"}, status=404)
    path = settings.PRIVATE_MEDIA_ROOT / memory.evidence_path
    if not path.is_file():
        return Response({"error": "evidence_missing"}, status=404)
    audit(obj, request.user, "evidence.read", memory.id)
    return FileResponse(
        path.open("rb"), content_type="image/jpeg", filename="evidence.jpg"
    )


@api_view(["POST"])
def ask(request, profile_id):
    tool = request.data.get("tool")
    obj = access(
        request.user, profile_id, "memory" if tool == "search_memory" else "read"
    )
    # Structured local tools are authoritative; no private health or memory data goes to an LLM.
    if tool == "search_memory":
        entity = request.data.get("entity", "")
        if not isinstance(entity, str) or not entity.strip() or len(entity) > 100:
            raise ValidationError("entity_required")
        item = (
            obj.memories.filter(
                entity__iexact=entity.strip(), expires_at__gt=timezone.now()
            )
            .order_by("-observed_at", "-created_at")
            .first()
        )
        audit(obj, request.user, "memory.search")
        return Response(
            {
                "tool": tool,
                "found": bool(item),
                "evidence": MemorySerializer(item).data if item else None,
                "answer_code": "last_reported_location" if item else "no_evidence",
                "mode": "local_evidence",
            }
        )
    if tool == "get_routines":
        today = timezone.now().astimezone(ZoneInfo(obj.timezone)).weekday()
        items = [
            x
            for x in obj.routines.filter(active=True)
            .select_related("profile", "created_by")
            .order_by("at")
            if today in x.weekdays
        ]
        return Response(
            {
                "tool": tool,
                "items": RoutineSerializer(items, many=True).data,
                "mode": "local_evidence",
            }
        )
    if tool == "get_care_messages":
        return Response(
            {
                "tool": tool,
                "items": MessageSerializer(
                    obj.messages.select_related("author").order_by("-created_at")[:20],
                    many=True,
                ).data,
                "mode": "local_evidence",
            }
        )
    raise ValidationError("tool_unsupported")


@api_view(["GET"])
def audit_events(request, profile_id):
    obj = access(request.user, profile_id, "owner")
    return Response(
        [
            {
                "id": x.id,
                "actor": x.actor.username,
                "action": x.action,
                "resource_id": x.resource_id,
                "created_at": x.created_at,
            }
            for x in AuditEvent.objects.filter(profile=obj)
            .select_related("actor")
            .order_by("-created_at")[:100]
        ]
    )
