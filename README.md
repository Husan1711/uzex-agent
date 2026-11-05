# Birja reyestri agenti

Rus va oʻzbek tilidagi savollarga 500 000 bitim boʻyicha javob beradigan veb-servis.

## Serverga joylash (Railway)

1. Shu papkani **private** GitHub repozitoriyaga yuklang.
2. railway.com → New Project → Deploy from GitHub repo. Railway `Dockerfile`ni oʻzi topadi.
3. Variables boʻlimiga kiriting:
   - `LLM_PROVIDER` = `anthropic` yoki `openai`
   - `LLM_API_KEY` = kalitingiz
   - `LLM_MODEL` = ixtiyoriy (standart: `claude-sonnet-5-5` yoki `gpt-4o`)
4. Settings → Networking → Generate Domain.
5. `https://<domen>/health` ochilsa va `"llm":true` chiqsa, servis tayyor.

Render’ning bepul tarifi yaroqsiz: u uxlab qoladi va birinchi javob juda kechikadi.

VPS’da: `docker build -t uzex . && docker run -d --restart=always -p 80:8000 --env-file .env uzex`

## Toʻliq sinov (topshirishdan oldin albatta)

```
pip install -r requirements.txt pytest
python -m uzex_agent.prepare
export LLM_PROVIDER=anthropic LLM_API_KEY=...
python -m pytest tests -q   # LLM siz tekshiruvlar
python -m tests.eval        # 42 ta savol: LLM bilan, javob oʻlchanadi
```

## Tuzilishi

- `uzex_agent/build_db.py`: CSV → DuckDB, tovar nomlarini normallashtirish
- `uzex_agent/resolve.py`: kompaniya, broker, tovar, viloyat qidiruvi
- `uzex_agent/db.py`: faqat oʻqish uchun SQL va maʼnoviy ogohlantirishlar
- `uzex_agent/agent.py`, `prompt.py`, `llm.py`: agent sikli
- `uzex_agent/grounding.py`: javobni dalillarga qarshi tekshirish
- `static/index.html`: veb-interfeys

## Streamlit chat (yangi interfeys)

```
pip install -r requirements.txt
cp .env.example .env        # LLM_API_KEY ni kiriting (yoki .streamlit/secrets.toml)
streamlit run streamlit_app.py
```

- Birinchi ishga tushishda `data/uzex.duckdb` avtomatik quriladi (~5 soniya).
- Oynada faqat savol-javob koʻrinadi; SQL, tekshiruvlar va hisoblar fonda bajariladi (`uzex_agent/` oʻzgarmagan).
- Javob “oʻylayapti” nuqtalaridan keyin soʻzma-soʻz yoziladi. Yuqori oʻngdagi **×** suhbatni tozalaydi.
- Dizayn: `streamlit_app.py` ichidagi `CSS` (Uiverse chat: #343541 karta, almashinuvchi qatorlar, `input-place`).
- Eski FastAPI interfeysi ham ishlaydi: `uvicorn uzex_agent.server:app`.
