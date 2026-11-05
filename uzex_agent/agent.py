"""Agent sikli: LLM vositalarni chaqiradi, yakuniy javob dalilga qarshi tekshiriladi."""
from __future__ import annotations

import json
import re
import time

from . import db, grounding, llm
from .prompt import SYSTEM, TOOLS
from .resolve import resolve

DEADLINE = 75  # soniya; komissiya chegarasi 90
MAX_ROUNDS = 8
MAX_FIX = 2

DATASET_FACTS = {"from": "2022-01-03", "to": "2026-10-30", "deals": 500000, "contracts": 6616,
                 "participants": 14392, "brokers": 120}

MSG = {
    "ru": {
        "timeout": "Не удалось завершить расчёт вовремя, поэтому ответа не даю: выдумывать нельзя. Попробуйте уточнить вопрос.",
        "fail": "Сервис анализа сейчас недоступен, поэтому ответа не даю. Повторите вопрос через минуту.",
        "unverified": "Текст ответа не прошёл автоматическую проверку, поэтому показываю только точный результат запроса к базе.",
        "empty": "В данных ответа на этот вопрос нет.",
    },
    "uz": {
        "timeout": "Hisobni oʻz vaqtida tugatib boʻlmadi, shuning uchun javob bermayman: oʻylab topish mumkin emas. Savolni aniqlashtirib koʻring.",
        "fail": "Tahlil xizmati hozir ishlamayapti, shuning uchun javob bermayman. Bir daqiqadan soʻng qayta soʻrang.",
        "unverified": "Javob matni avtomatik tekshiruvdan oʻtmadi, shuning uchun faqat bazadan olingan aniq natijani koʻrsatyapman.",
        "empty": "Maʼlumotlarda bu savolga javob yoʻq.",
    },
}


def detect_lang(text: str) -> str:
    t = text.lower()
    if re.search(r"[ўқғҳ]", t) or re.search(r"[a-z]", t) and not re.search(r"[а-я]", t):
        return "uz"
    if re.search(r"\b(qancha|nechta|necha|qaysi|bitim|narx|soʻm|кайси|қанча)\b", t):
        return "uz"
    return "ru"


def _exec(call: dict, evidence: list, steps: list) -> str:
    name, args = call["name"], call.get("args") or {}
    if name == "resolve_entity":
        res = resolve(args.get("kind", ""), args.get("text", ""))
        steps.append({"type": "resolve", "kind": args.get("kind"), "text": args.get("text"),
                      "found": [r.get("name") or r.get("product") or r.get("region") for r in res.get("results", [])][:5],
                      "match": [r.get("match") for r in res.get("results", [])][:5]})
        evidence.append(res)
        return json.dumps(res, ensure_ascii=False, default=str)
    if name == "run_sql":
        sql = args.get("sql", "")
        try:
            res = db.run_sql(sql)
        except db.SqlError as e:
            steps.append({"type": "sql", "sql": sql, "error": str(e)})
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        steps.append({"type": "sql", "sql": sql, "columns": res["columns"], "rows": res["rows"][:20],
                      "row_count": res["row_count"], "truncated": res["truncated"]})
        evidence.append({"result": res, "sql_literals": re.findall(r"\d+(?:\.\d+)?", db._strip_strings(sql))})
        return json.dumps(res, ensure_ascii=False, default=str)
    return json.dumps({"error": f"Nomaʼlum vosita: {name}"}, ensure_ascii=False)


def _last_rows(steps: list) -> dict | None:
    for s in reversed(steps):
        if s["type"] == "sql" and s.get("rows"):
            return s
    return None


def _has_rows(steps: list) -> bool:
    return _last_rows(steps) is not None


def _result(answer, status, lang, steps, issues, started):
    return {
        "answer": answer,
        "status": status,  # verified | not_found | table_only | error
        "language": lang,
        "steps": steps,
        "issues": issues,
        "seconds": round(time.time() - started, 1),
    }


def ask(question: str, history: list | None = None) -> dict:
    started = time.time()
    lang = detect_lang(question)
    text = MSG[lang]
    messages: list = []
    for h in (history or [])[-3:]:
        messages.append({"role": "user", "content": str(h.get("q", ""))[:500]})
        messages.append({"role": "assistant", "text": str(h.get("a", ""))[:800]})
    messages.append({"role": "user", "content": question})

    steps: list = []
    evidence: list = [DATASET_FACTS]
    rejected_found = None  # None: yakuniy javob hali boʻlmagan
    fixes = 0
    issues: list = []

    for _ in range(MAX_ROUNDS):
        left = DEADLINE - (time.time() - started)
        if left < 3:
            break
        try:
            reply = llm.chat(SYSTEM, messages, TOOLS, timeout=min(left, 45))
        except llm.LLMError as e:
            steps.append({"type": "error", "error": str(e)[:200]})
            return _result(text["fail"], "error", lang, steps, [], started)

        calls = reply["calls"]
        if not calls and reply["text"].strip():
            calls = [{"id": "plain", "name": "final_answer", "args": {"answer": reply["text"], "found": True}}]
            reply = {"text": "", "calls": calls}
        if not calls:
            continue
        messages.append({"role": "assistant", "text": reply["text"], "calls": calls})

        final = next((c for c in calls if c["name"] == "final_answer"), None)
        if final is None:
            for c in calls:
                messages.append({"role": "tool", "id": c["id"], "content": _exec(c, evidence, steps)})
            continue

        for c in calls:
            if c is not final:
                messages.append({"role": "tool", "id": c["id"], "content": _exec(c, evidence, steps)})
        answer = (final["args"].get("answer") or "").strip()
        found = bool(final["args"].get("found", True))
        if found and not _has_rows(steps):
            issues = ["Dalil yoʻq: birorta SQL natijasi olinmagan."]
        else:
            issues = grounding.check(answer, question, evidence)
        rejected_found = found
        if not issues:
            return _result(answer, "verified" if found else "not_found", lang, steps, [], started)
        fixes += 1
        if fixes > MAX_FIX:
            break
        messages.append({
            "role": "tool", "id": final["id"],
            "content": json.dumps({"rejected": issues,
                                   "instruction": "Ответ отклонён проверкой. Получи недостающие данные через run_sql или убери неподтверждённые факты, затем снова вызови final_answer."},
                                  ensure_ascii=False),
        })

    if rejected_found and _has_rows(steps):
        return _result(text["unverified"], "table_only", lang, steps, issues, started)
    if rejected_found is False:
        return _result(text["empty"], "not_found", lang, steps, issues, started)
    return _result(text["timeout"], "error", lang, steps, issues, started)
