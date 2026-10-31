"""Test helpers for the age and consent policy (care.consent). Not used by the application."""

from .consent import TERMS_VERSION, declare_adult, decide

META_PURPOSES = ("meta_conversation", "meta_photos", "meta_video", "meta_voice", "profile_personalization")


def adult(user):
    """The account declared it is 18 or older (as registration requires)."""
    declare_adult(user, TERMS_VERSION)
    return user


def authorize(profile, legacy=None, **purposes):
    """The owner is the person and decides: legacy flags (camera, microphone, meta_data) map to the purposes they
    used to cover; keyword purposes (e.g. meta_video=False) are decided as given."""
    profile.subject_status = "self"
    profile.save()
    adult(profile.owner)
    decisions = {}
    for key, value in (legacy or {}).items():
        if key == "camera":
            decisions["camera_local"] = value
        elif key == "microphone":
            decisions["microphone_local"] = value
        elif key == "meta_data":
            decisions.update({purpose: value for purpose in META_PURPOSES})
    decisions.update(purposes)
    for purpose, value in decisions.items():
        assert decide(profile, profile.owner, purpose, "grant" if value else "decline") is None
    profile.refresh_from_db()
    return profile
