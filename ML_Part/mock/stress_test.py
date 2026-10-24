#!/usr/bin/env python3
"""69 тестов ML-сервисов: контракт и краевые случаи, смысл прогнозов, реальные заявки, реальность, устойчивость.

Сервисы должны быть запущены: model1 на localhost:8000, model2 на localhost:8001.
    python mock/stress_test.py          # из папки ML_Part → отчёт TEST_REPORT.md
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import error, request

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract import CATALOG, PRODUCT_TYPES, validate_offer  # noqa: E402
from data import company_from_row, load_applications, offer_from_row, test_mask  # noqa: E402

M1, M2 = "http://localhost:8000", "http://localhost:8001"
REPORT = Path(__file__).resolve().parent.parent / "TEST_REPORT.md"


# --------------------------------------------------------------------------- #
# HTTP и данные
# --------------------------------------------------------------------------- #
def post(url, body=None, raw=None, method="POST"):
    data = raw if raw is not None else (None if body is None else json.dumps(body, ensure_ascii=False).encode())
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    t0 = time.perf_counter()
    try:
        with request.urlopen(req, timeout=60) as r:
            status, txt = r.status, r.read()
    except error.HTTPError as e:
        status, txt = e.code, e.read()
    ms = (time.perf_counter() - t0) * 1000
    try:
        resp = json.loads(txt)
    except ValueError:
        resp = txt.decode("utf-8", "replace")
    return status, resp, ms


def offers(c):
    s, r, _ = post(M1 + "/offers", {"company": c})
    return s, r


def oftenhood(c):
    s, r = offers(c)
    return {it["offer"]["product_type"]: it["oftenhood"] for it in r["offers"]}


def offer_of(c, product):
    return next(it["offer"] for it in offers(c)[1]["offers"] if it["offer"]["product_type"] == product)


def approval(c, o):
    s, r, _ = post(M2 + "/approval", {"company": c, "offer": o})
    return r["approval_probability"] if s == 200 else None


def status_approval(c, o):
    return post(M2 + "/approval", {"company": c, "offer": o})[0]


def alternative(c, o, gamma):
    s, r, _ = post(M2 + "/alternative", {"company": c, "offer": o, "gamma": gamma})
    return s, r


def of(p, a, t, r, c=0, ct=None, cs=None):
    return {"product_type": p, "amount": a, "term_months": t, "rate": r,
            "collateral_value": c, "collateral_type": ct, "collateral_subtype": cs}


def co(base, **kw):
    return {**base, **kw}


DATA = load_applications()
TEST = DATA[test_mask(DATA)].reset_index(drop=True)
# Тренировочные пользователи — из examples.md (JSON-блоки в порядке: IP_TRADE, LLC_BUILD, LLC_MANUF, LLC_TRANS, LLC_RISKY)
_md = (Path(__file__).resolve().parent.parent / "examples.md").read_text(encoding="utf-8")
USERS = dict(zip(["IP_TRADE", "LLC_BUILD", "LLC_MANUF", "LLC_TRANS", "LLC_RISKY"],
                 [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", _md, re.S)]))
IP, BUILD, MANUF, TRANS, RISKY = (USERS[k] for k in USERS)
WC = of("WORKING_CAPITAL", 10_000_000, 24, 20.0)  # базовое предложение для LLC_BUILD
NULLABLE = ["revenue_growth_yoy", "net_margin", "equity_ratio", "current_ratio", "debt_to_revenue",
            "bki_total_debt", "bki_max_dpd_12m"]


# --------------------------------------------------------------------------- #
# Тесты: каждый возвращает (пройден, что выдала модель)
# --------------------------------------------------------------------------- #
TESTS = []


def test(endpoint, kind, goal, expected):
    def wrap(fn):
        TESTS.append({"endpoint": endpoint, "kind": kind, "goal": goal, "expected": expected, "fn": fn})
        return fn
    return wrap


def fmt(x):
    return f"{x:.3f}" if isinstance(x, float) else str(x)


# ---------------------------- /offers ---------------------------------------
@test("/offers", "Контракт", "Формат ответа для всех 5 пользователей",
      "10 предложений, каждый продукт ровно один раз, по убыванию oftenhood, все условия в каталоге")
def _():
    bad = []
    for name, c in USERS.items():
        s, r = offers(c)
        items = r["offers"]
        types = [it["offer"]["product_type"] for it in items]
        often = [it["oftenhood"] for it in items]
        errs = [e for it in items for e in validate_offer(it["offer"], c["msp_category"], with_collateral_type=False)]
        if s != 200 or sorted(types) != sorted(PRODUCT_TYPES) or often != sorted(often, reverse=True) or errs:
            bad.append(name)
    return not bad, "все 5 ответов корректны" if not bad else f"ошибки у {bad}"


@test("/offers", "Устойчивость", "Детерминизм", "Два одинаковых запроса — одинаковый ответ")
def _():
    a, b = offers(MANUF)[1], offers(MANUF)[1]
    return a == b, "ответы совпали" if a == b else "ответы различаются"


@test("/offers", "Смысл", "Суммы растут с размером бизнеса",
      "У ООО с выручкой 2 млрд сумма по каждому продукту не меньше, чем у ИП с выручкой 13.8 млн")
def _():
    small = {it["offer"]["product_type"]: it["offer"]["amount"] for it in offers(IP)[1]["offers"]}
    big = {it["offer"]["product_type"]: it["offer"]["amount"] for it in offers(TRANS)[1]["offers"]}
    worse = [p for p in PRODUCT_TYPES if big[p] < small[p]]
    return not worse, (f"WORKING_CAPITAL: {small['WORKING_CAPITAL']:,} → {big['WORKING_CAPITAL']:,}; "
                       + ("нарушений нет" if not worse else f"меньше у {worse}"))


@test("/offers", "Краевой случай", "Выручка 1 рубль",
      "200, без падения; все суммы прижаты к минимуму продукта")
def _():
    s, r = offers(co(BUILD, revenue_last_year=1, taxes_paid_last_year=0))
    if s != 200:
        return False, f"HTTP {s}: {r}"
    not_min = [it["offer"]["product_type"] for it in r["offers"]
               if it["offer"]["amount"] != CATALOG[it["offer"]["product_type"]]["amount"][0]]
    return not not_min, "все суммы = минимум продукта" if not not_min else f"не минимум у {not_min}"


@test("/offers", "Краевой случай", "Выручка 10 млрд (больше потолка medium)",
      "200, суммы не выходят за максимум каталога")
def _():
    c = co(TRANS, revenue_last_year=10_000_000_000)
    s, r = offers(c)
    errs = [e for it in r["offers"] for e in validate_offer(it["offer"], c["msp_category"], with_collateral_type=False)]
    inv = next(it["offer"]["amount"] for it in r["offers"] if it["offer"]["product_type"] == "INVESTMENT")
    return s == 200 and not errs, f"INVESTMENT {inv:,} (максимум 500 000 000); нарушений {len(errs)}"


@test("/offers", "Смысл", "ИП и кредитная линия",
      "У ИП oftenhood CREDIT_LINE_REV ниже, чем у ООО с выручкой больше 30 млн")
def _():
    a, b = oftenhood(IP)["CREDIT_LINE_REV"], oftenhood(BUILD)["CREDIT_LINE_REV"]
    return a < b, f"ИП {a:.3f}, ООО {b:.3f}"


@test("/offers", "Смысл", "Факторинг нужен крупным торговым",
      "У ИП с выручкой 13.8 млн oftenhood FACTORING < 0.05; у торгового ООО с выручкой 2 млрд — выше")
def _():
    small, big = oftenhood(IP)["FACTORING"], oftenhood(co(TRANS, okved_section="G"))["FACTORING"]
    return small < 0.05 and big > small, f"ИП {small:.3f}, крупное торговое ООО {big:.3f}"


@test("/offers", "Смысл", "Льготная программа 1764 — только приоритетные отрасли",
      "У торговли (G) oftenhood GOV_1764 ниже, чем у той же компании в строительстве (F)")
def _():
    f, g = oftenhood(BUILD)["GOV_1764"], oftenhood(co(BUILD, okved_section="G"))["GOV_1764"]
    return g < f, f"строительство {f:.3f}, торговля {g:.3f}"


@test("/offers", "Смысл", "Молодой компании инвесткредит нужен реже",
      "oftenhood INVESTMENT у компании 6 мес. ниже, чем у той же компании 120 мес.")
def _():
    young, old = (oftenhood(co(MANUF, company_age_months=a))["INVESTMENT"] for a in (6, 120))
    return young < old, f"6 мес. {young:.3f}, 120 мес. {old:.3f}"


@test("/offers", "Краевой случай", "Все необязательные поля null (нет отчётности и БКИ)",
      "200, предложения в каталоге")
def _():
    c = co(BUILD, **{k: None for k in NULLABLE})
    s, r = offers(c)
    errs = [e for it in r["offers"] for e in validate_offer(it["offer"], c["msp_category"], with_collateral_type=False)] \
        if s == 200 else ["нет ответа"]
    return s == 200 and not errs, f"HTTP {s}, нарушений {len(errs)}"


@test("/offers", "Контракт", "Правила программы 1764",
      "micro: сумма ≤ 10 млн, срок ≤ 36, ставка 17.5; small: ставка 16.75")
def _():
    m, s = offer_of(BUILD, "GOV_1764"), offer_of(MANUF, "GOV_1764")
    ok = m["amount"] <= 10_000_000 and m["term_months"] <= 36 and m["rate"] == 17.5 and s["rate"] == 16.75
    return ok, (f"micro: {m['amount']:,}, {m['term_months']} мес., {m['rate']}%; small: {s['rate']}%")


@test("/offers", "Контракт", "Кредит под залог недвижимости соблюдает LTV",
      "У всех 5 пользователей SECURED_RE: сумма ≤ 0.7 × залог")
def _():
    ltv = [offer_of(c, "SECURED_RE") for c in USERS.values()]
    worst = max(o["amount"] / o["collateral_value"] for o in ltv)
    return worst <= 0.7, f"максимальный LTV {worst:.3f}"


@test("/offers", "Устойчивость", "Лишнее поле в Company",
      "Поле вне контракта игнорируется: 200")
def _():
    s, _ = offers(co(BUILD, name="ООО «Ромашка»"))
    return s == 200, f"HTTP {s}"


@test("/offers", "Контракт", "Неверные данные компании",
      "ИНН из 11 цифр → 422; флаг строкой \"false\" → 422")
def _():
    a = offers(co(BUILD, inn="50052431651"))[0]
    b = offers(co(BUILD, accounts_blocked_flag="false"))[0]
    return a == 422 and b == 422, f"ИНН: {a}, флаг: {b}"


@test("/offers", "Контракт", "Пустое тело и не JSON", "422 в обоих случаях")
def _():
    a = post(M1 + "/offers", raw=b"")[0]
    b = post(M1 + "/offers", raw="не json".encode())[0]
    return a == 422 and b == 422, f"пустое: {a}, не JSON: {b}"


# ---------------------------- /approval -------------------------------------
@test("/approval", "Смысл", "Больше сумма — ниже шанс",
      "Сумма 5 → 10 → 20 → 40 → 80 млн: шанс не растёт")
def _():
    ps = [approval(BUILD, co(WC, amount=a * 1_000_000)) for a in (5, 10, 20, 40, 80)]
    ok = all(b <= a + 1e-9 for a, b in zip(ps, ps[1:]))
    return ok, " → ".join(f"{p:.3f}" for p in ps)


@test("/approval", "Смысл", "Больше залог — выше шанс",
      "Залог 0 → 5 → 10 → 20 млн (склад): шанс не падает")
def _():
    ps = [approval(BUILD, co(WC, collateral_value=c, collateral_type="REAL_ESTATE" if c else None,
                                  collateral_subtype="WAREHOUSE" if c else None)) for c in (0, 5_000_000, 10_000_000, 20_000_000)]
    ok = all(b >= a - 1e-9 for a, b in zip(ps, ps[1:]))
    return ok, " → ".join(f"{p:.3f}" for p in ps)


@test("/approval", "Смысл", "Ликвидность вида залога",
      "При одинаковой стоимости залог-депозит даёт шанс не ниже, чем товары в обороте")
def _():
    dep = approval(BUILD, co(WC, collateral_value=10_000_000, collateral_type="FINANCIAL", collateral_subtype="DEPOSIT"))
    goods = approval(BUILD, co(WC, collateral_value=10_000_000, collateral_type="INVENTORY", collateral_subtype="GOODS"))
    return dep >= goods, f"депозит {dep:.3f}, товары {goods:.3f}"


@test("/approval", "Смысл", "Просрочка в БКИ", "Просрочка 120 дней — шанс ниже, чем без просрочек")
def _():
    a, b = approval(BUILD, WC), approval(co(BUILD, bki_max_dpd_12m=120), WC)
    return b < a, f"без просрочки {a:.3f}, 120 дней {b:.3f}"


@test("/approval", "Смысл", "Налоговый долг", "Долг 500 тыс. — шанс ниже, чем без долга")
def _():
    a, b = approval(BUILD, WC), approval(co(BUILD, tax_arrears_amount=500_000), WC)
    return b < a, f"без долга {a:.3f}, с долгом {b:.3f}"


@test("/approval", "Смысл", "Заблокированные счета", "Шанс почти 0 (< 0.05) — жёсткий отказ")
def _():
    p = approval(co(BUILD, accounts_blocked_flag=True), WC)
    return p < 0.05, f"{p:.4f}"


@test("/approval", "Смысл", "Банкротство", "Шанс почти 0 (< 0.05)")
def _():
    p = approval(co(BUILD, bankruptcy_flag=True), WC)
    return p < 0.05, f"{p:.4f}"


@test("/approval", "Смысл", "Компании 2 месяца", "Шанс почти 0 (< 0.05)")
def _():
    p = approval(co(BUILD, company_age_months=2), WC)
    return p < 0.05, f"{p:.4f}"


@test("/approval", "Смысл", "Факторинг при выручке < 20 млн", "Шанс почти 0 (< 0.05)")
def _():
    p = approval(co(BUILD, revenue_last_year=15_000_000), of("FACTORING", 2_000_000, 3, 24.0))
    return p < 0.05, f"{p:.4f}"


@test("/approval", "Смысл", "Программа 1764 в неприоритетной отрасли",
      "Торговля (G): шанс почти 0 (< 0.05), строительство (F) — заметно выше")
def _():
    o = of("GOV_1764", 8_000_000, 36, 17.5)
    f, g = approval(BUILD, o), approval(co(BUILD, okved_section="G"), o)
    return g < 0.05 < f, f"строительство {f:.3f}, торговля {g:.4f}"


@test("/approval", "Смысл", "Отрицательный капитал", "Капитал −50% активов — шанс ниже, чем при +40%")
def _():
    o = of("CREDIT_LINE_REV", 40_000_000, 18, 20.0)
    a, b = approval(co(MANUF, equity_ratio=0.4), o), approval(co(MANUF, equity_ratio=-0.5), o)
    return b < a, f"+40%: {a:.3f}, −50%: {b:.3f}"


@test("/approval", "Смысл", "Крупная компания без долгов и исков, небольшая сумма",
      "ООО с выручкой 2 млрд без налогового долга и исков, ликвидность 1.5, оборотный 5 млн на год — шанс > 0.8")
def _():
    clean = co(TRANS, tax_arrears_amount=0, arbitr_defendant_amount_12m=0, current_ratio=1.5)
    p = approval(clean, of("WORKING_CAPITAL", 5_000_000, 12, 20.0))
    return p > 0.8, f"{p:.3f}"


@test("/approval", "Краевой случай", "Сумма 1 000 000 000 на оборотный кредит",
      "422: максимум продукта 100 млн")
def _():
    s = status_approval(BUILD, co(WC, amount=1_000_000_000))
    return s == 422, f"HTTP {s}"


@test("/approval", "Краевой случай", "Граница суммы", "Ровно 100 000 000 → 200; 100 000 001 → 422")
def _():
    a, b = status_approval(BUILD, co(WC, amount=100_000_000)), status_approval(BUILD, co(WC, amount=100_000_001))
    return a == 200 and b == 422, f"{a}, {b}"


@test("/approval", "Краевой случай", "Граница LTV для SECURED_RE",
      "Сумма ровно 0.7 × залог → 200; на 1 ₽ больше → 422")
def _():
    o = of("SECURED_RE", 70_000_000, 60, 17.0, 100_000_000, "REAL_ESTATE", "OFFICE")
    a, b = status_approval(TRANS, o), status_approval(TRANS, co(o, amount=70_000_001))
    return a == 200 and b == 422, f"{a}, {b}"


@test("/approval", "Контракт", "Ставка", "Овердрафт под 50% → 422; ставка 20.05 (2 знака) → 422")
def _():
    a = status_approval(BUILD, of("OVERDRAFT", 1_000_000, 12, 50.0))
    b = status_approval(BUILD, co(WC, rate=20.05))
    return a == 422 and b == 422, f"{a}, {b}"


@test("/approval", "Контракт", "Срок не из сетки", "Оборотный на 7 мес. → 422")
def _():
    s = status_approval(BUILD, co(WC, term_months=7))
    return s == 422, f"HTTP {s}"


@test("/approval", "Краевой случай", "Лимиты 1764 для micro",
      "10 000 000 → 200; 10 000 001 → 422; срок 60 → 422")
def _():
    o = of("GOV_1764", 10_000_000, 36, 17.5)
    r = [status_approval(BUILD, o), status_approval(BUILD, co(o, amount=10_000_001)),
         status_approval(BUILD, co(o, term_months=60))]
    return r == [200, 422, 422], ", ".join(map(str, r))


@test("/approval", "Контракт", "Залог и его вид",
      "Отрицательный залог, дробный залог, вид без залога, SECURED_RE под транспорт → 422")
def _():
    r = [status_approval(BUILD, co(WC, collateral_value=-1)),
         status_approval(BUILD, co(WC, collateral_value=5_000_000.5, collateral_type="REAL_ESTATE",
                                   collateral_subtype="OFFICE")),
         status_approval(BUILD, co(WC, collateral_type="VEHICLES", collateral_subtype="CAR")),
         status_approval(TRANS, of("SECURED_RE", 50_000_000, 60, 17.0, 100_000_000, "VEHICLES", "TRUCK"))]
    return r == [422] * 4, ", ".join(map(str, r))


@test("/approval", "Реальные данные", "Калибровка и качество на 2000 тестовых заявках",
      "Средний прогноз ≈ доле одобрений (±0.03); AUC > 0.80")
def _():
    rows = TEST.sample(2000, random_state=1).to_dict("records")
    with ThreadPoolExecutor(8) as ex:
        ps = list(ex.map(lambda r: approval(company_from_row(r), offer_from_row(r)), rows))
    y = np.array([r["approved"] for r in rows])
    p = np.array(ps)
    rk = pd.Series(p).rank().to_numpy()
    n1, n0 = y.sum(), (1 - y).sum()
    auc = (rk[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
    return abs(p.mean() - y.mean()) <= 0.03 and auc > 0.8, f"прогноз {p.mean():.3f}, факт {y.mean():.3f}, AUC {auc:.3f}"


# ---------------------------- /alternative ----------------------------------
@test("/alternative", "Контракт", "Исходное проходит порог",
      "Возвращается исходное предложение, likelyhood = 1")
def _():
    o = of("BUSINESS_CARD", 300_000, 36, 25.0)
    s, r = alternative(IP, o, 0.5)
    return s == 200 and r["offer"] == o and r["likelyhood"] == 1, \
        f"шанс {r['source_approval_probability']}, likelyhood {r['likelyhood']}"


@test("/alternative", "Краевой случай", "gamma = 0", "Любой шанс больше 0 проходит → исходное")
def _():
    o = of("WORKING_CAPITAL", 6_000_000, 24, 24.0)
    s, r = alternative(RISKY, o, 0)
    return s == 200 and r["offer"] == o, f"исходный шанс {r['source_approval_probability']}, вернулось исходное: {r['offer'] == o}"


@test("/alternative", "Краевой случай", "gamma = 1", "Шанс не бывает больше 1 → offer = null")
def _():
    s, r = alternative(BUILD, WC, 1)
    return s == 200 and r["offer"] is None, f"offer = {r['offer']}"


@test("/alternative", "Смысл", "Заблокированные счета", "Никакое изменение условий не помогает → null")
def _():
    s, r = alternative(co(BUILD, accounts_blocked_flag=True), WC, 0.5)
    return s == 200 and r["offer"] is None, f"исходный {r['source_approval_probability']}, offer = {r['offer']}"


def alt_sample(n=100, gamma=0.7):
    rows = TEST.sample(n, random_state=2).to_dict("records")
    def run(row):
        c, o = company_from_row(row), offer_from_row(row)
        return c, o, alternative(c, o, gamma)[1]
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(run, rows))


ALT = []


@test("/alternative", "Реальные данные", "Ограничения на 100 тестовых заявках (gamma 0.7)",
      "Найденное: тот же продукт, шанс > 0.7, сумма и залог не больше исходных, вид залога и ставка те же, контракт")
def _():
    ALT.extend(alt_sample())
    bad, found = [], 0
    for c, o, r in ALT:
        a = r["offer"]
        if a is None or a == o:
            continue
        found += 1
        ok = (a["product_type"] == o["product_type"] and r["approval_probability"] > 0.7
              and a["amount"] <= o["amount"] and a["collateral_value"] <= o["collateral_value"]
              and a["rate"] == o["rate"] and not validate_offer(a, c["msp_category"])
              and (a["collateral_value"] == 0 or a["collateral_subtype"] == o["collateral_subtype"]))
        bad += [] if ok else [o["product_type"]]
    passed = sum(1 for _, _, r in ALT if r["offer"] is not None and r["likelyhood"] == 1)
    nulls = sum(1 for _, _, r in ALT if r["offer"] is None)
    return not bad, f"исходное прошло {passed}, найдено {found}, null {nulls}; нарушений {len(bad)}"


@test("/alternative", "Контракт", "Согласованность с /approval",
      "source_approval_probability и approval_probability совпадают с /approval для тех же предложений")
def _():
    diff = 0.0
    for c, o, r in ALT[:40]:
        diff = max(diff, abs(approval(c, o) - r["source_approval_probability"]))
        if r["offer"] is not None:
            diff = max(diff, abs(approval(c, r["offer"]) - r["approval_probability"]))
    return diff < 1e-3, f"максимальное расхождение {diff:.5f}"


@test("/alternative", "Краевой случай", "Максимальная сумма продукта у небольшой компании",
      "Инвесткредит 500 млн при выручке 52 млн: предложена меньшая сумма или null; ответ быстрее 1 с")
def _():
    o = of("INVESTMENT", 500_000_000, 60, 18.0)
    t0 = time.perf_counter()
    s, r = alternative(BUILD, o, 0.7)
    ms = (time.perf_counter() - t0) * 1000
    a = r["offer"]
    ok = s == 200 and ms < 1000 and (a is None or a["amount"] < 500_000_000)
    found = "null" if a is None else f"{a['amount']:,} на {a['term_months']} мес."
    return ok, f"{found}, шанс {r['approval_probability']}, {ms:.0f} мс"


@test("/alternative", "Контракт", "LTV в альтернативе к SECURED_RE",
      "Найденное предложение под залог недвижимости соблюдает сумма ≤ 0.7 × залог")
def _():
    o = of("SECURED_RE", 140_000_000, 36, 17.0, 200_000_000, "REAL_ESTATE", "OFFICE")
    s, r = alternative(TRANS, o, 0.8)
    a = r["offer"]
    ok = s == 200 and (a is None or a["amount"] <= 0.7 * a["collateral_value"])
    return ok, "null" if a is None else f"{a['amount']:,} при залоге {a['collateral_value']:,}, шанс {r['approval_probability']}"


@test("/alternative", "Краевой случай", "Сумма уже на минимуме продукта",
      "Экспресс 300 тыс. у рискованной компании, порог 0.9: уменьшать некуда — null или другой срок, сумма не ниже 300 тыс.")
def _():
    s, r = alternative(RISKY, of("EXPRESS_UNSECURED", 300_000, 6, 24.0), 0.9)
    a = r["offer"]
    return s == 200 and (a is None or a["amount"] >= 300_000), "null" if a is None else str(a)


@test("/alternative", "Контракт", "Неверный gamma", "gamma строкой \"0.7\" → 422; gamma −0.1 → 422")
def _():
    a = post(M2 + "/alternative", {"company": BUILD, "offer": WC, "gamma": "0.7"})[0]
    b = post(M2 + "/alternative", {"company": BUILD, "offer": WC, "gamma": -0.1})[0]
    return a == 422 and b == 422, f"{a}, {b}"


@test("/alternative", "Контракт", "Лимиты 1764 для micro в альтернативе",
      "Найденное предложение: срок ≤ 36, сумма ≤ 10 млн, ставка 17.5")
def _():
    s, r = alternative(BUILD, of("GOV_1764", 10_000_000, 36, 17.5), 0.95)
    a = r["offer"]
    ok = s == 200 and (a is None or (a["term_months"] <= 36 and a["amount"] <= 10_000_000 and a["rate"] == 17.5))
    return ok, "null" if a is None else f"{a['amount']:,} на {a['term_months']} мес., {a['rate']}%, шанс {r['approval_probability']}"


# ---------------------------- Реальность ------------------------------------
UNREAL = 0.001  # «нереальная» заявка: шанс < 0.1% (в процентах — 0.0%)
POOR_IP = co(IP, revenue_last_year=1_000_000, taxes_paid_last_year=60_000)


def dsr(o, revenue):
    r = o["rate"] / 1200
    pay = o["amount"] * r / (1 - (1 + r) ** (-o["term_months"]))
    return pay * min(12, o["term_months"]) / revenue


def unreal_test(goal, company, o):
    @test("/approval", "Реальность", goal,
          f"Платежи за год в {dsr(o, company['revenue_last_year']):.1f} раза больше выручки — шанс ≈ 0 (< 0.1%)")
    def _():
        p = approval(company, o)
        return p < UNREAL, f"{p:.4f} ({p:.2%})"


unreal_test("ИП с выручкой 1 млн просит оборотный 100 млн без залога", POOR_IP, of("WORKING_CAPITAL", 100_000_000, 12, 20.0))
unreal_test("ИП с выручкой 1 млн просит экспресс-кредит 10 млн", POOR_IP, of("EXPRESS_UNSECURED", 10_000_000, 36, 24.0))
unreal_test("ИП с выручкой 1 млн просит бизнес-карту 5 млн", POOR_IP, of("BUSINESS_CARD", 5_000_000, 36, 25.0))
unreal_test("ИП с выручкой 13.8 млн просит овердрафт 50 млн", IP, of("OVERDRAFT", 50_000_000, 12, 21.5))
unreal_test("ООО с выручкой 52 млн просит оборотный 100 млн на год", BUILD, of("WORKING_CAPITAL", 100_000_000, 12, 20.0))
unreal_test("ООО с выручкой 52 млн просит инвесткредит 500 млн", BUILD, of("INVESTMENT", 500_000_000, 120, 18.0))
unreal_test("ООО с выручкой 13.4 млн просит кредитную линию 60 млн", RISKY, of("CREDIT_LINE_REV", 60_000_000, 12, 20.0))


@test("/approval", "Реальность", "Обрыв шанса с ростом суммы",
      "ООО с выручкой 52 млн, оборотный на год 10 → 100 млн: шанс падает до ≈ 0 к 100 млн")
def _():
    ps = [approval(BUILD, co(WC, amount=a * 1_000_000, term_months=12)) for a in (10, 20, 40, 60, 80, 100)]
    ok = all(b <= a + 1e-9 for a, b in zip(ps, ps[1:])) and ps[-1] < UNREAL
    return ok, " → ".join(f"{p:.3f}" for p in ps)


@test("/approval", "Реальность", "Контроль: реалистичная заявка той же компании",
      "ООО с выручкой 52 млн, оборотный 10 млн на 2 года — нормальный шанс (> 0.5)")
def _():
    p = approval(BUILD, WC)
    return p > 0.5, f"{p:.3f}"


@test("/approval", "Реальность", "Контроль: крупная сумма у крупной компании",
      "ООО с выручкой 2 млрд без долгов, оборотный 100 млн — реалистично (> 0.5)")
def _():
    clean = co(TRANS, tax_arrears_amount=0, arbitr_defendant_amount_12m=0, current_ratio=1.5)
    p = approval(clean, of("WORKING_CAPITAL", 100_000_000, 12, 20.0))
    return p > 0.5, f"{p:.3f}"


@test("/approval", "Реальность", "Неподъёмные заявки в тестовых данных",
      "Все тестовые заявки с платежами больше выручки в 2+ раза: средний шанс < 0.5%, 95% заявок < 1%")
def _():
    t = TEST[TEST.product_type != "FACTORING"]
    r = t.rate / 1200
    d2 = t.amount * r / (1 - (1 + r) ** (-t.term_months)) * np.minimum(12, t.term_months) / t.revenue_last_year
    rows = t[d2 > 2].to_dict("records")
    with ThreadPoolExecutor(8) as ex:
        ps = np.array(list(ex.map(lambda row: approval(company_from_row(row), offer_from_row(row)), rows)))
    return ps.mean() < 0.005 and np.percentile(ps, 95) < 0.01, \
        f"заявок {len(ps)}, средний {ps.mean():.4f}, 95% — {np.percentile(ps, 95):.4f}, максимум {ps.max():.4f}"


@test("/alternative", "Реальность", "Альтернатива к нереальной заявке",
      "ИП с выручкой 1 млн просит 100 млн, порог 0.7: предложена посильная сумма (≤ 2 млн) или null")
def _():
    s, r = alternative(POOR_IP, of("WORKING_CAPITAL", 100_000_000, 12, 20.0), 0.7)
    a = r["offer"]
    ok = s == 200 and (a is None or a["amount"] <= 2_000_000)
    return ok, f"исходный {r['source_approval_probability']:.4f} → " + (
        "null" if a is None else f"{a['amount']:,} на {a['term_months']} мес., шанс {r['approval_probability']}")


def office(amount_coll):
    return {"collateral_value": int(amount_coll), "collateral_type": "REAL_ESTATE", "collateral_subtype": "OFFICE"}


@test("/approval", "Реальность", "Залог заметно помогает крупному кредиту",
      "ООО с выручкой 52 млн, оборотный 25 млн (≈ половина выручки): полное покрытие офисом "
      "(залог = сумма / 0.7) поднимает шанс минимум на 20 п.п.")
def _():
    o = of("WORKING_CAPITAL", 25_000_000, 24, 20.0)
    p0, p1 = approval(BUILD, o), approval(BUILD, co(o, **office(25_000_000 / 0.7)))
    return p1 - p0 >= 0.20, f"без залога {p0:.3f}, с залогом {p1:.3f} (+{100 * (p1 - p0):.0f} п.п.)"


@test("/approval", "Реальность", "Плато после полного покрытия",
      "Тот же кредит: залог 1.7 → 2.9 → 4.3 суммы (покрытие 1.2 → 2 → 3 после дисконта) — шанс растёт не больше чем на 3 п.п.")
def _():
    o = of("WORKING_CAPITAL", 25_000_000, 24, 20.0)
    ps = [approval(BUILD, co(o, **office(25_000_000 * k / 0.7))) for k in (1.2, 2, 3)]
    return ps[-1] - ps[0] <= 0.03, " → ".join(f"{p:.3f}" for p in ps)


@test("/approval", "Реальность", "Кредит больше годовой выручки — даже на 10 лет и под полный залог",
      "ООО с выручкой 52 млн, инвесткредит 60 млн на 120 мес. под офис 90 млн — лимит кредитования, шанс ≈ 0 (< 0.1%)")
def _():
    p = approval(BUILD, co(of("INVESTMENT", 60_000_000, 120, 18.0), **office(90_000_000)))
    return p < UNREAL, f"{p:.4f} ({p:.2%})"


@test("/approval", "Реальность", "Залог не спасает неподъёмную заявку",
      "ООО с выручкой 52 млн просит 100 млн на год под депозит 150 млн — платить нечем, шанс ≈ 0 (< 0.1%)")
def _():
    o = of("WORKING_CAPITAL", 100_000_000, 12, 20.0, 150_000_000, "FINANCIAL", "DEPOSIT")
    p = approval(BUILD, o)
    return p < UNREAL, f"{p:.4f} ({p:.2%})"


CLEAN_TRANS = co(TRANS, tax_arrears_amount=0, arbitr_defendant_amount_12m=0, current_ratio=1.5)


@test("/approval", "Реальность", "Крупная надёжная компания, сумма 1% выручки",
      "ООО с выручкой 2 млрд без долгов и исков, оборотный 20 млн на год — шанс ≈ 100% (> 98%)")
def _():
    p = approval(CLEAN_TRANS, of("WORKING_CAPITAL", 20_000_000, 12, 20.0))
    return p > 0.98, f"{p:.4f} ({p:.2%})"


@test("/approval", "Реальность", "Производственная компания, сумма 1% выручки",
      "ООО с выручкой 320 млн, прибыльное, без долгов, овердрафт 3 млн — шанс ≈ 100% (> 98%)")
def _():
    p = approval(MANUF, of("OVERDRAFT", 3_000_000, 12, 21.5))
    return p > 0.98, f"{p:.4f} ({p:.2%})"


@test("/approval", "Реальность", "Маленькая сумма не спасает плохую историю",
      "Та же крупная компания, но просрочка 120 дней и налоговый долг 1 млн: 20 млн — заметно ниже 98%")
def _():
    p = approval(co(CLEAN_TRANS, bki_max_dpd_12m=120, tax_arrears_amount=1_000_000), of("WORKING_CAPITAL", 20_000_000, 12, 20.0))
    return p < 0.95, f"{p:.4f} ({p:.2%})"


# ---------------------------- Устойчивость ----------------------------------
@test("все", "Устойчивость", "50 параллельных запросов на каждую ручку", "Все ответы 200")
def _():
    jobs = [(M1 + "/offers", {"company": IP})] * 50 + [(M2 + "/approval", {"company": BUILD, "offer": WC})] * 50 \
        + [(M2 + "/alternative", {"company": BUILD, "offer": WC, "gamma": 0.8})] * 50
    with ThreadPoolExecutor(50) as ex:
        codes = list(ex.map(lambda j: post(*j)[0], jobs))
    return all(c == 200 for c in codes), f"200: {codes.count(200)} из {len(codes)}"


@test("все", "Устойчивость", "Время ответа (по 30 последовательных запросов)",
      "p95: /offers и /approval < 150 мс, /alternative < 500 мс")
def _():
    def p95(url, body):
        return np.percentile([post(url, body)[2] for _ in range(30)], 95)
    a = p95(M1 + "/offers", {"company": MANUF})
    b = p95(M2 + "/approval", {"company": BUILD, "offer": WC})
    c = p95(M2 + "/alternative", {"company": BUILD, "offer": of("INVESTMENT", 500_000_000, 60, 18.0), "gamma": 0.7})
    return a < 150 and b < 150 and c < 500, f"/offers {a:.0f} мс, /approval {b:.0f} мс, /alternative {c:.0f} мс"


@test("все", "Устойчивость", "Тело 1 МБ мусора", "422, сервисы после этого живы")
def _():
    junk = b"{" + b"x" * 1_000_000
    a, b = post(M1 + "/offers", raw=junk)[0], post(M2 + "/approval", raw=junk)[0]
    alive = all(post(u + "/health", method="GET")[0] == 200 for u in (M1, M2))
    return a == 422 and b == 422 and alive, f"{a}, {b}; health: {'ок' if alive else 'нет ответа'}"


@test("все", "Устойчивость", "Неверный метод и адрес", "GET /offers → 405; POST /unknown → 404")
def _():
    a = post(M1 + "/offers", method="GET")[0]
    b = post(M2 + "/unknown", {})[0]
    return a == 405 and b == 404, f"{a}, {b}"


# --------------------------------------------------------------------------- #
# Запуск и отчёт
# --------------------------------------------------------------------------- #
def main():
    assert len(TESTS) == 69, len(TESTS)
    for i, t in enumerate(TESTS, 1):
        t0 = time.perf_counter()
        try:
            t["ok"], t["actual"] = t["fn"]()
        except Exception as e:  # тест сам по себе упал — это тоже результат
            t["ok"], t["actual"] = False, f"исключение: {type(e).__name__}: {e}"
        t["sec"] = time.perf_counter() - t0
        print(f"{i:2d}. {'✅' if t['ok'] else '❌'} {t['endpoint']:<12} {t['goal']} — {t['actual']}")
    n_ok = sum(t["ok"] for t in TESTS)
    kinds = pd.DataFrame(TESTS).groupby("kind")["ok"].agg(["sum", "size"])
    lines = [
        "# Отчёт о тестировании ML-сервисов", "",
        f"Пройдено **{n_ok} из {len(TESTS)}**. Тесты — `mock/stress_test.py`, запросы шли по HTTP к запущенным",
        "сервисам (model1 — `/offers`, model2 — `/approval`, `/alternative`).", "",
        "| Направление | Пройдено |", "|---|---|",
        *[f"| {k} | {int(r['sum'])} из {int(r['size'])} |" for k, r in kinds.iterrows()],
        "", "| № | Ручка | Направление | На что направлен | Ожидалось по смыслу | Что выдала модель | Итог |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, t in enumerate(TESTS, 1):
        lines.append(f"| {i} | `{t['endpoint']}` | {t['kind']} | {t['goal']} | {t['expected']} | "
                     f"{t['actual'].replace('|', '/')} | {'✅' if t['ok'] else '❌'} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nПройдено {n_ok} из {len(TESTS)}. Отчёт: {REPORT}")


if __name__ == "__main__":
    main()
