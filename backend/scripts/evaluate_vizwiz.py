"""Evaluate answerability on the prepared local subset. No inference, no fake predictions."""

import argparse
import json
from pathlib import Path


def evaluate(records, predictions):
    expected = {item["image"]: bool(item["answerable"]) for item in records}
    ids = [item.get("image") for item in predictions]
    if (
        len(ids) != len(set(ids))
        or set(ids) != set(expected)
        or any(type(item.get("answerable")) is not bool for item in predictions)
    ):
        raise ValueError(
            "Provide exactly one boolean answerability prediction for every subset image"
        )
    correct = sum(item["answerable"] == expected[item["image"]] for item in predictions)
    return {
        "records": len(records),
        "correct": correct,
        "answerability_accuracy": correct / len(records) if records else None,
        "metric": "subset binary answerability accuracy, not official VizWiz VQA or AP score",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    records = json.loads(
        (project / ".local" / "datasets" / "vizwiz-vqa-eval.json").read_text(
            encoding="utf-8"
        )
    )
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(records, predictions), indent=2))


if __name__ == "__main__":
    main()
