"""Opt-in, one-profile family matching. No cloud calls and no face-photo persistence.

Hotfix 31-10-2026: the whole module sits behind the server switch AINGEL_FACE_RECOGNITION_ENABLED, off unless it is
exactly "1". While off, nothing detects faces, computes or compares templates, or enrolls anyone: every entry point
refuses before reading the image, and embeddings() itself refuses before loading a model. Looking at the state and
withdrawing (turning the feature off, deleting one's own enrollment) keep working; stored templates are deleted only
when someone asks.

Matching checks the authorization before processing and again, under a row lock, after it: the profile's switch,
the person's own face_local grant, their consent epoch and each enrolled member's epoch. Any change in between
(a revocation while OpenCV ran) discards the result: nothing is returned, said or audited as a match.
"""

from datetime import timedelta
import hashlib
import json
import os
import threading

import cv2
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
import numpy as np
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.decorators import throttle_classes

from assistance.scene import normalize_image
from .consent import granted
from .crypto import decrypt, encrypt
from .models import FamilyFace, Profile
from .permissions import access, audit

_lock = threading.Lock()


class FaceRate(UserRateThrottle):
    scope = "face"


class FaceRecognitionDisabled(Exception):
    pass


class FaceConsentChanged(Exception):
    pass


def recognition_enabled():
    """The server switch; off by default (hotfix 31-10-2026)."""
    return os.environ.get("AINGEL_FACE_RECOGNITION_ENABLED", "0") == "1"


def require_enabled():
    if not recognition_enabled():
        raise FaceRecognitionDisabled("face_recognition_disabled")


DISABLED = {"error": "face_recognition_disabled"}


def embeddings(image_bytes):
    require_enabled()  # the last line of defence: no model is loaded and no face is detected while off
    root = settings.BASE_DIR.parent / ".local" / "face-models"
    detector_path = root / "face_detection_yunet_2023mar.onnx"
    recognizer_path = root / "face_recognition_sface_2021dec.onnx"
    if not detector_path.exists() or not recognizer_path.exists():
        raise ValidationError("face_models_not_installed")
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValidationError("image_invalid")
    h, w = image.shape[:2]
    with _lock:
        detector = cv2.FaceDetectorYN.create(
            str(detector_path), "", (w, h), 0.9, 0.3, 1000
        )
        _, faces = detector.detect(image)
        if faces is None:
            return []
        if len(faces) > 8:
            raise ValidationError("face_too_many")
        recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
        result = []
        for face in faces:
            if min(face[2], face[3]) < 64:
                continue
            aligned = recognizer.alignCrop(image, face)
            feature = recognizer.feature(aligned).flatten().astype(np.float32)
            norm = float(np.linalg.norm(feature))
            if feature.size != 128 or not np.isfinite(feature).all() or norm <= 0:
                raise ValidationError("face_embedding_invalid")
            result.append(
                {
                    "embedding": (feature / norm).tolist(),
                    "sharpness": float(
                        cv2.Laplacian(
                            cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY), cv2.CV_64F
                        ).var()
                    ),
                    "box": [
                        max(0, float(face[0]) / w),
                        max(0, float(face[1]) / h),
                        min(1, float(face[0] + face[2]) / w),
                        min(1, float(face[1] + face[3]) / h),
                    ],
                }
            )
        return result


def candidate_match(query, candidates):
    scores = []
    for candidate in candidates:
        samples = candidate.get("samples") or [candidate["embedding"]]
        similarities = sorted(
            (
                float(
                    np.dot(
                        np.asarray(query, dtype=np.float32),
                        np.asarray(sample, dtype=np.float32),
                    )
                )
                for sample in samples
            ),
            reverse=True,
        )
        # One score per person: extra samples cannot hide an ambiguous second person.
        score = float(np.mean(similarities[:2]))
        scores.append((score, candidate))
    scores.sort(key=lambda pair: pair[0], reverse=True)
    if (
        not scores
        or scores[0][0] < 0.55
        or (len(scores) > 1 and scores[0][0] - scores[1][0] < 0.10)
    ):
        return None
    return scores[0][1]


def decode_samples(ciphertext):
    value = json.loads(decrypt(ciphertext))
    samples = (
        value.get("samples")
        if isinstance(value, dict) and value.get("version") == 2
        else [value]
    )
    matrix = np.asarray(samples, dtype=np.float32)
    if (
        matrix.ndim != 2
        or matrix.shape[1] != 128
        or not 1 <= len(matrix) <= 3
        or not np.isfinite(matrix).all()
    ):
        raise ValueError("invalid_face_template")
    norms = np.linalg.norm(matrix, axis=1)
    if np.any(norms <= 0):
        raise ValueError("invalid_face_template")
    return (matrix / norms[:, None]).tolist()


