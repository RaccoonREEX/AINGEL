"""Live check, synthetic only: Meta receives a real MP4 with motion and answers about what changed over time.

Usage: python scripts/smoke_video.py --key-file <file with one LLM_ key> [--transport inline|files]
The clip is generated here (a blue square entering from the left and crossing a grey table line); no camera, no
person, no personal data. Prints the events, the sentence to speak and the timings; never prints the key.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np


def synthetic_clip(seconds=6, fps=10):
    path = os.path.join(tempfile.mkdtemp(), "smoke.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (480, 320))
    for i in range(seconds * fps):
        frame = np.full((320, 480, 3), 230, np.uint8)
        cv2.rectangle(frame, (0, 220), (480, 235), (120, 120, 120), -1)  # a table edge
        if i >= fps:  # nothing during the first second, then the square enters and crosses
            x = -60 + (i - fps) * 9
            cv2.rectangle(frame, (x, 150), (x + 60, 210), (200, 80, 20), -1)
        writer.write(frame)
    writer.release()
    data = Path(path).read_bytes()
    os.remove(path)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--transport", choices=["inline", "files"], default="inline")
    args = parser.parse_args()
    keys = set(re.findall(r"LLM_[A-Za-z0-9_-]+", args.key_file.read_text(encoding="utf-8-sig")))
    if len(keys) != 1:
        print(json.dumps({"error": "credential_file_format_invalid"}))
        return 1
    os.environ["MODEL_API_KEY"] = keys.pop()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_SECRET_KEY", "smoke-only")
    import django

    django.setup()
    from assistance.persona import profile_preferences
    from assistance.video import describe_changes, mp4_info

    clip = synthetic_clip()
    events, say, timings = describe_changes(clip, "es-EC", [], profile_preferences({}), args.transport)
    print(json.dumps({"clip": {**mp4_info(clip), "bytes": len(clip)}, "events": events, "say": say, "timings": timings}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
