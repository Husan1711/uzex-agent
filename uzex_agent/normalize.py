"""Matn normallashtirish: transliteratsiya, tovar nomi va atributlari."""
from __future__ import annotations

import re
import unicodedata

CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g",
    "ҳ": "h",
}
APOS = "'’‘ʻʼ`´ˈ"
LEGAL = re.compile(
    r"\b(mas\s*uliyati\s+cheklangan\s+jamiyati|mchj|aj|qk|xk|ok|ooo|ao|oao|zao|ip|llc|ltd|"
    r"masuliyati\s+cheklangan\s+jamiyati)\b"
)


def to_latin(text: str) -> str:
    """Kirill matnini oʻzbek lotin yozuviga oʻtkazadi (registr saqlanadi)."""
    out = []
    for ch in text or "":
        low = ch.lower()
        if low in CYR2LAT:
            rep = CYR2LAT[low]
            out.append(rep.capitalize() if ch.isupper() and rep else rep)
        else:
            out.append(ch)
    return "".join(out)


def fold(text: str) -> str:
    """Yozuv, registr va tovush farqlariga bardoshli qidiruv kaliti."""
    s = unicodedata.normalize("NFKC", text or "").lower()
    s = to_latin(s)
    for a in APOS:
        s = s.replace(a, "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    # x/h, q/k, dj/j, ts/s kabi yozuv farqlarini birlashtirish
    s = s.replace("dj", "j").replace("ts", "s").replace("x", "h").replace("q", "k")
    s = s.replace("yo", "e").replace("ye", "e")
    return re.sub(r"\s+", " ", s).strip()


def company_key(name: str) -> str:
    """Kompaniya nomining yuridik shaklsiz kaliti."""
    s = unicodedata.normalize("NFKC", name or "").lower()
    s = to_latin(s)
    for a in APOS:
        s = s.replace(a, "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = LEGAL.sub(" ", s)
    return fold(s)


# (regex, RU nomi, UZ nomi, qoʻshimcha sinonimlar)
PRODUCTS: list[tuple[str, str, str, str]] = [
    (r"хлопок.{0,2}сырец", "Хлопок-сырец", "Paxta xomashyosi", "хлопок paxta xom paxta raw cotton"),
    (r"масло хлопков|хлопковое масло", "Масло хлопковое", "Paxta yogʻi", "yog хлопковое масло"),
    (r"масло подсолн|подсолнечное масло", "Масло подсолнечное", "Kungaboqar yogʻi", "kungaboqar yog'i yog подсолнечное"),
    (r"мука", "Мука", "Un", "un мука пшеничная"),
    (r"пшеница", "Пшеница", "Bugʻdoy", "bug'doy bugdoy"),
    (r"^рис", "Рис", "Guruch", "guruch sholi"),
    (r"сахар", "Сахар", "Shakar", "shakar qand"),
    (r"вода", "Вода питьевая", "Ichimlik suvi", "suv ichimlik suvi"),
    (r"шрот", "Шрот хлопковый", "Paxta shroti", "shrot kunjara жмых"),
    (r"комбикорм", "Комбикорм", "Omuxta yem", "omuxta yem yem"),
    (r"кормосмесь", "Кормосмесь", "Yem aralashmasi", "yem aralashmasi"),
    (r"соль", "Соль", "Tuz", "tuz"),
    (r"гипс", "Гипс", "Gips", "gips"),
    (r"известь", "Известь", "Ohak", "ohak"),
    (r"цемент", "Цемент", "Sement", "sement портландцемент portlandsement"),
    (r"бензин", "Бензин", "Benzin", "benzin"),
    (r"дизельн", "Дизельное топливо", "Dizel yoqilgʻisi", "dizel solyarka солярка"),
    (r"мазут", "Мазут", "Mazut", "mazut"),
    (r"сжиж|пропан", "Сжиженный газ", "Suyultirilgan gaz", "gaz suyultirilgan gaz пропан бутан пропан-бутан"),
    (r"битум", "Битум", "Bitum", "bitum"),
    (r"аргон", "Аргон", "Argon", "argon"),
    (r"азот", "Азот", "Azot", "azot"),
    (r"кислота", "Серная кислота", "Sulfat kislotasi", "sulfat kislota oltingugurt kislotasi"),
    (r"сода", "Сода каустическая", "Kaustik soda", "kaustik soda"),
    (r"карбамид|мочевина", "Карбамид", "Karbamid", "karbamid mochevina мочевина"),
    (r"селитра", "Аммиачная селитра", "Ammiakli selitra", "selitra ammiak"),
    (r"эмаль", "Эмаль", "Emal", "emal bo'yoq краска"),
    (r"труб", "Труба ПЭ", "PE quvur", "quvur труба полиэтиленовая"),
    (r"полиэтилен", "Полиэтилен", "Polietilen", "polietilen"),
    (r"полипропилен", "Полипропилен", "Polipropilen", "polipropilen"),
    (r"поливинилхлорид", "Поливинилхлорид", "Polivinilxlorid", "pvx пвх pvc polivinilxlorid"),
    (r"пиломатериал", "Пиломатериалы", "Yogʻoch taxta", "yog'och taxta доска"),
    (r"пряжа", "Пряжа хлопчатобумажная", "Paxta ipi", "ip kalava пряжа"),
    (r"кирпич", "Кирпич", "Gʻisht", "g'isht gisht"),
    (r"стекло", "Стекло", "Shisha", "shisha oyna"),
    (r"лист стальной", "Лист стальной", "Poʻlat list", "po'lat list prokat"),
    (r"проволока", "Проволока арматурная", "Armatura simi", "sim armatura simi"),
    (r"арматура", "Арматура", "Armatura", "armatura"),
    (r"катод|медный", "Катод медный", "Mis katod", "mis katod медь"),
    (r"профиль|алюминиевый", "Профиль алюминиевый", "Alyuminiy profil", "alyuminiy profil алюминий"),
    (r"подшипник", "Подшипник", "Podshipnik", "podshipnik"),
    (r"кабель", "Кабель силовой", "Kuch kabeli", "kabel"),
]
_PRODUCT_RX = [(re.compile(rx), ru, uz, syn) for rx, ru, uz, syn in PRODUCTS]


def canon_product(name: str) -> tuple[str, str]:
    low = (name or "").lower().replace("ё", "е")
    for rx, ru, uz, _ in _PRODUCT_RX:
        if rx.search(low):
            return ru, uz
    raise ValueError(f"Tovar aniqlanmadi: {name!r}")


def _grade_from(text: str) -> str | None:
    t = text.lower()
    if re.search(r"высш|в/с", t):
        return "высший"
    m = re.search(r"(?<![a-zа-я0-9])(iii|ii|i|[123]|перв\w*|втор\w*|трет\w*)[ -]*сорт", t)
    if m:
        g = m.group(1)
        if g in ("i", "1") or g.startswith("перв"):
            return "1"
        if g in ("ii", "2") or g.startswith("втор"):
            return "2"
        return "3"
    return None


def _class_from(text: str) -> str | None:
    t = text.lower()
    if "а500с" in t:
        return "А500С"
    m = re.search(r"(?<![a-zа-я0-9])(iv|iii|ii|i|[1-4])[ -]*класс", t)
    if not m:
        return None
    return {"i": "1", "ii": "2", "iii": "3", "iv": "4"}.get(m.group(1), m.group(1))


BRAND_RX = re.compile(
    r"(ЦЕМ\s+[IV]+(?:/[А-ЯA-Z]-[А-ЯA-Z])?\s+\d\d,5\s*Н|АИ-\d\d|Ne\s*\d+/\d|БНД\s*\d+/\d+|"
    r"(?:PP|HD|LL|PE)-\d+|Г-\d|М-\d+|ПФ-\d+|Вр-1|М0+к)",
    re.I,
)


def normalize_brand(raw: str | None, name: str) -> str | None:
    src = raw.strip() if raw and raw.strip() else None
    if not src:
        m = BRAND_RX.search(name or "")
        src = m.group(1) if m else None
    if not src:
        return None
    s = re.sub(r"\s+", " ", src).strip().upper()
    s = re.sub(r"(\d,5)\s*Н$", r"\1Н", s)
    return s.replace("NE ", "Ne ").replace("ВЫСШИЙ", "высший")


SIZE_RX = re.compile(r"(Ø\s*\d+\s*мм|\d+х\d+(?:х\d+)?\s*мм|\d+(?:,\d+)?\s*мм)", re.I)


def normalize_size(raw: str | None, name: str) -> str | None:
    src = raw.strip() if raw and raw.strip() else None
    if not src:
        m = SIZE_RX.search(name or "")
        src = m.group(1) if m else None
    return re.sub(r"\s+", "", src).lower() if src else None


def contract_attrs(name, brand, size, grade, kind, klass) -> dict:
    brand, size, grade, kind, klass = (
        x if isinstance(x, str) else None for x in (brand, size, grade, kind, klass)
    )
    ru, uz = canon_product(name)
    blob = " ".join(x for x in (name, grade) if x)
    blob_c = " ".join(x for x in (name, klass) if x)
    return {
        "product": ru,
        "product_uz": uz,
        "grade": _grade_from(blob),
        "class": _class_from(blob_c),
        "brand": normalize_brand(brand, name),
        "size": normalize_size(size, name),
        "kind": (kind or "").strip().lower() or None,
    }
