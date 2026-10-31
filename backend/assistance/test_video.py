import os
import tempfile
from unittest.mock import patch

import cv2
import numpy as np
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from care.consent import decide
from care.models import Profile
from care.testing import adult, authorize

from .video import MAX_CLIP_BYTES, MemoryClipHandler, describe_changes, mp4_info

META = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_VIDEO_CLIPS": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "1"}


def synthetic_clip(seconds=6, fps=10):
    """An original synthetic MP4 with real motion: a square crossing the frame (not a repeated photo)."""
    path = os.path.join(tempfile.mkdtemp(), "clip.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    for i in range(int(seconds * fps)):
        frame = np.full((240, 320, 3), 235, np.uint8)
        x = 10 + i * 4
        cv2.rectangle(frame, (x, 90), (x + 50, 140), (40, 40, 200), -1)
        writer.write(frame)
    writer.release()
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


CLIP = synthetic_clip()
DOOR = [{"kind": "opened", "what": "la puerta", "certainty": "observed"}]


class VideoClipTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = adult(get_user_model().objects.create_user(username="video-owner"))
        self.profile = authorize(Profile.objects.create(owner=self.owner, display_name="Video"), {"camera": True, "meta_data": True})
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def post(self, seq=1, clip=CLIP, synthetic=True, env=META, events=DOOR, say="Se abrió la puerta.", **extra):
        data = {"clip": SimpleUploadedFile("clip.mp4", clip, content_type="video/mp4"), "locale": "es-EC",
                "session": "watch-session-1", "seq": seq, "synthetic": synthetic, **extra}
        with patch.dict(os.environ, env), patch("assistance.video.describe_changes", return_value=(events, say, {"meta_inference_ms": 5})) as call:
            return self.client.post("/api/v1/vision/clip/", data, format="multipart"), call

    def test_the_synthetic_clip_is_a_real_video_with_motion(self):
        info = mp4_info(CLIP)
        self.assertTrue(info["video"])
        self.assertAlmostEqual(info["seconds"], 6, delta=0.3)
        self.assertIsNone(mp4_info(b"\xff\xd8\xff" + b"0" * 2000))  # a JPEG is not a clip

    def test_off_by_default_and_only_valid_clips(self):
        response, call = self.post(env={**META, "AINGEL_VIDEO_CLIPS": "0"})
        self.assertEqual((response.status_code, response.data), (404, {"error": "video_disabled"}))
        self.assertEqual(self.post(clip=b"not a video" * 50)[0].data, {"error": "clip_invalid"})
        self.assertEqual(self.post(clip=synthetic_clip(seconds=12))[0].data, {"error": "clip_duration_invalid"})
        call.assert_not_called()

    def test_changes_are_announced_once_and_old_clips_are_dropped(self):
        first, _ = self.post(seq=1)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual((first.data["events"], first.data["say"], first.data["ai_generated"]), (DOOR, "Se abrió la puerta.", True))
        again, call = self.post(seq=2)  # the model reports the same door: not repeated
        self.assertEqual((again.data["events"], again.data["say"]), ([], ""))
        self.assertEqual(call.call_args.args[2][0]["what"], "la puerta")  # recent context went with the clip
        stale, call = self.post(seq=1)
        self.assertEqual(stale.data, {"stale": True, "events": [], "say": ""})
        call.assert_not_called()

    def test_backpressure_and_quota(self):
        cache.add(f"video-busy:{self.owner.pk}", True, 90)
        self.assertEqual(self.post()[0].data, {"error": "video_busy"})
        cache.clear()
        self.assertEqual(self.post(env={**META, "AINGEL_VIDEO_MAX_PER_HOUR": "1"}, seq=1)[0].status_code, 200)
        self.assertEqual(self.post(env={**META, "AINGEL_VIDEO_MAX_PER_HOUR": "1"}, seq=2)[0].data, {"error": "video_quota_exceeded"})

    def test_real_clips_need_the_operator_switch_and_the_persons_video_grant(self):
        real_env = {**META, "AINGEL_SYNTHETIC_TESTS_ONLY": "0", "AINGEL_REAL_DATA": "1"}
        refused, call = self.post(synthetic=False, profile=str(self.profile.pk), env=real_env)
        self.assertEqual(refused.data, {"error": "privacy_review_required"})  # AINGEL_VIDEO_REAL off by default
        call.assert_not_called()
        allowed_env = {**real_env, "AINGEL_VIDEO_REAL": "1"}
        self.assertEqual(self.post(synthetic=False, profile=str(self.profile.pk), env=allowed_env)[0].status_code, 200)
        decide(self.profile, self.owner, "meta_video", "revoke")
        self.assertEqual(self.post(seq=2, synthetic=False, profile=str(self.profile.pk), env=allowed_env)[0].data, {"error": "privacy_review_required"})

    def test_a_revocation_during_inference_drops_the_result(self):
        allowed_env = {**META, "AINGEL_SYNTHETIC_TESTS_ONLY": "0", "AINGEL_REAL_DATA": "1", "AINGEL_VIDEO_REAL": "1"}

        def revoke(*args, **kwargs):
            decide(self.profile, self.owner, "meta_video", "revoke")
            return DOOR, "Se abrió la puerta.", {}

        data = {"clip": SimpleUploadedFile("clip.mp4", CLIP, content_type="video/mp4"), "locale": "es-EC",
                "session": "watch-session-1", "seq": 1, "profile": str(self.profile.pk)}
        with patch.dict(os.environ, allowed_env), patch("assistance.video.describe_changes", side_effect=revoke):
            response = self.client.post("/api/v1/vision/clip/", data, format="multipart")
        self.assertEqual((response.status_code, response.data), (409, {"error": "consent_changed"}))

    def test_clips_stay_in_memory(self):
        handler = MemoryClipHandler(None)
        handler.handle_raw_input(None, {}, MAX_CLIP_BYTES, b"x")
        self.assertTrue(handler.activated)  # larger than Django's 2.5 MB default, still never written to disk
        handler.handle_raw_input(None, {}, MAX_CLIP_BYTES * 2, b"x")
        self.assertFalse(handler.activated)

    def test_meta_receives_the_mp4_inline_or_via_files_with_deletion(self):
        class Reply:
            def __init__(self, data):
                self.data = data

            def raise_for_status(self):
                pass

            def json(self):
                return self.data

        answer = {"status": "completed", "output": [{"type": "function_call", "name": "report_changes",
                                                     "arguments": '{"events":[{"kind":"moved","what":"un cuadrado","certainty":"observed"}],"say":"Un cuadrado se movió."}'}]}
        with patch.dict(os.environ, {"MODEL_API_KEY": "synthetic-key"}), patch("assistance.video.httpx.Client") as client:
            http = client.return_value.__enter__.return_value
            http.post.return_value = Reply(answer)
            events, say, _ = describe_changes(CLIP, "es-EC", [], {})
            payload = http.post.call_args.kwargs["json"]
            video = payload["input"][0]["content"][1]
            self.assertEqual(video["type"], "input_video")
            self.assertTrue(video["video_url"].startswith("data:video/mp4;base64,"))
            self.assertEqual((payload["store"], events[0]["kind"], say), (False, "moved", "Un cuadrado se movió."))
            http.post.side_effect = [Reply({"id": "file-123"}), Reply(answer)]
            describe_changes(CLIP, "es-EC", [], {}, transport="files")
            upload = http.post.call_args_list[-2]
            self.assertEqual(upload.kwargs["data"]["purpose"], "user_data")
            self.assertEqual(http.post.call_args.kwargs["json"]["input"][0]["content"][1], {"type": "input_video", "file_id": "file-123"})
            http.delete.assert_called_once()
            self.assertIn("file-123", http.delete.call_args.args[0])


    def test_a_test_server_validates_the_clip_without_calling_meta(self):
        response, call = self.post(env={**META, "AINGEL_AI_MODE": "mock"})
        self.assertEqual((response.status_code, response.data["mode"], response.data["events"]), (200, "mock", []))
        call.assert_not_called()

    def test_clips_use_the_global_meta_quota(self):
        from .meta_quota import MetaQuotaError
        from .video import VideoUnavailable
        with patch("assistance.video.reserve_meta_call", side_effect=MetaQuotaError("meta_quota_exceeded")),                 patch("assistance.video.httpx.Client") as client, patch.dict(os.environ, {"MODEL_API_KEY": "synthetic-key"}):
            with self.assertRaisesMessage(VideoUnavailable, "meta_quota_exceeded"):
                describe_changes(CLIP, "es-EC", [], {})
            client.assert_not_called()
