"""LLM siz tekshiruvlar: python -m pytest tests -q"""
import json
import pytest
from uzex_agent import agent, db, grounding, llm
from uzex_agent.resolve import resolve


def script(*replies):
    """Oldindan yozilgan LLM javoblari."""
    it = iter(replies)

    def fake(system, messages, tools, timeout=45):
        return next(it)

    return fake


def call(name, **args):
    return {"text": "", "calls": [{"id": name + str(len(args)), "name": name, "args": args}]}


def test_verified(monkeypatch):
    monkeypatch.setattr(llm, "chat", script(
        call("run_sql", sql="select count(*) n from deals where deal_year=2024"),
        call("final_answer", answer="В 2024 году **106 647** сделок.", found=True)))
    r = agent.ask("Сколько сделок в 2024?")
    assert r["status"] == "verified"


def test_made_up_number_rejected_then_table(monkeypatch):
    bad = call("final_answer", answer="В 2024 году **555 555** сделок.", found=True)
    monkeypatch.setattr(llm, "chat", script(
        call("run_sql", sql="select count(*) n from deals where deal_year=2024"), bad, bad, bad))
    r = agent.ask("Сколько сделок в 2024?")
    assert r["status"] == "table_only" and "555" not in r["answer"]


def test_answer_without_sql_rejected(monkeypatch):
    bad = call("final_answer", answer="Цена золота 100 сум.", found=True)
    monkeypatch.setattr(llm, "chat", script(bad, bad, bad))
    r = agent.ask("Какая цена золота?")
    assert r["status"] == "not_found" or r["status"] == "error"
    assert "100" not in r["answer"]


def test_not_found(monkeypatch):
    monkeypatch.setattr(llm, "chat", script(
        call("resolve_entity", kind="product", text="золото"),
        call("final_answer", answer="Золота в базе нет.", found=False)))
    r = agent.ask("Какая цена золота?")
    assert r["status"] == "not_found"


def test_llm_down(monkeypatch):
    def boom(*a, **k):
        raise llm.LLMError("x")
    monkeypatch.setattr(llm, "chat", boom)
    assert agent.ask("Сколько сделок?")["status"] == "error"


@pytest.mark.parametrize("sql", [
    "drop table deals", "select 1; select 2", "copy deals to 'x'",
    "select * from read_csv('/etc/passwd')", "install httpfs"])
def test_sql_guard(sql):
    with pytest.raises(db.SqlError):
        db.run_sql(sql)


def test_lint():
    w = db.lint("select sum(amount) from deals")
    assert len(w) == 2
    assert db.lint("select sum(amount_uzs) from deals where not is_cancelled") == []


@pytest.mark.parametrize("kind,text,expect", [
    ("company", "Harayum Kimyo", "915688255"), ("company", "ХАРАЙЎМ КИМЁ", "915688255"),
    ("company", "915688255", "915688255"), ("company", "mate stroy", "962584062")])
def test_company(kind, text, expect):
    r = resolve(kind, text)["results"]
    assert r[0]["inn"] == expect and r[0]["match"] == "exact"


def test_fake_company_not_exact():
    assert not [x for x in resolve("company", "Alfa Trade")["results"] if x["match"] == "exact"]
    assert resolve("company", "123456789")["results"] == []


@pytest.mark.parametrize("text,expect", [
    ("paxta", "Хлопок-сырец"), ("цемента", "Цемент"), ("bug‘doy", "Пшеница"), ("un", "Мука"),
    ("солярка", "Дизельное топливо"), ("g'isht", "Кирпич"), ("guruch", "Рис"), ("карбамид", "Карбамид")])
def test_product(text, expect):
    r = resolve("product", text)["results"]
    assert [x["product"] for x in r] == [expect]


@pytest.mark.parametrize("text", ["золото", "oltin", "нефть", "уголь", "кофе", "пшено"])
def test_absent_product(text):
    assert resolve("product", text)["results"] == []


def test_grounding_formats():
    ev = [{"rows": [[1234567890.55, "2024-03-15", 12.5]]}]
    assert grounding.check("**1 234 567 890,55** сум (1,23 млрд), 15.03.2024, 12,5", "x", ev) == []
    assert grounding.check("1 234 567 899 сум", "x", ev)
