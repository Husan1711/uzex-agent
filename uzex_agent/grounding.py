"""Yakuniy javobdagi raqam va nomlar dalillardan olinganini tekshiradi."""
from __future__ import annotations

import re

from .normalize import fold
from .resolve import known_vocab

SCALE = [
    (r"(?:трлн|триллион\w*|trln|trillion)", 1e12),
    (r"(?:млрд|миллиард\w*|mlrd|milliard)", 1e9),
    (r"(?:млн|миллион\w*|mln|million)", 1e6),
    (r"(?:тыс\.?|тысяч\w*|ming)", 1e3),
]
_SCALE_RX = "|".join(s for s, _ in SCALE)
NUM_RX = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)"
    r"(?:\s*(" + _SCALE_RX + r"))?(?![\w])",
    re.I,
)
DATE_RX = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b|\b(\d{4})-(\d{2})(?:-(\d{2}))?\b")
LEGAL_RX = re.compile(
    r"(?:[\"«“„]([^\"»”“]{2,60})[\"»”“])|"
    r"\b([A-ZА-ЯЁЎҚҒҲ‘’ʻ']{2,}(?:\s+[A-ZА-ЯЁЎҚҒҲ‘’ʻ']{2,}){0,3})\s+(?:MCHJ|МЧЖ|AJ|АЖ|QK|OK|XK)\b"
)


def _parse(raw: str) -> tuple[float, int]:
    s = re.sub(r"[   ]", "", raw)
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    dec = len(s.split(".")[1]) if "." in s else 0
    return float(s), dec


def _numbers(text: str) -> list[tuple[str, float, float]]:
    """(asl matn, qiymat, ruxsat etilgan xatolik)."""
    out = []
    for m in NUM_RX.finditer(text):
        val, dec = _parse(m.group(1))
        scale = 1.0
        if m.group(2):
            for rx, sc in SCALE:
                if re.fullmatch(rx, m.group(2), re.I):
                    scale = sc
        out.append((m.group(0), val * scale, 0.51 * 10 ** (-dec) * scale))
    return out


def _flatten(evidence: list) -> tuple[list[float], str]:
    nums: list[float] = []
    chunks: list[str] = []

    def walk(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            nums.append(abs(float(v)))
        elif isinstance(v, str):
            chunks.append(v)
            for raw in re.findall(r"\d+(?:\.\d+)?", v):
                nums.append(float(raw))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(evidence)
    return nums, " \n ".join(chunks)


def check(answer: str, question: str, evidence: list) -> list[str]:
    """Muammolar roʻyxatini qaytaradi; boʻsh boʻlsa javob dalillarga mos."""
    problems: list[str] = []
    nums, text = _flatten(evidence)
    q_nums = [v for _, v, _ in _numbers(question)]
    body = DATE_RX.sub(lambda m: _date_ok(m, nums, q_nums, problems), answer)
    # roʻyxat tartib raqamlari: satr boshidagi "1." / "2)"
    body = re.sub(r"(?m)^\s*\d{1,2}[.)]\s", " ", body)
    for raw, val, tol in _numbers(body):
        if val < 13 and float(val).is_integer():  # 1-chi, 3 ta kabi kichik tartib sonlar
            if val in nums or val in q_nums or val <= 10:
                continue
        if any(abs(val - n) <= tol for n in nums) or any(abs(val - n) <= tol for n in q_nums):
            continue
        problems.append(f"Raqam dalilda yoʻq: {raw}")

    hay = fold(text + " " + question)
    for m in LEGAL_RX.finditer(answer):
        name = (m.group(1) or m.group(2) or "").strip()
        if name and fold(name) and fold(name) not in hay:
            problems.append(f"Nom dalilda yoʻq: {name}")
    for ru, uz in known_vocab()["products"]:
        for w in (ru, uz):
            if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", answer, re.I) and fold(w) not in hay:
                if fold(ru) not in hay and fold(uz) not in hay:
                    problems.append(f"Tovar dalilda yoʻq: {w}")
    return problems


def _date_ok(m, nums, q_nums, problems) -> str:
    """Sana qismlari dalil yoki savolda boʻlishi kerak."""
    if m.group(1):
        parts = [float(m.group(3)), float(m.group(2)), float(m.group(1))]
    else:
        parts = [float(m.group(4)), float(m.group(5))] + ([float(m.group(6))] if m.group(6) else [])
    pool = set(nums) | set(q_nums)
    if not all(p in pool for p in parts):
        problems.append(f"Sana dalilda yoʻq: {m.group(0)}")
    return " "
