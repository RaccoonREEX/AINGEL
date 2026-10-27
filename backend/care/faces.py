"""Opt-in, one-profile family matching. No cloud calls and no face-photo persistence."""

from datetime import timedelta
import hashlib
import json
import threading

import cv2
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone
import numpy as np
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.decorators import throttle_classes

from assistance.scene import normalize_image
from .crypto import decrypt, encrypt
from .models import FamilyFace, Profile
from .permissions import access, audit

_lock = threading.Lock()


class FaceRate(UserRateThrottle):
    scope = "face"


def embeddings(image_bytes):
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
                "enabled": profile.face_recognition_enabled,
                "enrollments": [enrollment_data(x) for x in faces],
                "can_enroll": profile.members.filter(user=request.user).exists(),
            }
        )
    member = profile.members.filter(user=request.user).first()
    if not member:
        raise PermissionDenied("self_enrollment_requires_membership")
    if request.method == "DELETE":
        FamilyFace.objects.filter(member=member).delete()
        audit(profile, request.user, "face.consent_revoked", member.id)
        return Response(status=204)
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
        if (
            not locked.face_recognition_enabled
            or not locked.members.filter(pk=member.pk).exists()
        ):
            raise ValidationError("face_feature_disabled")
        face, _ = FamilyFace.objects.update_or_create(
            member=member,
            defaults={
                "display_name": label.strip(),
                "embedding_encrypted": encrypt(
                    json.dumps({"version": 2, "samples": samples})
                ),
                "expires_at": timezone.now() + timedelta(days=30),
                "consented_at": timezone.now(),
            },
        )
    audit(profile, request.user, "face.consented_enrolled", member.id)
    return Response(enrollment_data(face), status=201)


@api_view(["POST"])
def face_consent(request, profile_id):
    profile = access(request.user, profile_id, "owner")
    enabled = request.data.get("enabled")
    if type(enabled) is not bool:
        raise ValidationError("face_consent_required")
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
    profile = access(request.user, profile_id, "owner")
    if not profile.face_recognition_enabled:
        raise ValidationError("face_feature_disabled")
    if request.data.get("consent") not in [True, "true"]:
        raise ValidationError("face_capture_consent_required")
    image = request.FILES.get("image")
    if not image:
        raise ValidationError("image_required")
    faces = FamilyFace.objects.filter(
        member__profile=profile, expires_at__gt=timezone.now()
    ).select_related("member__user")
    candidates = []
    try:
        for face in faces:
            candidates.append(
                {
                    "id": str(face.id),
                    "display_name": face.display_name,
                    "relationship": face.member.relationship,
                    "samples": decode_samples(face.embedding_encrypted),
                }
            )
        detected = embeddings(normalize_image(image))
    except (ValueError, cv2.error, InvalidToken):
        raise ValidationError("face_processing_failed") from None
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
    audit(profile, request.user, "face.local_match_requested")
    return Response(
        {
            "mode": "local_experimental",
            "faces": results,
            "warning_code": "possible_match_not_verified_identity",
        }
    )
