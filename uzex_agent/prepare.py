"""ZIP arxivdan bazani quradi: python -m uzex_agent.prepare"""
import os
import tempfile
import zipfile

from .build_db import build

ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
with tempfile.TemporaryDirectory() as tmp:
    zipfile.ZipFile(os.path.join(ROOT, "uzex_spot_data.zip")).extractall(tmp)
    src = os.path.join(tmp, "uzex_spot_data")
    build(src, os.path.join(ROOT, "uzex.duckdb"))
print("Baza tayyor")
