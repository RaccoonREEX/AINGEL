"""Download licensed VizWiz VQA annotations only; no images or cloud inference."""

import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx


def main():
    source = "https://vizwiz.cs.colorado.edu/VizWiz_final/vqa_data/Annotations.zip"
    project = Path(__file__).resolve().parents[2]
    raw = bytearray()
    with httpx.stream("GET", source, timeout=60, follow_redirects=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw) > 25 * 1024 * 1024:
                raise RuntimeError("Annotation download exceeds limit")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [x for x in archive.infolist() if Path(x.filename).name == "val.json"]
        if len(names) != 1 or names[0].file_size > 25 * 1024 * 1024:
            raise RuntimeError("Unexpected annotation archive")
        data = json.loads(archive.read(names[0]))
    # Preserve a bounded local subset for later consent/privacy-screened image evaluation.
    unanswerable = [x for x in data if x.get("answerable") == 0][:15]
    answerable = [x for x in data if x.get("answerable") == 1][:15]
    subset = unanswerable + answerable
    output = project / ".local" / "datasets"
    output.mkdir(parents=True, exist_ok=True)
    (output / "vizwiz-vqa-eval.json").write_text(
        json.dumps(subset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "dataset": "VizWiz VQA validation annotations",
        "source": source,
        "official_page": "https://vizwiz.org/tasks-and-datasets/vqa/",
        "license": "CC-BY-4.0",
        "attribution": "Danna Gurari et al., VizWiz Grand Challenge: Answering Visual Questions from Blind People, CVPR 2018; VizWiz project",
        "archive_sha256": hashlib.sha256(raw).hexdigest(),
        "validation_records": len(data),
        "local_subset_records": len(subset),
        "unanswerable_subset": len(unanswerable),
        "answerable_subset": len(answerable),
        "images_downloaded": 0,
        "training_performed": False,
        "inference_performed": False,
        "purpose": "Prepare balanced answerability evaluation; image privacy screening and actual evaluation remain pending.",
    }
    (project / "docs" / "DATASET_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "validation_records": len(data),
                "local_subset_records": len(subset),
                "images_downloaded": 0,
                "training_performed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
