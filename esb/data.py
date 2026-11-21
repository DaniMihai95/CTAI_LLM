"""Turning prepared ESConv examples into token ids with loss only on the reply."""
import json

from .config import MAX_SEQ_LEN
from .model import render, text_tokenizer


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def encode(tok, example, max_len: int = MAX_SEQ_LEN):
    """Prompt tokens get label -100 so training only learns the supporter reply.

    If too long, the oldest dialogue messages are dropped (system prompt kept).
    Returns None when even the shortest context does not fit.
    """
    t = text_tokenizer(tok)
    target_ids = t(example["target"] + "<|im_end|>", add_special_tokens=False)["input_ids"]
    messages = list(example["messages"])
    while True:
        prompt = render(tok, messages, enable_thinking=False)
        prompt_ids = t(prompt, add_special_tokens=False)["input_ids"]
        if len(prompt_ids) + len(target_ids) <= max_len:
            break
        if len(messages) <= 2:  # only system and last student message left
            return None
        messages = [messages[0]] + messages[2:]
    input_ids = prompt_ids + target_ids
    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": [-100] * len(prompt_ids) + target_ids,
    }