def enrollment_data(face):
    try:
        sample_count = len(decode_samples(face.embedding_encrypted))
    except (ValueError, TypeError, InvalidToken):
        # Leave revocation available if a stored template/key is damaged.
        sample_count = 0
    return {
        "id": face.id,
        "sample_count": sample_count,
        "member_id": face.member_id,
        "username": face.member.user.username,
        "display_name": face.display_name,
        "relationship": face.member.relationship,
        "consented_at": face.consented_at,
        "expires_at": face.expires_at,
    }


def authorization(profile_id):
    """What allows matching for this profile right now, read from the database (never from a request's stale copy)."""
    profile = Profile.objects.get(pk=profile_id)
    return {
        "enabled": profile.face_recognition_enabled,
        "granted": granted(profile, ("face_local",)),
        "epoch": profile.consent_epoch,
        "members": {
            str(face.id): face.member.face_consent_epoch
            for face in FamilyFace.objects.filter(member__profile=profile, expires_at__gt=timezone.now()).select_related("member")
        },
    }


def family_matches(profile, image):
    """Enrolled family members found in [image] (normalized JPEG bytes), matched here with OpenCV: no cloud call.
    Each detected face gets its box and a candidate (id, display_name, relationship) or None.
    Raises FaceRecognitionDisabled (switch off), ValidationError face_consent_required (not authorized before
    processing) or FaceConsentChanged (revoked while processing: the result is discarded)."""
    require_enabled()
    before = authorization(profile.pk)
    if not before["enabled"] or not before["granted"]:
        raise ValidationError("face_consent_required")  # checked before any face is detected
    faces = FamilyFace.objects.filter(
        pk__in=list(before["members"]), expires_at__gt=timezone.now()
    ).select_related("member__user")
    candidates = [
        {
            "id": str(face.id),
            "display_name": face.display_name,
            "relationship": face.member.relationship,
            "samples": decode_samples(face.embedding_encrypted),
            "consent_epoch": before["members"].get(str(face.id)),
        }
        for face in faces
    ]
    detected = embeddings(image)
    with transaction.atomic():
        # Serialized with every revocation (they lock the same row): a revocation committed while OpenCV ran is seen.
        Profile.objects.select_for_update().get(pk=profile.pk)
        after = authorization(profile.pk)
        if (
            not recognition_enabled()
            or not after["enabled"]
            or not after["granted"]
            or after["epoch"] != before["epoch"]
        ):
            raise FaceConsentChanged("face_consent_changed")
        candidates = [
            candidate
            for candidate in candidates
            if after["members"].get(candidate["id"]) == candidate["consent_epoch"]
        ]
        results = []
        for detection in detected:
            match = (
                candidate_match(detection["embedding"], candidates)
                if detection.get("sharpness", 100) >= 30
                else None
            )
            results.append(
                {
                    "box": detection["box"],
                    "candidate": (
                        {k: match[k] for k in ["id", "display_name", "relationship"]}
                        if match
                        else None
                    ),
                }
            )
    return results


