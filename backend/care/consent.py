"""Who may use Meta, and whose data may reach it.

Accounts: the Meta Model API terms require every user and end user to be 18 or older. Each account declares it
(AccountPolicy: date, terms version, kind of declaration; no birth date nor documents). A self-declaration is not
identity verification. Accounts without it cannot use any Meta endpoint (meta_account_denial).

People: the data of a profile belongs to the person it describes (the subject), not to whoever created it. Only that
adult decides, purpose by purpose (PURPOSES), from their own account:
- "pending_confirmation": profiles from before this policy: who the data belongs to was never recorded and is not
  inferred; the owner confirms it explicitly (confirm_subject). Nothing reaches Meta meanwhile.
- "self": the owner account is the person.
- "pending_consent": an adult created it for another adult, who has not accepted yet (SubjectInvite code).
- "subject_linked": the person linked their own account (subject_user) and decides there.
- "requires_legal_review": the person cannot give consent and no reviewed legal basis exists; nothing is enabled
  until staff record one. A caregiver's help to operate a screen is never a legal authorization to decide.
Minors are not supported in this product (Meta prohibits integrated products directed at them), not even with a
guardian's authorization.

A general authorization never stands in for a specific one: each kind of transfer has its own purpose. Revoking or
declining bumps Profile.consent_epoch, so work started before cannot be presented as current (still_current).
Real (non-synthetic) data also needs the operator switch AINGEL_REAL_DATA=1.
"""

import os

from django.db import transaction
from django.db.models import F
from django.utils import timezone

TERMS_VERSION = "2026-10-30"
CONSENT_VERSION = "2026-10-30"

# Legacy coarse flags (kept so old rows and clients are readable; they no longer authorize anything).
KEYS = ("camera", "microphone", "meta_data")

# Each purpose: what it allows, which data, where it goes. Clients show and read these texts aloud.
PURPOSES = {
    "camera_local": {
        "to": "local",
        "es": ("Usar la cámara", "AINGEL abre la cámara del teléfono cuando se lo pides o durante la vigilancia continua. Esto solo no envía imágenes a nadie."),
        "en": ("Use the camera", "AINGEL opens the phone camera when you ask or during continuous watching. On its own this sends images to no one."),
    },
    "microphone_local": {
        "to": "local",
        "es": ("Usar el micrófono", "AINGEL escucha cuando le hablas, para conversar, subtitular o traducir a señas. Con este permiso AINGEL no envía audio a nadie. Para pasar tu voz a texto, el navegador o el teléfono usan su propio reconocimiento de voz, que puede ser un servicio de su fabricante; AINGEL lo indica antes de usarlo."),
        "en": ("Use the microphone", "AINGEL listens when you speak, to talk, caption or translate to signs. With this permission AINGEL sends audio to no one. To turn your voice into text, the browser or phone uses its own speech recognition, which may be its vendor's service; AINGEL says so before using it."),
    },
    "meta_conversation": {
        "to": "meta",
        "es": ("Enviar tus preguntas a Meta", "Las preguntas que haces a AINGEL y las frases que se traducen a señas se envían a Meta Muse Spark para responder. Puede buscar en la web si hace falta."),
        "en": ("Send your questions to Meta", "The questions you ask AINGEL and the sentences translated to signs are sent to Meta Muse Spark to answer. It may search the web when needed."),
    },
    "meta_photos": {
        "to": "meta",
        "es": ("Enviar fotos a Meta", "Las fotos de la cámara que pides describir, o para buscar un objeto, se envían a Meta para analizarlas. AINGEL no las guarda."),
        "en": ("Send photos to Meta", "Camera photos you ask to describe, or to find an object, are sent to Meta to be analysed. AINGEL does not keep them."),
    },
    "meta_video": {
        "to": "meta",
        "es": ("Enviar videos cortos a Meta", "En la vigilancia continua con video (experimental), clips de pocos segundos se envían a Meta para entender qué cambia. AINGEL no los guarda."),
        "en": ("Send short videos to Meta", "In continuous watching with video (experimental), clips of a few seconds are sent to Meta to understand what changes. AINGEL does not keep them."),
    },
    "meta_voice": {
        "to": "meta",
        "es": ("Enviar voz a Meta", "El audio del micrófono para subtítulos en vivo se envía a Meta para transcribirlo. AINGEL no lo guarda."),
        "en": ("Send voice to Meta", "Microphone audio for live captions is sent to Meta to be transcribed. AINGEL does not keep it."),
    },
    "profile_personalization": {
        "to": "meta",
        "es": ("Personalizar con tu perfil", "Los apoyos indicados y las alergias de tu perfil acompañan tus preguntas a Meta para adaptar las respuestas. Nunca se envían nombres, rutinas, mensajes ni recuerdos."),
        "en": ("Personalize with your profile", "The support needs and allergies in your profile go with your questions to Meta to tailor answers. Names, routines, messages and memories are never sent."),
    },
    "face_local": {
        "to": "aingel",
        "es": ("Reconocer a tu familia", "Las caras de familiares que se inscribieron con su permiso se comparan en el servidor de AINGEL, no en Meta. Es una coincidencia posible, no una identificación."),
        "en": ("Recognize your family", "Faces of relatives who enrolled with their permission are compared on AINGEL's server, not at Meta. It is a possible match, not an identification."),
    },
}
CREDITS_NOTICE = {
    "es": "Mientras la cuenta de AINGEL use créditos gratuitos de Meta, Meta advierte que puede usar el contenido para mejorar sus productos.",
    "en": "While AINGEL's account uses Meta free credits, Meta warns it may use the content to improve its products.",
}
NEEDS = {
    "conversation": ("meta_conversation",),
    "personalization": ("meta_conversation", "profile_personalization"),
    "image": ("camera_local", "meta_photos"),
    "audio": ("microphone_local", "meta_voice"),
    "video": ("camera_local", "meta_video"),
}
DECISIONS = {"grant": "granted", "decline": "declined", "revoke": "revoked"}


