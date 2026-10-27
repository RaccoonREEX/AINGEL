"""Opt-in live Meta smoke check using an original, synthetic image only.

The key is read from a local file into process memory, never printed or saved.
Run from backend/: python scripts/smoke_meta.py --key-file <local-file>
"""

import argparse
import io
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--locate", action="store_true")
    args = parser.parse_args()
    try:
        content = args.key_file.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError):
        print(json.dumps({"error": "credential_file_unreadable"}))
        return 1
    candidates = set(re.findall(r"LLM_[A-Za-z0-9_-]+", content))
    if len(candidates) != 1:
        print(json.dumps({"error": "credential_file_format_invalid"}))
        return 1
    os.environ["MODEL_API_KEY"] = candidates.pop()
    del content, candidates
    os.environ["AINGEL_AI_MODE"] = "meta"
    os.environ["AINGEL_SYNTHETIC_TESTS_ONLY"] = "1"
    try:
        import django

        django.setup()
        from django.contrib.auth import get_user_model
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image, ImageDraw
        from rest_framework.test import APIClient

        image = Image.new("RGB", (640, 480), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((60, 150, 220, 310), fill="blue")
        draw.ellipse((380, 150, 540, 310), fill="red")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        client = APIClient()
        # Exercise the real Django endpoint without creating a persistent user/session.
        client.force_authenticate(get_user_model()(pk=1, username="synthetic-smoke"))
        response = client.post(
            "/api/v1/locate/" if args.locate else "/api/v1/scene/",
            {
                "image": SimpleUploadedFile(
                    "synthetic-shapes.png", buffer.getvalue(), "image/png"
                ),
                "locale": "es-EC",
                "synthetic": "true",
                **({"object_name": "red circle"} if args.locate else {}),
            },
            format="multipart",
        )
        result = {
            "fixture": "original 640x480 white canvas, blue square left, red circle right",
            "transport": "Django APIClient -> scene endpoint -> actual Meta HTTPS API",
            "http_status": response.status_code,
            "result": (
                response.data
                if not args.locate or response.status_code != 200
                else {
                    **response.data,
                    "matches": [
                        {
                            **{k: v for k, v in match.items() if k != "mask_png"},
                            "mask_decoded": match["mask_png"].startswith(
                                "data:image/png;base64,"
                            ),
                        }
                        for match in response.data["matches"]
                    ],
                }
            ),
        }
        if args.report:
            args.report.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(result, ensure_ascii=True))
        return (
            0
            if response.status_code == 200 and response.data.get("mode") == "meta"
            else 1
        )
    finally:
        os.environ.pop("MODEL_API_KEY", None)


if __name__ == "__main__":
    raise SystemExit(main())
