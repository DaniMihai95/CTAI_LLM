"""Affect sensor: a pretrained text emotion classifier applied to each student message."""
from transformers import pipeline

from .config import AFFECT_MODEL


def intensity_from_score(score: float) -> str:
    """Map classifier confidence to a coarse intensity level."""
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


class AffectSensor:
    """Wraps the classifier; returns label, score and intensity per text."""

    def __init__(self, device: int = -1):
        # device=-1 runs on CPU so the GPU stays free for the LLM.
        self.clf = pipeline("text-classification", model=AFFECT_MODEL,
                            top_k=1, device=device, truncation=True)

    def __call__(self, texts, batch_size: int = 32):
        single = isinstance(texts, str)
        batch = [texts] if single else list(texts)
        raw = self.clf(batch, batch_size=batch_size)
        out = []
        for r in raw:
            best = r[0] if isinstance(r, list) else r  # pipeline output shape differs by version
            score = float(best["score"])
            out.append({"label": best["label"], "score": round(score, 3),
                        "intensity": intensity_from_score(score)})
        return out[0] if single else out
