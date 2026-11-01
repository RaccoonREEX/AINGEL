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
    # Legacy sign-up authorizations (camera, microphone, meta_data), kept for history only: the granular
    # ConsentGrant decisions of the person themselves replace them (care.consent).
    consents = models.JSONField(default=dict, blank=True)
    # Who the data belongs to. "pending_confirmation": not recorded (profiles from before 30-10-2026): the owner must
    # confirm it explicitly, nothing is inferred. "self": the owner account is the person; "pending_consent": created by an adult for
    # another adult, who has not accepted yet; "subject_linked": that person accepted from their own account
    # (subject_user); "requires_legal_review": consent cannot be given by the person and no reviewed legal basis
    # exists yet. Only the person decides; nothing reaches Meta until they do.
    # Database defaults too: code from before 0007 (a rollback, or the old container during a deploy) inserts
    # profiles without these columns.
    subject_status = models.CharField(max_length=30, default="pending_confirmation", db_default="pending_confirmation")
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="subject_profiles"
    )
    # Bumped on every revocation or decline: work started before it cannot be presented as current.
    consent_epoch = models.PositiveIntegerField(default=0, db_default=0)
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


class AccountPolicy(models.Model):
    """Adult (18+) self-declaration of an account, required by the Meta Model API terms. Minimal data: no birth
    date nor documents; a self-declaration is not identity verification."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="aingel_policy")
    adult_declared_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=20, blank=True)
    declaration = models.CharField(max_length=30, default="self_declaration")
    # The account holder's own decision that the browser's (or phone's) speech recognition may send their voice to its
    # vendor (care.consent.SPEECH_SERVICE_VERSION). Their voice, so their account: never inherited by another one.
    speech_service_accepted_at = models.DateTimeField(null=True, blank=True)
    speech_service_version = models.CharField(max_length=20, blank=True, default="", db_default="")
    # Meta's Restricted Territories (care.territory): only whether the account declared being located in one of them,
    # for the policy version it answered. Never the country nor a location.
    territory = models.CharField(max_length=20, blank=True, default="", db_default="")
    territory_version = models.CharField(max_length=20, blank=True, default="", db_default="")
    territory_declared_at = models.DateTimeField(null=True, blank=True)


class ConsentGrant(models.Model):
    """One decision of the person about one purpose (care.consent.PURPOSES). The latest row per purpose is current;
    earlier rows are the history (who, when, version, how)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="consent_grants")
    purpose = models.CharField(max_length=40)
    status = models.CharField(max_length=20)  # granted | declined | revoked
    version = models.CharField(max_length=20)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    method = models.CharField(max_length=30, default="own_account")
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["profile", "purpose", "decided_at"])]


class SubjectInvite(models.Model):
    """One-time code so the adult a profile was created for can accept or decline from their own account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="subject_invites")
    code_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class SignFeedback(models.Model):
    """A Deaf user's or an expert's correction of one sign as AINGEL animates it (care.sign_registry). Reviewers read
    these before recording reviews; they never change a sign's status by themselves."""

    VERDICTS = [("correct", "correct"), ("incorrect", "incorrect"), ("unclear", "unclear"), ("regional_variant", "regional_variant")]
    ROLES = [("deaf_signer", "deaf_signer"), ("interpreter", "interpreter"), ("hearing_signer", "hearing_signer"),
             ("learner", "learner"), ("other", "other")]

    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    sign = models.CharField(max_length=40)
    language = models.CharField(max_length=10, default="lsec")
    fingerprint = models.CharField(max_length=64, blank=True)
    verdict = models.CharField(max_length=20, choices=VERDICTS)
    role = models.CharField(max_length=20, choices=ROLES)
    region = models.CharField(max_length=100, blank=True)
    comment = models.CharField(max_length=500, blank=True)
