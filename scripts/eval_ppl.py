"""Step 3: compare base and fine-tuned model on held-out ESConv supporter replies.

Metric: mean token loss and perplexity on the reply tokens only (lower = the
model finds real supporter replies more likely). Both conditions use the same
loaded weights; the base condition temporarily disables the LoRA adapter.

Usage: python scripts/eval_ppl.py [--n 300]
"""
import argparse
import json
import math
import random
import sys
from contextlib import nullcontext
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from esb import model as M  # noqa: E402  imports Unsloth first

import torch  # noqa: E402

from esb.config import ADAPTER_DIR, DATA_DIR, RESULTS_DIR, SEED  # noqa: E402
from esb.data import encode, read_jsonl  # noqa: E402


def mean_loss(model, rows, use_adapter):
    ctx = model.disable_adapter() if not use_adapter else nullcontext()
    total, count = 0.0, 0
    with ctx, torch.inference_mode():
        for enc in rows:
            ids = torch.tensor([enc["input_ids"]], device=model.device)
            labels = torch.tensor([enc["labels"]], device=model.device)
            n = int((labels != -100).sum())  # reply tokens; the first position is always prompt
            out = model(input_ids=ids, labels=labels)
            total += float(out.loss) * n
            count += n
    return total / count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="number of test replies")
    args = ap.parse_args()

    model, tok = M.load(adapter_dir=ADAPTER_DIR)
    rows = read_jsonl(DATA_DIR / "test.jsonl")
    random.seed(SEED)
    random.shuffle(rows)
    enc = [e for e in (encode(tok, r) for r in rows[:args.n]) if e is not None]

    results = {"n_replies": len(enc)}
    for name, use_adapter in (("base", False), ("lora", True)):
        loss = mean_loss(model, enc, use_adapter)
        results[name] = {"loss": round(loss, 4), "perplexity": round(math.exp(loss), 2)}
        print(f"{name}: loss {loss:.4f}, perplexity {math.exp(loss):.2f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "perplexity.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Written to", RESULTS_DIR / "perplexity.json")


if __name__ == "__main__":
    main()
