import re

# ── Phone number patterns (Chinese) ─────────────────────────────

MOBILE_RE = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")

PHONE_SEP_RE = re.compile(
    r"(?<!\d)(1[3-9]\d)[\s-](\d{4})[\s-](\d{4})(?!\d)"
)

LANDLINE_RE = re.compile(
    r"(?<!\d)(\d{3,4})[\s-](\d{7,8})(?!\d)"
)


def _mask_phone(m):
    if len(m.groups()) == 3:
        return f"{m.group(1)}****{m.group(3)}"
    return f"{m.group(1)}-****"


# ── Email pattern ───────────────────────────────────────────────

EMAIL_RE = re.compile(
    r"([a-zA-Z0-9._%+-]+)(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
)


def _mask_email(m):
    local = m.group(1)
    if len(local) <= 2:
        masked = local[0] + "*" * (len(local) - 1)
    elif len(local) <= 5:
        masked = local[0] + "*" * (len(local) - 2) + local[-1]
    else:
        masked = local[:2] + "*" * (len(local) - 4) + local[-2:]
    return masked + m.group(2)


# ── Name detection ──────────────────────────────────────────────

NAME_LABELS = [
    r"姓名\s*[：:]\s*",
    r"名字\s*[：:]\s*",
    r"Name\s*[：:]\s*",
    r"联系人\s*[：:]\s*",
    r"应聘人\s*[：:]\s*",
    r"求职者\s*[：:]\s*",
]

# Match 2-4 Chinese characters as a name
CN_NAME_RE = re.compile(r"([一-龥]{2,4})")

# Match English full name: First Last
EN_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


def _mask_chinese_name(name: str) -> str:
    if len(name) <= 1:
        return name
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def _mask_english_name(name: str) -> str:
    parts = name.split()
    masked = []
    for p in parts:
        if len(p) <= 2:
            masked.append(p[0] + "*")
        else:
            masked.append(p[0] + "*" * (len(p) - 2) + p[-1])
    return " ".join(masked)


# ── Main mask function ──────────────────────────────────────────

def mask_resume(text: str) -> str:
    """Detect and mask personal info in resume text."""

    # 1. Mask phone numbers
    text = MOBILE_RE.sub(_mask_phone, text)
    text = PHONE_SEP_RE.sub(_mask_phone, text)
    text = LANDLINE_RE.sub(_mask_phone, text)

    # 2. Mask emails
    text = EMAIL_RE.sub(_mask_email, text)

    # 3. Mask names after explicit labels
    for label_pat in NAME_LABELS:
        pat = re.compile(f"({label_pat})(\\S+)")
        text = pat.sub(lambda m: _mask_labeled_name(m), text)

    # 4. Try to detect name on the first meaningful line
    lines = text.strip().split("\n")
    if lines:
        first = lines[0].strip()
        # Remove page markers like "--- 第 1 页 ---"
        first = re.sub(r"^[-—]+\s*第\s*\d+\s*页\s*[-—]+", "", first).strip()
        # Remove "《》" markers
        first = re.sub(r"《[^》]+》", "", first).strip()
        if first and len(first) <= 6:
            # Check if it looks like a name (2-3 Chinese chars or English name)
            cn = CN_NAME_RE.fullmatch(first)
            if cn and 2 <= len(cn.group(1)) <= 3:
                lines[0] = _mask_chinese_name(cn.group(1))
                text = "\n".join(lines)

    return text


def _mask_labeled_name(m) -> str:
    label = m.group(1)
    value = m.group(2).strip()
    if re.fullmatch(r"[一-龥]{2,4}", value):
        return label + _mask_chinese_name(value)
    if re.fullmatch(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)*", value):
        return label + _mask_english_name(value)
    if len(value) > 1:
        return label + value[0] + "*" * (len(value) - 1)
    return m.group(0)
