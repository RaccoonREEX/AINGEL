from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from rest_framework import serializers

from .consent import PURPOSES, clean_consents
from .models import Memory, Message, Profile, Routine

COMMUNICATION_DEFAULTS = {
    "addressing": "preferred_name",
    "preferred_name": "",
    "sentence_length": "short",
    "pace": "standard",
    "interaction": "one_step",
    "distress": "quiet_reassurance",
    "sign_language": "none",
    "communication_notes": "",
}


class CommunicationSerializer(serializers.Serializer):
    addressing = serializers.ChoiceField(
        choices=["preferred_name", "formal", "informal"]
    )
    preferred_name = serializers.CharField(max_length=100, allow_blank=True)
    sentence_length = serializers.ChoiceField(choices=["short", "standard"])
    pace = serializers.ChoiceField(choices=["slow", "standard"])
    interaction = serializers.ChoiceField(choices=["one_step", "standard"])
    distress = serializers.ChoiceField(
        choices=["quiet_reassurance", "contact_caregiver"]
    )
    sign_language = serializers.ChoiceField(choices=["none", "lsec", "asl", "other"])
    communication_notes = serializers.CharField(max_length=1000, allow_blank=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError(
                {"non_field_errors": ["communication_fields_invalid"]}
            )
        return super().to_internal_value(data)


class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    caregiver_count = serializers.SerializerMethodField()
    ready = serializers.SerializerMethodField()
    # Creation only: whether the account holder is the person (self) or sets it up for another adult, who must be
    # 18+ (no minors in this product) and then accepts from their own account (care.consent).
    for_self = serializers.BooleanField(write_only=True, required=False, default=False)
    subject_adult = serializers.BooleanField(write_only=True, required=False, default=False)
    grants = serializers.ListField(child=serializers.ChoiceField(choices=list(PURPOSES)), write_only=True, required=False, max_length=len(PURPOSES))

    class Meta:
        model = Profile
        fields = [
            "id",
            "display_name",
            "locale",
            "timezone",
            "allergies",
            "support_notes",
            "emergency_contact",
            "preferences",
            "role",
            "permissions",
            "caregiver_count",
            "ready",
            "face_recognition_enabled",
            "consents",
            "subject_status",
            "for_self",
            "subject_adult",
            "grants",
        ]
        # Decisions go through profiles/<id>/consent/ (only the person decides); the legacy flags are read-only.
        read_only_fields = ["face_recognition_enabled", "consents", "subject_status"]

    def validate(self, attrs):
        if self.instance is None:
            if not attrs.get("for_self") and not attrs.get("subject_adult"):
                raise serializers.ValidationError({"subject_adult": ["subject_minor_not_supported"]})
            if attrs.get("grants") and not attrs.get("for_self"):
                # A caregiver cannot accept on behalf of another adult.
                raise serializers.ValidationError({"grants": ["consent_subject_only"]})
        else:
            for key in ("for_self", "subject_adult", "grants"):
                attrs.pop(key, None)
        return attrs

    def create(self, validated):
        for_self = validated.pop("for_self", False)
        validated.pop("subject_adult", None)
        grants = validated.pop("grants", [])
        validated["subject_status"] = "self" if for_self else "pending_consent"
        profile = super().create(validated)
        from .consent import decide

        for purpose in dict.fromkeys(grants):
            decide(profile, profile.owner, purpose, "grant", method="own_account_signup")
        return profile

    def get_role(self, obj):
        user_id = self.context["request"].user.id
        if obj.owner_id == user_id:
            return "owner"
        return "subject" if obj.subject_user_id == user_id else "caregiver"

    def get_permissions(self, obj):
        if self.get_role(obj) == "owner":
            return {"configure": True, "memories": True, "manage_circle": True}
        if self.get_role(obj) == "subject":
            return {"configure": True, "memories": True, "manage_circle": False}
        member = obj.members.get(user=self.context["request"].user)
        return {
            "configure": member.can_configure,
            "memories": member.can_view_memories,
            "manage_circle": False,
        }

    def get_caregiver_count(self, obj):
        return obj.members.count()

    def get_ready(self, obj):
        return 1 <= obj.members.count() <= 4

    def validate_locale(self, value):
        if value not in ["es-EC", "en-US"]:
            raise serializers.ValidationError("locale_unsupported")
        return value

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise serializers.ValidationError("timezone_invalid") from None
        return value

    def validate_preferences(self, value):
        allowed = {
            "visual_assistance",
            "hearing_assistance",
            "memory_assistance",
            "large_text",
            "high_contrast",
            "voice_output",
            "reduced_motion",
            "simple_instructions",
        }
        if (
            not isinstance(value, dict)
            or set(value) - allowed
            or any(type(v) is not bool for v in value.values())
        ):
            raise serializers.ValidationError("preferences_invalid")
        return value


class RoutineSerializer(serializers.ModelSerializer):
    weekdays = serializers.JSONField(required=True)
    author = serializers.CharField(source="created_by.username", read_only=True)
    # Display name of who organizes the routine (the cared-for person sees it read-only).
    author_name = serializers.SerializerMethodField()
    confirmed_today = serializers.SerializerMethodField()
    confirmation_actor = serializers.SerializerMethodField()

    class Meta:
        model = Routine
        fields = [
            "id",
            "category",
            "title",
            "at",
            "weekdays",
            "instructions",
            "active",
            "author",
            "author_name",
            "confirmed_today",
            "confirmation_actor",
        ]

    def get_author_name(self, obj):
        user = obj.created_by
        return (user.get_full_name() or user.first_name or user.username).strip()

    def validate_weekdays(self, value):
        if (
            not isinstance(value, list)
            or not value
            or any(type(x) is not int or x not in range(7) for x in value)
            or len(set(value)) != len(value)
        ):
            raise serializers.ValidationError("weekdays_invalid")
        return sorted(value)

    def _check(self, obj):
        today = timezone.now().astimezone(ZoneInfo(obj.profile.timezone)).date()
        return obj.checks.filter(date=today).select_related("actor").first()

    def get_confirmed_today(self, obj):
        return self._check(obj) is not None

    def get_confirmation_actor(self, obj):
        check = self._check(obj)
        return check.actor.username if check else None


class MessageSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Message
        fields = ["id", "body", "locale", "author", "created_at"]

    def validate_locale(self, value):
        if value not in {"es-EC", "en-US"}:
            raise serializers.ValidationError("locale_unsupported")
        return value


class MemorySerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="recorded_by.username", read_only=True)
    has_evidence = serializers.SerializerMethodField()

    class Meta:
        model = Memory
        fields = [
            "id",
            "entity",
            "location",
            "observed_at",
            "source",
            "note",
            "author",
            "has_evidence",
            "expires_at",
        ]
        read_only_fields = ["source", "expires_at"]

    def validate_entity(self, value):
        return value.strip().casefold()

    def validate_observed_at(self, value):
        if value > timezone.now() + timedelta(minutes=1):
            raise serializers.ValidationError("observation_in_future")
        if value < timezone.now() - timedelta(days=7):
            raise serializers.ValidationError("observation_too_old")
        return value

    def get_has_evidence(self, obj):
        return bool(obj.evidence_path)
