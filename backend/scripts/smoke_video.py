"""Live check, synthetic only: Meta receives a real MP4 with motion and answers about what changed over time.

Usage: python scripts/smoke_video.py --key-file <file with one LLM_ key> [--transport inline|files]
The clip is the server fixture (assistance.synthetic: a blue square entering from the left and crossing a grey
table line); no camera, no person, no personal data. Prints the events, the sentence to speak and the timings; never prints the key.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


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
    from assistance import synthetic
    from assistance.video import describe_changes, mp4_info

    clip = synthetic.clip("moving_square")
    events, say, timings = describe_changes(clip, "es-EC", [], synthetic.FICTIONAL_PREFERENCES, args.transport,
                                             basis=synthetic.FIXTURE)
    print(json.dumps({"clip": {**mp4_info(clip), "bytes": len(clip)}, "events": events, "say": say, "timings": timings}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
