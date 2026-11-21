"""Rule-based risk check and human handover, applied outside the LLM.

Levels: "crisis" (self-harm or suicide signals), "elevated" (strong distress),
"none". The guard is deliberately simple and transparent so its decisions can
be audited; it is a demonstration, not a validated clinical screener.
"""
import re

CRISIS_PATTERNS = [
    r"\bkill(ing)? myself\b",
    r"\bsuicid",
    r"\bend (it all|my life)\b",
    r"\bbetter off without me\b",
    r"\b(don'?t|do not) want to (live|be alive|be here|exist)\b",
    r"\bwant to die\b",
    r"\bhurt(ing)? myself\b",
    r"\bself[- ]?harm",
    r"\bno (point|reason) (in )?(living|to live)\b",
    r"\boverdose\b",
]

ELEVATED_PATTERNS = [
    r"\bpanic attacks?\b",
    r"\bcan'?t (breathe|stop crying)\b",
    r"\bhopeless",
    r"\bworthless\b",
    r"\bsuch a failure\b",
    r"\b(don'?t|do not) see the point\b",
    r"\bhaven'?t (really )?slept\b",
]

# Contacts shown at handover. Netherlands defaults; edit for another setting.
CONTACTS = (
    "- Your university's student counsellor or student psychologist (via the student desk).\n"
    "- 113 Suicide Prevention: call 113 or 0800-0113 (free, 24/7), or chat at 113.nl.\n"
    "- In immediate danger: call 112."
)

HANDOVER_MESSAGE = (
    "I'm really glad you told me, and I'm taking what you said seriously. "
    "You deserve support from a person right now, not only from a chatbot. "
    "Please reach out to one of these:\n" + CONTACTS + "\n"
    "If you can, tell someone you trust how you are feeling today. I'm still here to talk while you do."
)

ELEVATED_NOTE = ("Safety note: the student shows signs of strong distress. Respond with extra care "
                 "and gently mention that the university student counsellor can help, without pushing.")

FLAGGED_NOTE = ("Safety note: earlier in this conversation the student mentioned possible self-harm. "
                "Stay warm and calm, keep encouraging contact with a counsellor or the crisis line, "
                "never promise secrecy, and do not change the subject to study tips.")

REMINDER = "Reminder: 113 (or 0800-0113) and your student counsellor are there for you, any time."


def _matches(patterns, text):
    return [p for p in patterns if re.search(p, text, flags=re.IGNORECASE)]


def assess(text: str):
    """Return (level, matched_patterns) for one student message."""
    hits = _matches(CRISIS_PATTERNS, text)
    if hits:
        return "crisis", hits
    hits = _matches(ELEVATED_PATTERNS, text)
    if hits:
        return "elevated", hits
    return "none", []


class Guard:
    """Per-conversation state: once a crisis is flagged it stays flagged."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.flagged = False

    def before_turn(self, text: str):
        """Decide how this turn is handled.

        Returns (level, hits, action, note): action is "handover" (send the
        fixed message, skip the LLM) or "generate"; note goes into the system prompt.
        """
        level, hits = assess(text)
        if not self.enabled:
            return level, hits, "generate", None
        if level == "crisis" and not self.flagged:
            self.flagged = True
            return level, hits, "handover", None
        if self.flagged:
            return level, hits, "generate", FLAGGED_NOTE
        if level == "elevated":
            return level, hits, "generate", ELEVATED_NOTE
        return level, hits, "generate", None

    def after_turn(self, reply: str) -> str:
        """Append the contact reminder to every model reply after a crisis flag."""
        if self.enabled and self.flagged:
            return reply.rstrip() + "\n\n" + REMINDER
        return reply
