from django.urls import path

from . import auth, consent_views, views, mfa, faces, knowledge, signs
from assistance.companion import chat
from assistance.conversation import conversation
from assistance.gloss import gloss

urlpatterns = [
    path("auth/session/", auth.session),
    path("auth/login/", auth.authenticate_user),
    path("auth/register/", auth.authenticate_user, {"register": True}),
    path("auth/logout/", auth.sign_out),
    path("auth/adult/", auth.declare),
    path("auth/mfa/verify/", mfa.verify_challenge),
    path("auth/mfa/status/", mfa.mfa_status),
    path("auth/mfa/setup/", mfa.mfa_setup),
    path("auth/mfa/enable/", mfa.mfa_enable),
    path("auth/mfa/disable/", mfa.mfa_disable),
    path("profiles/", views.profiles),
    path("invites/accept/", views.accept_invite),
    path("profiles/<uuid:profile_id>/", views.profile_detail),
    path("profiles/<uuid:profile_id>/communication/", views.communication),
    path("profiles/<uuid:profile_id>/resources/search/", knowledge.resources),
    path("profiles/<uuid:profile_id>/companion/chat/", chat),
    path("profiles/<uuid:profile_id>/conversation/", conversation),
    path("profiles/<uuid:profile_id>/consent/", consent_views.consent),
    path("profiles/<uuid:profile_id>/consent/invite/", consent_views.invite),
    path("profiles/<uuid:profile_id>/consent/legal-review/", consent_views.legal_review),
    path("consent/redeem/", consent_views.redeem),
    path("consent/purposes/", consent_views.purposes),
    path("profiles/<uuid:profile_id>/signs/catalog/", signs.catalog),
    path("profiles/<uuid:profile_id>/signs/lookup/", signs.lookup),
    path("profiles/<uuid:profile_id>/signs/gloss/", gloss),
    path("profiles/<uuid:profile_id>/signs/clips/<str:clip_id>/", signs.clip_content),
    path("profiles/<uuid:profile_id>/circle/", views.circle),
    path("profiles/<uuid:profile_id>/circle/<uuid:member_id>/", views.membership),
    path(
        "profiles/<uuid:profile_id>/invitations/<uuid:invitation_id>/",
        views.cancel_invite,
    ),
    path("profiles/<uuid:profile_id>/routines/", views.routines),
    path(
        "profiles/<uuid:profile_id>/routines/<uuid:routine_id>/", views.routine_detail
    ),
    path(
        "profiles/<uuid:profile_id>/routines/<uuid:routine_id>/confirm/",
        views.routine_confirm,
    ),
    path("profiles/<uuid:profile_id>/messages/", views.messages),
    path(
        "profiles/<uuid:profile_id>/messages/<uuid:message_id>/", views.message_delete
    ),
    path("profiles/<uuid:profile_id>/memories/", views.memories),
    path("profiles/<uuid:profile_id>/memories/<uuid:memory_id>/", views.memory_detail),
    path("profiles/<uuid:profile_id>/ask/", views.ask),
    path("profiles/<uuid:profile_id>/audit/", views.audit_events),
    path("profiles/<uuid:profile_id>/faces/", faces.family_faces),
    path("profiles/<uuid:profile_id>/faces/consent/", faces.face_consent),
    path("profiles/<uuid:profile_id>/faces/recognize/", faces.recognize_family),
]
