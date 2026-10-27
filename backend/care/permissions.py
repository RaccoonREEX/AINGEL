from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from .models import AuditEvent, Profile


def profiles_for(user):
    return Profile.objects.filter(Q(owner=user) | Q(members__user=user)).distinct()


def access(user, profile_id, scope="read"):
    # Scope membership in the lookup: outsider cannot enumerate profile existence.
    profile = get_object_or_404(profiles_for(user), pk=profile_id)
    if profile.owner_id == user.id:
        return profile
    member = profile.members.get(user=user)
    if (
        scope == "owner"
        or (scope == "configure" and not member.can_configure)
        or (scope == "memory" and not member.can_view_memories)
    ):
        raise PermissionDenied("permission_denied")
    return profile


def audit(profile, actor, action, resource_id=""):
    AuditEvent.objects.create(
        profile=profile, actor=actor, action=action, resource_id=str(resource_id)
    )