@api_view(["GET", "POST", "DELETE"])
@throttle_classes([FaceRate])
def family_faces(request, profile_id):
    profile = access(request.user, profile_id)
    if request.method == "GET":
        faces = FamilyFace.objects.filter(
            member__profile=profile, expires_at__gt=timezone.now()
        ).select_related("member__user")
        return Response(
            {
                # available: the server switch (hotfix); enabled: the profile's own setting, still visible and revocable.
                "available": recognition_enabled(),
                "enabled": profile.face_recognition_enabled,
                "enrollments": [enrollment_data(x) for x in faces],
                "can_enroll": profile.members.filter(user=request.user).exists(),
            }
        )
    member = profile.members.filter(user=request.user).first()
    if not member:
        raise PermissionDenied("self_enrollment_requires_membership")
    if request.method == "DELETE":
        with transaction.atomic():
            locked = Profile.objects.select_for_update().get(pk=profile.pk)
            member = locked.members.filter(user=request.user).first()
            if not member:
                raise PermissionDenied("self_enrollment_requires_membership")
            member.face_consent_epoch += 1
            member.save(update_fields=["face_consent_epoch"])
            FamilyFace.objects.filter(member=member).delete()
        audit(profile, request.user, "face.consent_revoked", member.id)
        return Response(status=204)
    if not recognition_enabled():
        return Response(DISABLED, status=503)  # no new enrollment: nothing is read or processed
    if not profile.face_recognition_enabled:
        raise ValidationError("face_feature_disabled")
    if request.data.get("consent") not in [True, "true"] or request.data.get(
        "own_photo"
    ) not in [True, "true"]:
        raise ValidationError("face_consent_required")
    images = request.FILES.getlist("image")
    label = request.data.get("display_name", "")
    if (
        not 1 <= len(images) <= 3
        or not isinstance(label, str)
        or not label.strip()
        or len(label) > 100
    ):
        raise ValidationError("face_enrollment_invalid")
    if sum(image.size for image in images) > 5 * 1024 * 1024:
        raise ValidationError("face_images_too_large")
    samples = []
    initial_epoch = member.face_consent_epoch
    seen = set()
    try:
        for image in images:
            normalized = normalize_image(image)
            digest = hashlib.sha256(normalized).digest()
            if digest in seen:
                raise ValidationError("face_duplicate_photo")
            seen.add(digest)
            features = embeddings(normalized)
            if len(features) != 1:
                raise ValidationError("face_single_clear_face_required")
            if features[0].get("sharpness", 100) < 30:
                raise ValidationError("face_photo_blurry")
            sample = features[0]["embedding"]
            if any(float(np.dot(sample, previous)) < 0.4 for previous in samples):
                raise ValidationError("face_photos_inconsistent")
            samples.append(sample)
    except (ValueError, cv2.error):
        raise ValidationError("face_image_invalid") from None
    with transaction.atomic():
        locked = Profile.objects.select_for_update().get(pk=profile.pk)
        current_member = locked.members.filter(pk=member.pk).first()
        if (
            not recognition_enabled()
            or not locked.face_recognition_enabled
            or not current_member
            or current_member.face_consent_epoch != initial_epoch
        ):
            raise ValidationError("face_consent_changed")
        face, _ = FamilyFace.objects.update_or_create(
            member=current_member,
            defaults={
                "display_name": label.strip(),
                "embedding_encrypted": encrypt(
                    json.dumps({"version": 2, "samples": samples})
                ),
                "expires_at": timezone.now() + timedelta(days=30),
                "consented_at": timezone.now(),
            },
        )
        current_member.face_consent_epoch += 1
        current_member.save(update_fields=["face_consent_epoch"])
    audit(profile, request.user, "face.consented_enrolled", member.id)
    return Response(enrollment_data(face), status=201)


@api_view(["POST"])
def face_consent(request, profile_id):
    profile = access(request.user, profile_id, "owner")
    enabled = request.data.get("enabled")
    if type(enabled) is not bool:
        raise ValidationError("face_consent_required")
    if enabled and not recognition_enabled():
        return Response(DISABLED, status=503)  # it cannot be turned on; turning it off always works
    if enabled:
        password = request.data.get("password", "")
        if (
            not isinstance(password, str)
            or not request.user.check_password(password)
            or request.data.get("consent") is not True
        ):
            raise PermissionDenied("current_password_and_consent_required")
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(pk=profile.pk)
        if not enabled:
            profile.members.update(face_consent_epoch=F("face_consent_epoch") + 1)
            FamilyFace.objects.filter(member__profile=profile).delete()
        profile.face_recognition_enabled = enabled
        profile.save(update_fields=["face_recognition_enabled"])
    audit(
        profile,
        request.user,
        "face.feature_enabled" if enabled else "face.feature_disabled",
    )
    return Response({"enabled": enabled})


@api_view(["POST"])
@throttle_classes([FaceRate])
def recognize_family(request, profile_id):
    if not recognition_enabled():
        return Response(DISABLED, status=503)  # before the image is even read
    profile = access(request.user, profile_id, "owner")
    if not profile.face_recognition_enabled:
        raise ValidationError("face_feature_disabled")
    if request.data.get("consent") not in [True, "true"]:
        raise ValidationError("face_capture_consent_required")
    image = request.FILES.get("image")
    if not image:
        raise ValidationError("image_required")
    try:
        results = family_matches(profile, normalize_image(image))
    except FaceRecognitionDisabled:
        return Response(DISABLED, status=503)
    except FaceConsentChanged:
        return Response({"error": "face_consent_changed"}, status=409)  # revoked meanwhile: nothing is returned
    except (ValueError, cv2.error, InvalidToken):
        raise ValidationError("face_processing_failed") from None
    audit(profile, request.user, "face.local_match_requested")
    return Response(
        {
            "mode": "local_experimental",
            "faces": results,
            "warning_code": "possible_match_not_verified_identity",
        }
    )
