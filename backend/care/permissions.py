from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from .models import AuditEvent, Profile


def profiles_for(user):
    # The owner, the care circle and the person the profile describes (once they linked their own account).
    return Profile.objects.filter(Q(owner=user) | Q(members__user=user) | Q(subject_user=user)).distinct()


def access(user, profile_id, scope="read"):
    # Scope membership in the lookup: outsider cannot enumerate profile existence.
    profile = get_object_or_404(profiles_for(user), pk=profile_id)
    if profile.owner_id == user.id:
        return profile
    if profile.subject_user_id == user.id:
        # The person themselves: their own data and preferences, not the circle's administration.
        if scope == "owner":
            raise PermissionDenied("permission_denied")
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