# --- Accounts --------------------------------------------------------------------------------------------------

def adult_declared(user):
    if user is None or not getattr(user, "is_authenticated", False) or user.pk is None:
        return False
    from .models import AccountPolicy

    return AccountPolicy.objects.filter(user=user, adult_declared_at__isnull=False).exists()


def declare_adult(user, terms_version):
    from .models import AccountPolicy

    AccountPolicy.objects.update_or_create(
        user=user, defaults={"adult_declared_at": timezone.now(), "terms_version": terms_version, "declaration": "self_declaration"}
    )


def meta_user_allowed(user):
    """Production Meta access is restricted to explicitly listed account IDs.

    No account is implicitly privileged; an empty list denies every real Meta
    request. Use numeric IDs obtained only after creating a trusted account,
    avoiding username squatting and case-normalization problems.
    """
    if os.environ.get("AINGEL_ENV", "local") != "production" or os.environ.get("AINGEL_AI_MODE", "mock") != "meta":
        return True
    if not user or not user.is_authenticated or not user.is_active or user.pk is None:
        return False
    allowed = {item.strip() for item in os.environ.get("AINGEL_META_ALLOWED_USER_IDS", "").split(",")}
    # A public demo must be an explicit operator choice, and only enables the
    # server's own synthetic fixtures (assistance.synthetic); clients cannot declare content synthetic.
    public_synthetic_demo = (
        "*" in allowed
        and os.environ.get("AINGEL_SYNTHETIC_TESTS_ONLY") == "1"
        and os.environ.get("AINGEL_REAL_DATA") == "0"
        and os.environ.get("AINGEL_PRIVATE_OWN_MEDIA_TEST", "0") == "0"
    )
    return public_synthetic_demo or str(user.pk) in allowed


def meta_account_denial(user):
    """Why this account may not use a Meta endpoint at all (synthetic tests included), or None."""
    if os.environ.get("AINGEL_AI_MODE", "mock") == "meta" and not adult_declared(user):
        return "adult_declaration_required"
    if not meta_user_allowed(user):
        return "meta_access_denied"
    return None


# The notice shown before the browser's speech recognition may use its vendor's service (web/.../browserSpeech.ts).
SPEECH_SERVICE_VERSION = "2026-10-30"


def speech_service_accepted(user):
    """The account holder accepted the current notice: their voice may go to the browser vendor's recognition."""
    if user is None or not getattr(user, "is_authenticated", False) or user.pk is None:
        return False
    from .models import AccountPolicy

    return AccountPolicy.objects.filter(user=user, speech_service_accepted_at__isnull=False,
                                        speech_service_version=SPEECH_SERVICE_VERSION).exists()


def decide_speech_service(user, accept):
    from .models import AccountPolicy

    AccountPolicy.objects.update_or_create(user=user, defaults={
        "speech_service_accepted_at": timezone.now() if accept else None,
        "speech_service_version": SPEECH_SERVICE_VERSION if accept else "",
    })


# --- People and their decisions --------------------------------------------------------------------------------

def subject_account(profile):
    """The account of the person the profile describes, when that person can decide; otherwise None."""
    if profile is None:
        return None
    if profile.subject_status == "self":
        return profile.owner
    if profile.subject_status == "subject_linked":
        return profile.subject_user
    return None


def current_grants(profile):
    """{purpose: status} from the latest decision per purpose."""
    states = {}
    for grant in profile.consent_grants.order_by("decided_at"):
        states[grant.purpose] = grant.status
    return states


def granted(profile, purposes):
    states = current_grants(profile)
    return all(states.get(p) == "granted" for p in purposes)


