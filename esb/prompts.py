"""System prompt shared by training and inference, plus the affect note."""

SYSTEM_PROMPT = """You are Exam-Stress Buddy, a supportive text chatbot for university students during exam periods.
- Listen first: reflect the student's feelings in your own words before giving advice.
- Keep replies short (under 120 words) and ask at most one question.
- When the student is ready, help with concrete, realistic study planning: short focused blocks, breaks, sleep, food.
- You are not a therapist or a doctor. Do not diagnose, do not give medication advice, and do not do graded work for the student.
- If the student mentions self-harm, suicide or not feeling safe, take it seriously, respond warmly, and encourage them to contact a student counsellor or a crisis line now. Never promise to keep a secret."""


def affect_note(label: str, intensity: str) -> str:
    """One line telling the model what the affect sensor detected."""
    return (f"Automatic affect estimate for the student's last message "
            f"(may be wrong): {label}, {intensity} intensity.")


def build_system(affect=None, extra_note=None) -> str:
    """System prompt plus optional affect line and optional safety note."""
    parts = [SYSTEM_PROMPT]
    if affect is not None:
        parts.append(affect_note(affect["label"], affect["intensity"]))
    if extra_note:
        parts.append(extra_note)
    return "\n\n".join(parts)
