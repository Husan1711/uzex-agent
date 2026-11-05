"""Toʻliq sinov (LLM kaliti kerak): python -m tests.eval"""
import re
import sys
import time

from uzex_agent import agent, db
from uzex_agent.grounding import _numbers
from uzex_agent.normalize import fold
from .golden import ABSENT, ANSWER


def has(answer: str, value) -> bool:
    if isinstance(value, (int, float)):
        nums = [v for _, v, _ in _numbers(re.sub(r"\*", "", answer))]
        return any(abs(n - value) <= max(abs(value) * 0.006, 0.011) for n in nums)
    return fold(str(value)) in fold(answer)


def main() -> int:
    bad = 0
    times = []
    for q, sql in ANSWER:
        expected = db.connection().cursor().execute(sql).fetchone()
        r = agent.ask(q)
        times.append(r["seconds"])
        ok = r["status"] == "verified" and all(has(r["answer"], v) or _name_ok(r, v) for v in expected)
        bad += not ok
        print("OK " if ok else "BAD", f"{r['seconds']:5.1f}s {r['status']:10} {q}")
        if not ok:
            print("     kutilgan:", expected, "\n     javob:", r["answer"][:300], "\n     muammo:", r["issues"])
    for q in ABSENT:
        r = agent.ask(q)
        times.append(r["seconds"])
        ok = r["status"] == "not_found"
        bad += not ok
        print("OK " if ok else "BAD", f"{r['seconds']:5.1f}s {r['status']:10} {q}")
        if not ok:
            print("     javob:", r["answer"][:300])
    total = len(ANSWER) + len(ABSENT)
    print(f"\nNatija: {total - bad}/{total}; eng uzun javob {max(times):.1f}s")
    return 1 if bad else 0


def _name_ok(r, v) -> bool:
    """INN javobda boʻlmasa ham, nomi toʻgʻri koʻrsatilgan boʻlishi mumkin."""
    if not (isinstance(v, str) and v.isdigit()):
        return False
    row = db.connection().cursor().execute(
        "select name,name_latin from participants where inn=? ", [v]).fetchone()
    return bool(row) and any(fold(x) in fold(r["answer"]) for x in row)


if __name__ == "__main__":
    sys.exit(main())
