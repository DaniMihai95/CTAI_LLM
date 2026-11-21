"""Step 1: download ESConv, keep exam-stress topics, label affect, write chat examples.

Each supporter turn becomes one training example: the dialogue so far (last
HISTORY_MESSAGES messages) with the shared system prompt plus the affect
sensor's reading of the last student message, and the supporter reply as target.

Usage: python scripts/prepare_data.py [--all-topics]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch  # noqa: E402
from datasets import load_dataset  # noqa: E402

from esb.affect import AffectSensor  # noqa: E402
from esb.config import (DATA_DIR, DOMAIN_PROBLEM_TYPES, ESCONV_DATASET,  # noqa: E402
                        HISTORY_MESSAGES)
from esb.prompts import build_system  # noqa: E402

SEEKER = {"usr", "seeker", "user"}
SUPPORTER = {"sys", "supporter", "assistant"}


def parse_turns(record):
    """Return merged [(role, text, strategy)] with consecutive same-speaker turns joined."""
    merged = []
    for turn in record["dialog"]:
        speaker = str(turn.get("speaker", "")).lower()
        text = (turn.get("text") or turn.get("content") or "").strip()
        strategy = turn.get("strategy") or (turn.get("annotation") or {}).get("strategy")
        if not text:
            continue
        if speaker in SEEKER:
            role = "user"
        elif speaker in SUPPORTER:
            role = "assistant"
        else:
            raise ValueError(f"Unknown speaker value {speaker!r}; turn keys: {list(turn)}")
        if merged and merged[-1][0] == role:
            merged[-1] = (role, merged[-1][1] + " " + text, merged[-1][2] or strategy)
        else:
            merged.append((role, text, strategy))
    return merged


def build_examples(records, split):
    """One example per supporter reply that follows at least one student message."""
    examples = []
    for i, rec in enumerate(records):
        turns = parse_turns(rec)
        for j, (role, text, strategy) in enumerate(turns):
            if role != "assistant" or j == 0:
                continue
            history = [{"role": r, "content": t} for r, t, _ in turns[:j]][-HISTORY_MESSAGES:]
            if history[0]["role"] == "assistant":  # start the window on a student message
                history = history[1:]
            if not history:
                continue
            examples.append({
                "id": f"{split}-{i}-{j}",
                "problem_type": rec.get("problem_type"),
                "emotion_type": rec.get("emotion_type"),
                "strategy": strategy,
                "history": history,
                "target": text,
            })
    return examples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-topics", action="store_true",
                    help="keep every ESConv problem type, not only the exam-stress ones")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ds = load_dataset(ESCONV_DATASET)
    first = json.loads(ds["train"][0]["text"])
    print("Record keys:", list(first))
    print("Turn keys:", list(first["dialog"][0]))

    sensor = AffectSensor(device=0 if torch.cuda.is_available() else -1)
    stats = {}
    for split in ds:
        records = [json.loads(row["text"]) for row in ds[split]]
        topics = Counter(str(r.get("problem_type", "")).lower() for r in records)
        if not args.all_topics:
            records = [r for r in records
                       if str(r.get("problem_type", "")).lower() in DOMAIN_PROBLEM_TYPES]
        examples = build_examples(records, split)

        # Affect of the last student message, the same signal used at inference.
        last_user = [ex["history"][-1]["content"] for ex in examples]
        affects = sensor(last_user)
        out_path = DATA_DIR / f"{split}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for ex, aff in zip(examples, affects):
                ex["affect"] = aff
                ex["messages"] = [{"role": "system", "content": build_system(aff)}] + ex.pop("history")
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        stats[split] = {
            "dialogues_total": sum(topics.values()),
            "dialogues_kept": len(records),
            "examples": len(examples),
            "problem_types_all": dict(topics.most_common()),
            "affect_labels": dict(Counter(a["label"] for a in affects).most_common()),
            "strategies": dict(Counter(ex["strategy"] for ex in examples).most_common()),
        }
        print(f"{split}: kept {len(records)} of {sum(topics.values())} dialogues, "
              f"{len(examples)} examples -> {out_path}")

    with open(DATA_DIR / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print("Stats written to", DATA_DIR / "stats.json")


if __name__ == "__main__":
    main()
