"""Nomlarni bazadagi aniq yozuvlarga bogʻlash (kirill/lotin, xato yozuv)."""
from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from .db import connection
from .normalize import company_key, fold

_cache: dict = {}


def _load() -> dict:
    if _cache:
        return _cache
    c = connection().cursor()
    _cache["companies"] = c.execute(
        """select p.inn,p.name,p.name_latin,p.region,p.role,p.activity,p.name_key,
                  coalesce(s.n,0)+coalesce(b.n,0) deals
           from participants p
           left join (select seller_inn i,count(*) n from deals group by 1) s on s.i=p.inn
           left join (select buyer_inn i,count(*) n from deals group by 1) b on b.i=p.inn"""
    ).fetchall()
    _cache["brokers"] = c.execute(
        """select b.code,b.name,b.name_latin,b.inn,b.region,b.name_key,
                  (select count(*) from deals d where d.seller_broker=b.code or d.buyer_broker=b.code)
           from brokers b"""
    ).fetchall()
    _cache["products"] = c.execute(
        "select product,product_uz,aliases,category,units,deal_count from products"
    ).fetchall()
    _cache["regions"] = c.execute("select region,region_ru,aliases from regions").fetchall()
    _cache["company_keys"] = [r[6] for r in _cache["companies"]]
    _cache["broker_keys"] = [r[5] for r in _cache["brokers"]]
    c.close()
    return _cache


def _company(row, match):
    return {"inn": row[0], "name": row[1], "name_latin": row[2], "region": row[3], "role": row[4],
            "activity": row[5], "deals": row[7], "match": match}


def _broker(row, match):
    return {"code": row[0], "name": row[1], "name_latin": row[2], "inn": row[3], "region": row[4],
            "deals": row[6], "match": match}


def _find_named(text: str, rows, keys, make, key_idx, id_idx, inn_idx):
    q = text.strip()
    digits = re.sub(r"\D", "", q)
    if len(digits) == 9 and len(digits) >= len(re.sub(r"\s", "", q)) - 4:
        hit = [make(r, "exact") for r in rows if r[inn_idx] == digits]
        return hit
    if id_idx is not None:
        hit = [make(r, "exact") for r in rows if str(r[id_idx]).lower() == q.lower()]
        if hit:
            return hit
    k = company_key(q)
    if not k:
        return []
    exact = [make(r, "exact") for r in rows if r[key_idx] == k]
    if exact:
        return sorted(exact, key=lambda x: -x["deals"])[:8]
    # Rus tilidagi yozuvda ў koʻpincha у boʻlib ketadi: o/u farqini eʼtiborsiz qoldiramiz
    lf = lambda x: x.replace("u", "o").replace("yo", "e")
    loose = lf(k)
    same = [make(r, "exact") for r in rows if lf(r[key_idx]) == loose]
    if same:
        return sorted(same, key=lambda x: -x["deals"])[:8]
    near = process.extract(k, keys, scorer=fuzz.ratio, limit=5, score_cutoff=80)
    return [make(rows[i], "similar") for _, _, i in near]


def resolve(kind: str, text: str) -> dict:
    d = _load()
    kind = (kind or "").lower()
    if kind == "company":
        res = _find_named(text, d["companies"], d["company_keys"], _company, 6, None, 0)
    elif kind == "broker":
        res = _find_named(text, d["brokers"], d["broker_keys"], _broker, 5, 0, 3)
    elif kind == "product":
        res = _find_product(text, d["products"])
    elif kind == "region":
        res = _find_region(text, d["regions"])
    else:
        return {"error": "kind: company | broker | product | region"}
    exact = [r for r in res if r.get("match") == "exact"]
    note = (
        "exact=topildi. Bir nechta exact boʻlsa, foydalanuvchiga INN bilan aniqlashtirish taklif qiling."
        if exact
        else "Aniq moslik YOʻQ. similar yozuvlar BOSHQA obyektlar: ular boʻyicha javob bermang, faqat 'aniq moslik topilmadi, ehtimol ...' deb ayting."
        if res
        else "Bazada topilmadi."
    )
    return {"query": text, "results": res, "note": note}


def _find_product(text, rows):
    q = fold(text)
    if not q:
        return []
    out = []
    for product, uz, aliases, cat, units, n in rows:
        names = [fold(product), fold(uz)] + [fold(a) for a in aliases.split()]
        if q in names:
            out.append({"product": product, "product_uz": uz, "category": cat, "units": units,
                        "deals": n, "match": "exact"})
    if out:
        return out
    for product, uz, aliases, cat, units, n in rows:
        names = [fold(product), fold(uz)] + [fold(a) for a in aliases.split()]
        if any(len(q) >= 3 and re.search(rf"\b{re.escape(q)}\b", x) for x in names):
            out.append({"product": product, "product_uz": uz, "category": cat, "units": units,
                        "deals": n, "match": "exact"})
    if out:
        return out
    # shakl oʻzgarishi uchun: "цемента", "paxtani", "бензина"
    for product, uz, aliases, cat, units, n in rows:
        for w in [fold(product), fold(uz)] + [fold(a) for a in aliases.split()]:
            for token in q.split():
                if len(token) >= 4 and len(w) >= 3 and (fuzz.ratio(token, w) >= 86 or token.startswith(w[:-1]) and len(w) >= 4):
                    out.append({"product": product, "product_uz": uz, "category": cat, "units": units,
                                "deals": n, "match": "exact"})
                    break
            else:
                continue
            break
    return out


def _find_region(text, rows):
    q = fold(text)
    out = []
    for region, ru, aliases in rows:
        hay = [fold(region), fold(ru), fold(aliases)]
        if any(q and q in h for h in hay) or fuzz.partial_ratio(q, hay[0]) >= 88:
            out.append({"region": region, "region_ru": ru, "match": "exact"})
    return out


def known_vocab() -> dict:
    """Javob tekshiruvi uchun: bazadagi barcha tovar nomlari."""
    d = _load()
    return {"products": [(p[0], p[1]) for p in d["products"]]}
