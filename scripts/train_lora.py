"""Step 2: LoRA fine-tune Qwen3.5-4B (bf16, non-thinking format) on the prepared ESConv data.

Usage:
  python scripts/train_lora.py --max-steps 20   # smoke test, a few minutes
  python scripts/train_lora.py                  # full run (epochs from esb/config.py)
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from esb import model as M  # noqa: E402  imports Unsloth first
from unsloth import FastLanguageModel  # noqa: E402

import torch  # noqa: E402
from datasets import Dataset  # noqa: E402
from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments  # noqa: E402

from esb.config import (ADAPTER_DIR, BASE_MODEL, DATA_DIR, LORA, MAX_SEQ_LEN,  # noqa: E402
                        OUT_DIR, RESULTS_DIR, SEED, TRAIN)
from esb.data import encode, read_jsonl  # noqa: E402


def encode_all(tok, rows):
    encoded = [encode(tok, r) for r in rows]
    kept = [e for e in encoded if e is not None]
    return kept, len(encoded) - len(kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-steps", type=int, default=-1, help="-1 trains for the configured epochs")
    ap.add_argument("--epochs", type=float, default=TRAIN["epochs"])
    args = ap.parse_args()

    random.seed(SEED)
    torch.manual_seed(SEED)

    model, tok = M.load(for_training=True)
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA["r"],
        lora_alpha=LORA["alpha"],
        lora_dropout=LORA["dropout"],
        target_modules=LORA["target_modules"],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=SEED,
        max_seq_length=MAX_SEQ_LEN,
    )
    model.print_trainable_parameters()

    t = M.text_tokenizer(tok)
    train_rows = read_jsonl(DATA_DIR / "train.jsonl")
    val_rows = read_jsonl(DATA_DIR / "validation.jsonl")
    random.shuffle(val_rows)
    val_rows = val_rows[:TRAIN["eval_examples"]]
    train_enc, train_dropped = encode_all(tok, train_rows)
    val_enc, val_dropped = encode_all(tok, val_rows)
    print(f"Train examples {len(train_enc)} (dropped {train_dropped}), "
          f"validation {len(val_enc)} (dropped {val_dropped})")

    steps_per_epoch = max(1, len(train_enc) // (TRAIN["batch_size"] * TRAIN["grad_accum"]))
    total_steps = args.max_steps if args.max_steps > 0 else int(steps_per_epoch * args.epochs)
    eval_steps = max(10, total_steps // 5)

    training_args = TrainingArguments(
        output_dir=str(OUT_DIR / "checkpoints"),
        per_device_train_batch_size=TRAIN["batch_size"],
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=TRAIN["grad_accum"],
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        learning_rate=TRAIN["lr"],
        lr_scheduler_type="cosine",
        warmup_steps=max(1, int(total_steps * TRAIN["warmup_fraction"])),
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=eval_steps,
        save_strategy="no",
        bf16=True,
        optim="adamw_torch",
        seed=SEED,
        report_to="none",
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=Dataset.from_list(train_enc),
        eval_dataset=Dataset.from_list(val_enc),
        data_collator=DataCollatorForSeq2Seq(t, padding=True, label_pad_token_id=-100),
    )

    torch.cuda.reset_peak_memory_stats()
    start = time.time()
    trainer.train()
    minutes = round((time.time() - start) / 60, 1)
    final_eval = trainer.evaluate()

    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(ADAPTER_DIR))
    tok.save_pretrained(str(ADAPTER_DIR))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log = {
        "base_model": BASE_MODEL,
        "lora": LORA,
        "train_config": TRAIN | {"epochs": args.epochs, "max_steps": args.max_steps},
        "max_seq_len": MAX_SEQ_LEN,
        "train_examples": len(train_enc),
        "val_examples": len(val_enc),
        "total_steps": total_steps,
        "minutes": minutes,
        "gpu": torch.cuda.get_device_name(0),
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        "final_eval": final_eval,
        "log_history": trainer.state.log_history,
    }
    with open(RESULTS_DIR / "train_log.json", "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    print(f"Done in {minutes} min, peak VRAM {log['peak_vram_gb']} GB. "
          f"Adapter -> {ADAPTER_DIR}, log -> {RESULTS_DIR / 'train_log.json'}")


if __name__ == "__main__":
    main()
