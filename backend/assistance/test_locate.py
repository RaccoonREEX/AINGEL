import os
from unittest.mock import patch

from django.test import SimpleTestCase
from .locate import locate_object, parse_segmentation
from .scene import SceneUnavailable


class LocateTests(SimpleTestCase):
    def test_empty_completed_lane_means_no_matches(self):
        self.assertEqual(parse_segmentation("", (640, 480)), [])

    def test_malformed_geometry_fails_closed(self):
        with self.assertRaises(SceneUnavailable):
            parse_segmentation("not geometry", (640, 480))

    @patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"})
    def test_mock_does_not_claim_object_was_detected(self):
        result = locate_object(b"fixture", "keys", True)
        self.assertFalse(result["analyzed"])
        self.assertEqual(result["matches"], [])
        self.assertIsNone(result["model"])

    @patch.dict(os.environ, {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic"})
    def test_non_synthetic_input_blocked(self):
        with self.assertRaisesRegex(SceneUnavailable, "privacy_review_required"):
            locate_object(b"fixture", "keys", False)
