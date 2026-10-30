import uuid

from django.conf import settings
from django.db import models


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aingel_profile",
    )
    display_name = models.CharField(max_length=100)
    locale = models.CharField(max_length=20, default="es-EC")
    timezone = models.CharField(max_length=80, default="America/Guayaquil")
    allergies = models.TextField(max_length=2000, blank=True)
    support_notes = models.TextField(max_length=3000, blank=True)
    emergency_contact = models.CharField(max_length=200, blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    communication = models.JSONField(default=dict, blank=True)
    face_recognition_enabled = models.BooleanField(default=False)
    # Authorizations given at sign-up (care.consent): camera, microphone, meta_data + version, time, who.
    consents = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Membership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    relationship = models.CharField(max_length=80)
    can_configure = models.BooleanField(default=True)
    can_view_memories = models.BooleanField(default=False)
    face_consent_epoch = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "user"], name="unique_profile_caregiver"
            )
        ]


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="invitations"
    )
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    relationship = models.CharField(max_length=80)
    can_configure = models.BooleanField(default=True)
    can_view_memories = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class Routine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="routines"
    )
    category = models.CharField(
        max_length=20,
        choices=[
            (x, x)
            for x in [
                "sleep",
                "wake",
                "medicine",
                "bathroom",
                "meal",
                "water",
                "appointment",
                "other",
            ]
        ],
    )
    title = models.CharField(max_length=150)
    at = models.TimeField()
    weekdays = models.JSONField(default=list)
    instructions = models.TextField(max_length=2000, blank=True)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class RoutineCheck(models.Model):
    routine = models.ForeignKey(
        Routine, on_delete=models.CASCADE, related_name="checks"
    )
    date = models.DateField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["routine", "date"], name="one_routine_confirmation_per_day"
            )
        ]


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=2000)
    locale = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)


class Memory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="memories"
    )
    entity = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    observed_at = models.DateTimeField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source = models.CharField(max_length=20, default="user_report", editable=False)
    note = models.TextField(max_length=1000, blank=True)
    evidence_path = models.CharField(max_length=160, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MFADevice(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_device"
    )
    secret_encrypted = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)
    last_counter = models.BigIntegerField(default=-1)
    pending_encrypted = models.TextField(blank=True)
    pending_at = models.DateTimeField(null=True)
    recovery_hashes = models.JSONField(default=list)
    epoch = models.PositiveIntegerField(default=0)


class FamilyFace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.OneToOneField(
        Membership, on_delete=models.CASCADE, related_name="face_enrollment"
    )
    display_name = models.CharField(max_length=100)
    embedding_encrypted = models.TextField()
    consent_version = models.CharField(max_length=30, default="family-face-v1")
    consented_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
