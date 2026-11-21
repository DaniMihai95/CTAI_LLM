"""Live terminal demo for the presentation.

Shows, per message, what the affect sensor and the risk guard detected, then the reply.
Commands: /reset clears the conversation, /quit exits.

Usage: python scripts/chat_demo.py [--condition lora|base|base_think] [--no-guard]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from esb import model as M  # noqa: E402  imports Unsloth first

from esb.affect import AffectSensor  # noqa: E402
from esb.config import ADAPTER_DIR, SEED  # noqa: E402
from esb.prompts import build_system  # noqa: E402
from esb.safety import HANDOVER_MESSAGE, Guard  # noqa: E402

CONDITIONS = {
    "base": dict(think=False, use_adapter=False),
    "base_think": dict(think=True, use_adapter=False),
    "lora": dict(think=False, use_adapter=True),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=list(CONDITIONS), default="lora")
    ap.add_argument("--no-guard", action="store_true")
    args = ap.parse_args()
    cfg = CONDITIONS[args.condition]

    print("Loading model...")
    model, tok = M.load(adapter_dir=ADAPTER_DIR if cfg["use_adapter"] else None)
    sensor = AffectSensor(device=-1)
    guard, history, turn = Guard(enabled=not args.no_guard), [], 0
    print(f"Exam-Stress Buddy ({args.condition}, guard {'off' if args.no_guard else 'on'}). "
          "Type /reset or /quit.\n")

    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text == "/quit":
            break
        if text == "/reset":
            guard, history = Guard(enabled=not args.no_guard), []
            print("(conversation cleared)\n")
            continue
        turn += 1
        affect = sensor(text)
        level, _, action, note = guard.before_turn(text)
        print(f"   [affect: {affect['label']} {affect['score']} ({affect['intensity']}) | risk: {level}]")
        history.append({"role": "user", "content": text})
        if action == "handover":
            reply = HANDOVER_MESSAGE
        else:
            messages = [{"role": "system", "content": build_system(affect, note)}] + history
            gen = M.generate(model, tok, messages, think=cfg["think"],
                             use_adapter=cfg["use_adapter"], seed=SEED + turn)
            reply = guard.after_turn(gen["answer"] or "(reasoning hit the token limit)")
        history.append({"role": "assistant", "content": reply})
        print(f"Buddy: {reply}\n")


if __name__ == "__main__":
    main()
