"""Download official OpenCV weights, pin commit and validate Git LFS SHA-256."""

import hashlib
import json
from pathlib import Path
import re

import httpx


def main():
    project = Path(__file__).resolve().parents[2]
    output = project / ".local" / "face-models"
    output.mkdir(parents=True, exist_ok=True)
    licenses = project / "docs" / "licenses"
    licenses.mkdir(exist_ok=True)
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        manifest_path = project / "docs" / "FACE_MODELS.json"
        if manifest_path.exists():
            commit = json.loads(manifest_path.read_text(encoding="utf-8"))["upstream_commit"]
            if not re.fullmatch(r"[a-f0-9]{40}", commit):
                raise RuntimeError("Invalid pinned model commit")
        else:
            response = client.get("https://api.github.com/repos/opencv/opencv_zoo/commits/main")
            response.raise_for_status()
            commit = response.json()["sha"]
        records = []
        for family, name in [
            ("face_detection_yunet", "face_detection_yunet_2023mar.onnx"),
            ("face_recognition_sface", "face_recognition_sface_2021dec.onnx"),
        ]:
            source = f"https://raw.githubusercontent.com/opencv/opencv_zoo/{commit}/models/{family}"
            license_response = client.get(source + "/LICENSE")
            license_response.raise_for_status()
            (licenses / (family + ".txt")).write_text(
                license_response.text, encoding="utf-8"
            )
            pointer = client.get(source + "/" + name)
            pointer.raise_for_status()
            match = re.search(r"oid sha256:([a-f0-9]{64})", pointer.text)
            if not match:
                raise RuntimeError("Expected official Git LFS pointer")
            expected = match.group(1)
            url = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{commit}/models/{family}/{name}"
            dest = output / name
            if (
                not dest.exists()
                or hashlib.sha256(dest.read_bytes()).hexdigest() != expected
            ):
                data = client.get(url)
                data.raise_for_status()
                if (
                    len(data.content) > 50 * 1024 * 1024
                    or hashlib.sha256(data.content).hexdigest() != expected
                ):
                    raise RuntimeError("Model size/hash check failed")
                dest.write_bytes(data.content)
            records.append(
                {
                    "name": name,
                    "sha256": expected,
                    "source": url,
                    "license": (
                        "MIT" if family == "face_detection_yunet" else "Apache-2.0"
                    ),
                }
            )
    manifest = {
        "upstream_commit": commit,
        "models": records,
        "note": "Model weights only, not biometric training datasets. Quality and bias require local evaluation before use.",
    }
    (project / "docs" / "FACE_MODELS.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Two official OpenCV models installed locally; SHA-256 checks passed. No faces or biometric datasets downloaded."
    )


if __name__ == "__main__":
    main()
