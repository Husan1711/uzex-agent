"""Faqat oʻqish uchun DuckDB: xavfsiz SQL, vaqt cheklovi, yengil lint."""
from __future__ import annotations

import datetime as dt
import decimal
import os
import re
import threading

import duckdb

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "uzex.duckdb"))
MAX_ROWS = 60
SQL_TIMEOUT = 15

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|copy|attach|detach|install|load|pragma|set|call|export|import|"
    r"read_csv|read_parquet|read_json|read_text|read_blob|glob|getenv|duckdb_settings)\b",
    re.I,
)


class SqlError(Exception):
    pass


_con = None
_lock = threading.Lock()


def connection() -> duckdb.DuckDBPyConnection:
    global _con
    with _lock:
        if _con is None:
            _con = duckdb.connect(
                DB_PATH,
                read_only=True,
                config={"threads": max(2, os.cpu_count() or 2), "enable_external_access": "false", "memory_limit": "1GB"},
            )
        return _con


def _strip_strings(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def check_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    bare = _strip_strings(s)
    if ";" in bare:
        raise SqlError("Faqat bitta soʻrov ruxsat etilgan.")
    if not re.match(r"^(select|with)\b", bare, re.I):
        raise SqlError("Faqat SELECT yoki WITH soʻrovlari ruxsat etilgan.")
    m = _FORBIDDEN.search(bare)
    if m:
        raise SqlError(f"Taqiqlangan kalit soʻz: {m.group(1)}")
    return s


def lint(sql: str) -> list[str]:
    """Maʼnoviy xatolarga ogohlantirish: model buni koʻrib soʻrovni tuzatadi."""
    s = _strip_strings(sql).lower()
    out: list[str] = []
    if "deals" not in s:
        return out
    if re.search(r"\b(sum|avg)\s*\(\s*(\w+\.)?amount\s*\)", s) and "currency" not in s and "contract_type" not in s:
        out.append("amount bir nechta valyutada: jamlash uchun amount_uzs ishlating yoki currency boʻyicha ajrating.")
    if re.search(r"\bavg\s*\(\s*(\w+\.)?unit_price\s*\)", s):
        out.append("avg(unit_price) oddiy oʻrtacha: vaznli narx uchun sum(amount)/sum(volume) ishlating (bitta birlik va valyuta ichida).")
    if re.search(r"\bsum\s*\(\s*(\w+\.)?(volume|delivered_volume)\s*\)", s) and not re.search(r"\bunit\b", s):
        out.append("volume turli birliklarda: mass_tons ishlating yoki unit boʻyicha guruhlang/filtrlang.")
    if re.search(r"\b(sum|avg)\s*\(\s*(\w+\.)?(amount|amount_uzs|amount_usd|volume|mass_tons)\b", s) and not re.search(
        r"is_cancelled|status", s
    ):
        out.append("Summa/hajmga bekor qilingan bitimlar kirgan: is_cancelled=false qoʻshing (yoki buni ataylab qilgan boʻlsangiz, javobda ayting).")
    return out


def _clean(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v


def run_sql(sql: str) -> dict:
    s = check_sql(sql)
    cur = connection().cursor()
    timer = threading.Timer(SQL_TIMEOUT, cur.interrupt)
    timer.start()
    try:
        res = cur.execute(s)
        cols = [d[0] for d in res.description]
        rows = res.fetchmany(MAX_ROWS + 1)
    except duckdb.Error as e:
        raise SqlError(str(e)[:400]) from e
    finally:
        timer.cancel()
        cur.close()
    truncated = len(rows) > MAX_ROWS
    rows = [[_clean(v) for v in r] for r in rows[:MAX_ROWS]]
    return {"columns": cols, "rows": rows, "row_count": len(rows), "truncated": truncated, "warnings": lint(s)}