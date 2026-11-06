"""Birja reyestri agenti: Streamlit chat.

Ishga tushirish:  streamlit run streamlit_app.py
Agent mantiqi (uzex_agent) oʻzgarmagan: SQL, tekshiruv va hisoblar fonda bajariladi,
foydalanuvchiga faqat savol-javob oynasi koʻrinadi.
"""
from __future__ import annotations

import html
import os
import re
import time

import streamlit as st

st.set_page_config(page_title="UZEX agent", page_icon="💬", layout="centered")


# ───────────────────────── sozlamalar (kalit va h.k.) ─────────────────────────
def _load_settings() -> None:
    """LLM_* qiymatlarini .env yoki Streamlit secrets dan muhitga qoʻyadi (agent importidan oldin)."""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        for line in open(env_file, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
    for k in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        try:
            if k in st.secrets:
                os.environ.setdefault(k, str(st.secrets[k]))
        except Exception:  # secrets.toml yoʻq
            pass


_load_settings()


@st.cache_resource(show_spinner="Maʼlumotlar bazasi tayyorlanmoqda…")
def _prepare_db() -> bool:
    """data/uzex.duckdb yoʻq boʻlsa, ZIP dan bir marta quradi."""
    root = os.path.join(os.path.dirname(__file__), "data")
    path = os.environ.get("DB_PATH", os.path.join(root, "uzex.duckdb"))
    if not os.path.exists(path):
        import tempfile
        import zipfile

        from uzex_agent.build_db import build

        with tempfile.TemporaryDirectory() as tmp:
            zipfile.ZipFile(os.path.join(root, "uzex_spot_data.zip")).extractall(tmp)
            build(os.path.join(tmp, "uzex_spot_data"), path)
    return True


_prepare_db()
from uzex_agent import agent  # noqa: E402  (muhit oʻzgaruvchilaridan keyin import qilinadi)


@st.cache_resource(show_spinner=False)
def _warm() -> dict:
    """Qidiruv lugʻatini oldindan yuklaydi va takroriy savollar uchun kesh beradi."""
    from uzex_agent.resolve import resolve

    resolve("company", "warmup")
    return {}


_CACHE = _warm()

# ───────────────────────── dizayn (Uiverse chat, kattalashtirilgan) ─────────────────────────
CSS = """
<style>
:root{
  --card:#343541; --row-a:#2E2F3A; --row-b:#343541; --input:#40414F; --line:#2E2F3A;
  --muted:#6B6C7B; --ph:#828E9E; --text:#ECECF1; --accent:#19c37d;
}
html, body, .stApp{background:#202123 !important;}
header[data-testid="stHeader"], footer, #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"]{display:none !important;}
.block-container{max-width:520px !important; padding:4vh 12px 0 !important;}

/* —— .container —— */
.st-key-card{
  background:var(--card); border-radius:8px; gap:0 !important; overflow:hidden;
  box-shadow:0 20px 50px rgba(0,0,0,.45);
}
.st-key-card [data-testid="stVerticalBlock"]{gap:0 !important;}

/* —— .nav-bar —— */
.nav-bar{width:100%; height:44px; display:flex; align-items:center; justify-content:space-between;}
.nav-bar span{color:var(--muted); white-space:nowrap; margin-left:14px; user-select:none; font:500 14px/1 system-ui,sans-serif; letter-spacing:.02em;}
.close{width:44px; height:44px; display:flex; justify-content:center; align-items:center; position:relative; cursor:pointer; text-decoration:none !important;}
.line{position:absolute; width:20px; height:3px; background:var(--muted); border-radius:30px; transition:background .15s;}
.line.one{transform:rotate(45deg);} .line.two{transform:rotate(135deg);}
.close:hover .line{background:#fff;}

/* —— .messages-area —— */
.st-key-msgs{background:var(--card); padding:0 !important; scrollbar-width:thin; scrollbar-color:#4a4b59 transparent;}
.st-key-msgs > div, .st-key-msgs [data-testid="stVerticalBlock"]{gap:0 !important; padding:0 !important;}
.st-key-msgs [data-testid="stMarkdownContainer"]{width:100%;}
.st-key-msgs [data-testid="stElementContainer"]{width:100% !important;}
.message{width:100%; display:flex; gap:12px; padding:16px 16px; box-sizing:border-box; color:var(--text); font:400 15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;}
.message.one{background:var(--row-a);}      /* savol */
.message.two{background:var(--row-b);}      /* javob */
.message .ava{flex:0 0 28px; height:28px; border-radius:6px; display:grid; place-items:center; font:700 12px/1 system-ui; color:#fff; margin-top:1px;}
.message.one .ava{background:#6B6C7B;} .message.two .ava{background:var(--accent);}
.message .txt{min-width:0; flex:1; overflow-wrap:anywhere;}
.message .txt p{margin:0 0 8px;} .message .txt p:last-child{margin:0;}
.message .txt ul,.message .txt ol{margin:4px 0 8px; padding-left:20px;}
.message .txt p.h{margin:14px 0 6px; font-weight:650; color:#fff; font-size:15px;} .message .txt p.h:first-child{margin-top:0;}
.message .txt strong{color:#fff; font-weight:650;}
.message .tbl{overflow:auto; margin-top:10px; max-height:260px; border-radius:6px; background:#2a2b36;}
.message table{border-collapse:collapse; width:100%; font-size:13px;}
.message th,.message td{padding:6px 10px; text-align:left; white-space:nowrap; border-bottom:1px solid #3d3e4c;}
.message th{color:var(--ph); font-weight:600; position:sticky; top:0; background:#2a2b36;}
.message td.n,.message th.n{text-align:right;}

/* —— "Nimaga asoslangan" (fon jarayoni) —— */
.basis{margin-top:16px; border:1px solid rgba(25,195,125,.55); border-radius:10px; background:#2b2c37; overflow:hidden;}
.basis > summary{cursor:pointer; list-style:none; user-select:none; outline:none; display:flex; align-items:center; gap:10px;
  padding:13px 16px; color:#fff; font-size:16px; font-weight:650; background:rgba(25,195,125,.12); transition:background .15s;}
.basis > summary::-webkit-details-marker{display:none;}
.basis > summary::before{content:"▸"; color:var(--accent); font-size:16px;}
.basis[open] > summary::before{content:"▾";}
.basis > summary::after{content:"bosing"; margin-left:auto; font-size:12px; font-weight:500; color:var(--accent); letter-spacing:.03em;}
.basis[open] > summary::after{content:"yopish";}
.basis > summary:hover{background:rgba(25,195,125,.22);}
.basis > :not(summary){margin-left:16px; margin-right:16px;}
.basis[open]{padding-bottom:16px;}
.basis .bh{margin-top:16px; margin-bottom:6px; font-size:13px; font-weight:700; color:#d5d6e0; text-transform:uppercase; letter-spacing:.05em;}
.basis .bl{font-size:15px; color:#ececf1; line-height:1.65; overflow-wrap:anywhere;}
.basis .ok{color:var(--accent); font-weight:600;} .basis .bad{color:#ff7b72; font-weight:600;}
.basis .sql{background:#20212a; border:1px solid #3d3e4c; border-radius:8px; padding:12px 14px; margin-top:6px; margin-bottom:8px; font:13px/1.6 ui-monospace,Consolas,monospace; color:#d6e2ff; white-space:pre-wrap; overflow:auto; max-height:280px;}
.basis .tbl{margin-top:10px; max-height:300px;}
.basis table{font-size:14px;}

/* yozilayotgan kursor va "oʻylayapti" nuqtalari */
.caret{display:inline-block; width:7px; height:1em; margin-left:2px; vertical-align:-2px; background:var(--accent); animation:blink 1s steps(1) infinite;}
.dots{display:inline-flex; gap:5px; align-items:center; height:24px;}
.dots i{width:7px; height:7px; border-radius:50%; background:var(--ph); animation:bounce 1.2s infinite ease-in-out;}
.dots i:nth-child(2){animation-delay:.15s;} .dots i:nth-child(3){animation-delay:.3s;}
@keyframes blink{50%{opacity:0}}
@keyframes bounce{0%,60%,100%{transform:translateY(0);opacity:.5}30%{transform:translateY(-6px);opacity:1}}

/* —— .sender-area / .input-place —— */
.st-key-sender{background:var(--card); border-radius:8px; padding:15px 12px 15px !important; margin:0 !important;}
.st-key-sender [data-testid="stForm"], .st-key-sender form{border:none !important; padding:0 !important; background:none !important;}
.st-key-sender [data-testid="stVerticalBlock"]{flex-direction:row !important; align-items:center; gap:5px !important;
  background:var(--input); border:1px solid var(--line); border-radius:7px; height:46px; padding:0 6px 0 4px;}
.st-key-sender [data-testid="stTextInput"]{flex:1; min-width:0;}
.st-key-sender [data-testid="stTextInput"] > div, .st-key-sender [data-baseweb="input"], .st-key-sender [data-baseweb="base-input"]{
  background:none !important; border:none !important; box-shadow:none !important; outline:none !important;}
.st-key-sender [data-testid="stTextInputRootElement"], .st-key-sender [data-testid="stTextInputRootElement"]:focus-within{
  background:transparent !important; border:none !important; box-shadow:none !important; outline:none !important;}
.st-key-sender input{background:none !important; border:none !important; outline:none !important; color:#fff !important; font:400 15px system-ui,-apple-system,'Segoe UI',sans-serif !important; padding:0 8px !important; text-overflow:ellipsis;}
.st-key-sender input::placeholder{color:var(--ph) !important; opacity:1;}
.st-key-sender [data-testid="InputInstructions"]{display:none !important;}
.st-key-sender [data-testid="stFormSubmitButton"]{flex:0 0 auto; width:auto !important;}
.st-key-sender [data-testid="stFormSubmitButton"] button{
  width:32px; height:32px; min-height:0; padding:0; border:none; background:transparent center/17px no-repeat;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236B6C7B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M22 2 11 13'/><path d='M22 2 15 22l-4-9-9-4 20-7z'/></svg>");
  cursor:pointer; font-size:0; color:transparent; box-shadow:none;}
.st-key-sender [data-testid="stFormSubmitButton"] button p{display:none;}
.st-key-sender [data-testid="stFormSubmitButton"] button:hover{
  background-color:transparent; border:none;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2319c37d' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M22 2 11 13'/><path d='M22 2 15 22l-4-9-9-4 20-7z'/></svg>");}
.st-key-sender [data-testid="stFormSubmitButton"] button:focus{box-shadow:none; outline:none;}

/* skriptni saqlovchi iframe koʻrinmasin */
.st-key-scroller{position:absolute; height:0; width:0; overflow:hidden; opacity:0; pointer-events:none;}
@media (max-width:560px){ .block-container{padding-top:0 !important;} }
</style>
"""

NAV = """
<div class="nav-bar"><span>UZEX agent</span>
  <a class="close" href="?clear=1" target="_self" title="Suhbatni tozalash" aria-label="Suhbatni tozalash">
    <div class="line one"></div><div class="line two"></div></a></div>
"""

SCROLL_JS = """
<script>
(function(){
  const doc = window.parent.document;
  let stick = true;
  function box(){ return doc.querySelector('.st-key-msgs'); }
  function bind(){
    const b = box(); if(!b || b.dataset.bound) return;
    b.dataset.bound = 1;
    b.addEventListener('scroll', () => { stick = b.scrollHeight - b.scrollTop - b.clientHeight < 90; });
  }
  setInterval(() => { bind(); const b = box(); if(b && stick) b.scrollTop = b.scrollHeight; }, 80);
})();
</script>
"""

def _run_js(code: str) -> None:
    """Yashirin iframe ichida skript ishga tushiradi (xabarlar oynasini pastga aylantirish uchun)."""
    if hasattr(st, "iframe"):
        st.iframe(code, height=1)
    else:  # eski Streamlit
        import streamlit.components.v1 as components

        components.html(code, height=0)


GREETING = "Salom! Men birja bitimlari boʻyicha savollarga javob beraman. Savolingizni oʻzbek yoki rus tilida yozing."


# ───────────────────────── yordamchi funksiyalar ─────────────────────────
def _inline(t: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)


def md(text: str) -> str:
    """Kichik markdown → HTML: sarlavha, qalin, roʻyxat, jadval, abzats. Avval HTML escape qilinadi."""
    out, lst, tbl = [], None, []

    def close():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None

    def flush_table():
        nonlocal tbl
        if not tbl:
            return
        rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", r)]
        tbl = []
        if not rows:
            return
        head, body = rows[0], rows[1:]
        isnum = lambda v: bool(re.fullmatch(r"[-+−]?[\d\s.,%]+", (v or "").replace("**", "")))
        th = "".join(f'<th class="{"n" if body and isnum(body[0][i] if i < len(body[0]) else "") else ""}">{_inline(c)}</th>' for i, c in enumerate(head))
        tr = "".join("<tr>" + "".join(f'<td class="{"n" if isnum(c) else ""}">{_inline(c)}</td>' for c in r) + "</tr>" for r in body)
        out.append(f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>')

    for raw in html.escape(text, quote=False).split("\n"):
        if raw.strip().startswith("|"):
            close()
            tbl.append(raw)
            continue
        flush_table()
        line = raw.strip()
        m_h = re.match(r"^#{1,6}\s+(.*)", line)
        line = _inline(line)
        m_ul, m_ol = re.match(r"^[-*•]\s+(.*)", line), re.match(r"^\d+[.)]\s+(.*)", line)
        if m_h:
            close()
            out.append(f'<p class="h">{_inline(m_h.group(1))}</p>')
        elif m_ul or m_ol:
            kind = "ul" if m_ul else "ol"
            if lst != kind:
                close()
                out.append(f"<{kind}>")
                lst = kind
            out.append(f"<li>{(m_ul or m_ol).group(1)}</li>")
        else:
            close()
            if line:
                out.append(f"<p>{line}</p>")
    close()
    flush_table()
    return "".join(out)


def num(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:,.2f}".rstrip("0").rstrip(".").replace(",", " ") if isinstance(v, float) else f"{v:,}".replace(",", " ")
    return html.escape(str(v if v is not None else ""))


def table_html(cols: list, rows: list) -> str:
    if not rows:
        return ""
    head = "".join(f'<th class="{"n" if isinstance(rows[0][i], (int, float)) else ""}">{html.escape(str(c))}</th>' for i, c in enumerate(cols))
    body = "".join(
        "<tr>" + "".join(f'<td class="{"n" if isinstance(v, (int, float)) and not isinstance(v, bool) else ""}">{num(v)}</td>' for v in r) + "</tr>"
        for r in rows
    )
    return f'<div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def row(role: str, inner: str) -> str:
    cls, ava = ("one", "S") if role == "user" else ("two", "AI")
    return f'<div class="message {cls}"><div class="ava">{ava}</div><div class="txt">{inner}</div></div>'


def user_row(text: str) -> str:
    return row("user", f"<p>{html.escape(text)}</p>")


def bot_row(text: str, table: str = "", caret: bool = False) -> str:
    body = md(text)
    if caret:
        body = body.replace("</p>", '<span class="caret"></span></p>', 1) if body.endswith("</p>") and body.count("</p>") == 1 else body + '<span class="caret"></span>'
    return row("bot", body + table)


def thinking_row() -> str:
    return row("bot", '<span class="dots"><i></i><i></i><i></i></span>')


def stream(placeholder, text: str, table: str) -> None:
    """Javobni soʻzma-soʻz “yozib” chiqaradi (umumiy vaqt ~0,7 s dan oshmaydi)."""
    tokens = re.findall(r"\S+\s*", text)
    delay = min(0.02, 0.7 / max(len(tokens), 1))
    shown = ""
    for tok in tokens:
        shown += tok
        part = shown + ("**" if shown.count("**") % 2 else "")  # ochiq qalin belgi buzmasin
        placeholder.markdown(bot_row(part, caret=True), unsafe_allow_html=True)
        time.sleep(delay)
    placeholder.markdown(bot_row(text, table), unsafe_allow_html=True)


def answer_table(res: dict) -> str:
    """Matn tekshiruvdan oʻtmasa, javobning oʻzi sifatida bazadan olingan jadval koʻrsatiladi."""
    if res.get("status") != "table_only":
        return ""
    for s in reversed(res.get("steps", [])):
        if s.get("rows"):
            return table_html(s["columns"], s["rows"])
    return ""


STATUS_TXT = {
    "verified": ("ok", "Javob bazadagi natija bilan tekshirildi"),
    "table_only": ("bad", "Javob matni tekshiruvdan oʻtmadi, shuning uchun faqat bazadan olingan natija koʻrsatildi"),
    "not_found": ("bad", "Maʼlumotlarda bu savolga javob topilmadi"),
    "error": ("bad", "Hisob yakunlanmadi (xizmat xatosi yoki vaqt tugadi)"),
}


def basis_html(res: dict) -> str:
    """“Nimaga asoslangan”: fonda nima boʻlgani: nomlarni aniqlash, bazaga yuborilgan SQL, natija, yakuniy holat."""
    e = html.escape
    kind, label = STATUS_TXT.get(res.get("status"), ("bad", "Nomaʼlum holat"))
    sec = f" · {res['seconds']} s" if res.get("seconds") is not None else ""
    p = [f'<div class="bh">Yakuniy holat</div><div class="bl"><span class="{kind}">●</span> {e(label)}{sec}</div>']
    n = 0
    for x in res.get("steps", []):
        t = x.get("type")
        if t == "resolve":
            n += 1
            found = ", ".join(e(str(v)) for v in (x.get("found") or [])[:3]) or "mos yozuv topilmadi"
            p.append(f'<div class="bh">{n}. Nomni aniqlash</div><div class="bl">«{e(str(x.get("text", "")))}» ({e(str(x.get("kind", "")))}) → {found}</div>')
        elif t == "sql":
            n += 1
            sql = e(str(x.get("sql", "")).strip()).replace("\n", "&#10;")
            if x.get("error"):
                state = f'<span class="bad">✗ Xato:</span> {e(str(x["error"])[:200])}'
            else:
                cnt = x.get("row_count", len(x.get("rows", [])))
                state = f'<span class="ok">✓ Bajarildi:</span> {cnt} qator qaytdi' + (", jadvalda dastlabki 10 tasi" if cnt > 10 else "")
            p.append(f'<div class="bh">{n}. Bazaga yuborilgan soʻrov (SQL)</div><div class="sql">{sql}</div><div class="bl">{state}</div>')
            if x.get("rows"):
                p.append(table_html(x["columns"], x["rows"][:10]))
        elif t == "error":
            n += 1
            p.append(f'<div class="bh">{n}. Tahlil xizmati</div><div class="bl"><span class="bad">✗</span> Xizmatga ulanishda xato yuz berdi</div>')
    if res.get("issues"):
        items = "<br>".join("• " + e(str(i)) for i in res["issues"][:5])
        p.append(f'<div class="bh">Tekshiruv izohlari</div><div class="bl">{items}</div>')
    return '<details class="basis"><summary>Nimaga asoslangan</summary>' + "".join(p) + "</details>"


# ───────────────────────── holat ─────────────────────────
if "clear" in st.query_params:
    st.query_params.clear()
    st.session_state.pop("msgs", None)
st.session_state.setdefault("msgs", [])  # [{"role","content","table"}]
history: list = st.session_state["msgs"]

st.markdown(CSS, unsafe_allow_html=True)

# ───────────────────────── interfeys ─────────────────────────
with st.container(key="card"):
    st.markdown(NAV, unsafe_allow_html=True)
    box = st.container(key="msgs", height=520)
    with box:
        st.markdown(bot_row(GREETING), unsafe_allow_html=True)
        for m in history:
            st.markdown(user_row(m["content"]) if m["role"] == "user" else bot_row(m["content"], m.get("table", "")), unsafe_allow_html=True)

    with st.container(key="sender"):
        with st.form("sender_form", clear_on_submit=True, border=False):
            q = st.text_input("Savol", placeholder="Savolingizni yozing…", label_visibility="collapsed", max_chars=1000)
            sent = st.form_submit_button("Yuborish")
    with st.container(key="scroller"):
        _run_js(SCROLL_JS)

if sent and q.strip():
    q = q.strip()
    pairs = []  # agentga oxirgi savol-javoblar
    msgs = history
    for i in range(0, len(msgs) - 1, 2):
        if msgs[i]["role"] == "user" and msgs[i + 1]["role"] == "bot":
            pairs.append({"q": msgs[i]["content"], "a": msgs[i + 1]["content"]})
    with box:
        st.markdown(user_row(q), unsafe_allow_html=True)
        slot = st.empty()
        slot.markdown(thinking_row(), unsafe_allow_html=True)
        try:
            key = q.lower()
            res = _CACHE.get(key) if not pairs else None  # bir xil savol: darhol
            if res is None:
                res = agent.ask(q, pairs[-3:])
                if not pairs and res.get("status") in ("verified", "not_found") and len(_CACHE) < 300:
                    _CACHE[key] = res
        except Exception:  # fon xatolari foydalanuvchiga koʻrsatilmaydi
            res = {"answer": "Kechirasiz, hozir javob bera olmadim. Savolni qayta yuboring.", "status": "error", "steps": []}
        text, tbl = res["answer"], answer_table(res) + basis_html(res)
        stream(slot, text, tbl)
    history.append({"role": "user", "content": q})
    history.append({"role": "bot", "content": text, "table": tbl})