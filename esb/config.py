"""Central settings: paths, model names, training and generation parameters."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "outputs"
RESULTS_DIR = ROOT / "results"
SCENARIO_DIR = ROOT / "scenarios"

# Same weights as Qwen/Qwen3.5-4B, mirrored by Unsloth for its loader.
BASE_MODEL = "unsloth/Qwen3.5-4B"
ADAPTER_DIR = OUT_DIR / "lora_esconv"

# Text emotion classifier used as the affect sensor (7 classes).
AFFECT_MODEL = "j-hartmann/emotion-english-distilroberta-base"

ESCONV_DATASET = "thu-coai/esconv"
# ESConv problem types that match the exam-stress domain.
DOMAIN_PROBLEM_TYPES = {
    "academic pressure",
    "procrastination",
    "sleep problems",
    "appearing anxious",
}

MAX_SEQ_LEN = 1024
HISTORY_MESSAGES = 8  # dialogue messages kept before the target reply

LORA = dict(
    r=16,
    alpha=16,
    dropout=0.0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
)

TRAIN = dict(
    epochs=2,
    lr=2e-4,
    batch_size=1,
    grad_accum=8,
    warmup_fraction=0.05,
    eval_examples=200,
)

SEED = 3407

# Sampling settings from the Qwen3.5 model card. Hugging Face generate has no
# presence_penalty, so a mild repetition_penalty stands in for it.
GEN_NO_THINK = dict(temperature=0.7, top_p=0.8, top_k=20, max_new_tokens=300)
GEN_THINK = dict(temperature=1.0, top_p=0.95, top_k=20, max_new_tokens=3072)
REPETITION_PENALTY = 1.05