def refused(profile, purpose):
    """The person explicitly declined or revoked [purpose]: nothing of that kind is captured for them, not even for a
    local test server. (Starting a capture also needs the grant: the clients check it before opening anything.)"""
    return profile is not None and current_grants(profile).get(purpose) in ("declined", "revoked")


def decide(profile, user, purpose, decision, method="own_account"):
    """Record the person's own decision. Returns an error code, or None when recorded."""
    from .models import ConsentGrant, Profile

    if purpose not in PURPOSES or decision not in DECISIONS:
        return "consent_request_invalid"
    if profile.subject_status == "requires_legal_review":
        return "legal_review_required"
    if profile.subject_status == "pending_confirmation":
        return "subject_confirmation_required"
    subject = subject_account(profile)
    if subject is None or subject.pk != user.pk:
        return "consent_subject_only"
    if not adult_declared(user):
        return "adult_declaration_required"
    with transaction.atomic():
        ConsentGrant.objects.create(profile=profile, purpose=purpose, status=DECISIONS[decision],
                                    version=CONSENT_VERSION, decided_by=user, method=method)
        if decision != "grant":
            Profile.objects.filter(pk=profile.pk).update(consent_epoch=F("consent_epoch") + 1)
    return None


def confirm_subject(profile, user, for_self, subject_adult):
    """The owner states, explicitly, whose data the profile holds. Returns an error code, or None when recorded."""
    from .models import Profile

    if profile.owner_id != user.pk:
        return "permission_denied"
    if profile.subject_status != "pending_confirmation":
        return "subject_already_confirmed"
    if for_self is True:
        if not adult_declared(user):
            return "adult_declaration_required"
        status = "self"
    elif for_self is False:
        if subject_adult is not True:
            return "subject_minor_not_supported"
        status = "pending_consent"
    else:
        return "consent_request_invalid"
    Profile.objects.filter(pk=profile.pk, subject_status="pending_confirmation").update(subject_status=status)
    return None


def still_current(profile, epoch):
    """False when a revocation happened after [epoch] was read: the result must not be shown as current."""
    from .models import Profile

    return Profile.objects.filter(pk=profile.pk, consent_epoch=epoch).exists()


def consent_state(profile, user, locale="es-EC"):
    language = "es" if locale == "es-EC" else "en"
    states = current_grants(profile)
    subject = subject_account(profile)
    return {
        "version": CONSENT_VERSION,
        "subject_status": profile.subject_status,
        # Moves on every decline or revocation: clients compare it during active captures and stop on a change.
        "epoch": profile.consent_epoch,
        "is_subject": subject is not None and subject.pk == user.pk,
        # Profiles from before the policy: only the owner can say whose data they hold.
        "can_confirm": profile.subject_status == "pending_confirmation" and profile.owner_id == user.pk,
        "subject_adult": subject is not None and adult_declared(subject),
        "purposes": [
            {"id": key, "to": value["to"], "title": value[language][0], "detail": value[language][1], "status": states.get(key, "pending")}
            for key, value in PURPOSES.items()
        ],
        "credits_notice": CREDITS_NOTICE[language],
    }


# --- Gates used by every Meta endpoint -------------------------------------------------------------------------

def clean_consents(value, user):
    """Legacy coarse consents (kept for old clients' reads); they no longer authorize anything."""
    if not isinstance(value, dict) or set(value) - set(KEYS) or not all(isinstance(value.get(k, False), bool) for k in KEYS):
        return None
    return {
        **{k: value.get(k, False) for k in KEYS},
        "version": "2026-10-29",
        "granted_at": timezone.now().isoformat(),
        "granted_by": user.get_username(),
    }


def real_data_enabled():
    return os.environ.get("AINGEL_REAL_DATA", "0") == "1"


def meta_allowed(profile, kind):
    """True when this profile's real data of [kind] may be sent to Meta: operator switch, an adult person who can
    decide, and that person's own grants for every purpose the kind needs."""
    # The private own-media test deliberately does not enable generic personal text,
    # including conversation/gloss, or the broader legacy real-data path.
    if os.environ.get("AINGEL_PRIVATE_OWN_MEDIA_TEST", "0") == "1":
        return False
    if profile is None or not real_data_enabled():
        return False
    subject = subject_account(profile)
    return subject is not None and adult_declared(subject) and granted(profile, NEEDS[kind])


def private_media_allowed(profile, user, kind, declared):
    """Opt-in owner-only test; declaration is not analysis of image or audio content."""
    if kind not in ("image", "audio", "video"):
        return False
    if not (
        os.environ.get("AINGEL_PRIVATE_OWN_MEDIA_TEST", "0") == "1"
        and real_data_enabled()
        and os.environ.get("AINGEL_SYNTHETIC_TESTS_ONLY", "1") == "0"
        and declared is True
        and profile is not None
        and user.is_authenticated
        and profile.owner_id == user.id
        and profile.subject_status == "self"
    ):
        return False
    return adult_declared(user) and granted(profile, NEEDS[kind])
