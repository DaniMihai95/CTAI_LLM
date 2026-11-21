"""Loading Qwen3.5-4B (with or without the LoRA adapter), chat rendering and generation."""
import unsloth  # noqa: F401  Unsloth must be imported before transformers
from unsloth import FastLanguageModel

import time
from contextlib import nullcontext

import torch

from .config import (BASE_MODEL, GEN_NO_THINK, GEN_THINK, MAX_SEQ_LEN,
                     REPETITION_PENALTY)

END_TOKENS = ("<|im_end|>", "<|endoftext|>")


def text_tokenizer(tok):
    """Qwen3.5 is multimodal: the loader may return a processor wrapping the tokenizer."""
    return getattr(tok, "tokenizer", tok)


def render(tok, messages, enable_thinking: bool, add_generation_prompt: bool = True) -> str:
    """Apply the Qwen chat template; enable_thinking switches reasoning mode on or off."""
    t = text_tokenizer(tok)
    kwargs = dict(tokenize=False, add_generation_prompt=add_generation_prompt,
                  enable_thinking=enable_thinking)
    try:
        return t.apply_chat_template(messages, **kwargs)
    except (ValueError, AttributeError):
        # Fallback: processor template expects content as a list of parts.
        parts = [{"role": m["role"], "content": [{"type": "text", "text": m["content"]}]}
                 for m in messages]
        return tok.apply_chat_template(parts, **kwargs)


def load(adapter_dir=None, for_training: bool = False):
    """Load the base model, or base plus adapter when adapter_dir is given (bf16, no 4-bit)."""
    name = str(adapter_dir) if adapter_dir else BASE_MODEL
    model, tok = FastLanguageModel.from_pretrained(
        model_name=name,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=False,  # Unsloth advises against 4-bit training for Qwen3.5
        load_in_16bit=True,
    )
    if not for_training:
        FastLanguageModel.for_inference(model)
    return model, tok


def split_thinking(raw: str, think: bool):
    """Separate the <think> reasoning from the visible answer."""
    for end in END_TOKENS:
        raw = raw.split(end)[0]
    if "</think>" in raw:
        reasoning, answer = raw.split("</think>", 1)
        return reasoning.replace("<think>", "").strip(), answer.strip(), False
    if think or "<think>" in raw:  # the template opens <think> itself, so no tag in the output
        return raw.replace("<think>", "").strip(), "", True
    return "", raw.strip(), False


def generate(model, tok, messages, think: bool = False, use_adapter: bool = True,
             seed: int = 0) -> dict:
    """One reply. use_adapter=False temporarily disables LoRA to get the base model."""
    t = text_tokenizer(tok)
    prompt = render(tok, messages, enable_thinking=think)
    inputs = t(prompt, return_tensors="pt", add_special_tokens=False).to(model.device)
    cfg = GEN_THINK if think else GEN_NO_THINK
    end_ids = [i for i in t.convert_tokens_to_ids(list(END_TOKENS)) if i is not None and i != t.unk_token_id]
    ctx = model.disable_adapter() if (not use_adapter and hasattr(model, "disable_adapter")) else nullcontext()
    torch.manual_seed(seed)
    start = time.time()
    with ctx, torch.inference_mode():
        out = model.generate(
            **inputs,
            do_sample=True,
            temperature=cfg["temperature"],
            top_p=cfg["top_p"],
            top_k=cfg["top_k"],
            max_new_tokens=cfg["max_new_tokens"],
            repetition_penalty=REPETITION_PENALTY,
            pad_token_id=t.pad_token_id if t.pad_token_id is not None else t.eos_token_id,
            eos_token_id=end_ids,  # stop at the end of the assistant turn
        )
    new_ids = out[0, inputs["input_ids"].shape[1]:]
    raw = t.decode(new_ids, skip_special_tokens=False)
    reasoning, answer, truncated = split_thinking(raw, think)
    return {
        "answer": answer,
        "reasoning": reasoning,
        "truncated": truncated,
        "new_tokens": int(new_ids.shape[0]),
        "seconds": round(time.time() - start, 2),
    }
