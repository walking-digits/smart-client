"""Модель 2: шанс одобрения (/approval) и поиск похожего предложения с высоким шансом (/alternative).

Используется и сервисом (app.py), и обучением (train.py) — признаки считаются в одном месте.
"""
from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from contract import CATALOG, COLLATERAL_TYPES, GOV_MICRO_MAX_TERM, PRODUCT_TYPES, SECURED_MAX_LTV

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"

# Похожесть на исходное: likelyhood = exp(−(W_AMOUNT·|ln a/a₀| + W_TERM·|ln t/t₀| + W_COLL·|c − c₀| / a₀))
W_AMOUNT = 1.0
W_TERM = 0.5
W_COLL = 1.0
COLL_STEPS = [1.0, 0.75, 0.5, 0.25, 0.0]  # залог-кандидаты — доли исходного (больше исходного нельзя)

CATEGORIES = {
    "legal_form": ["LLC", "IE"],
    "okved_section": list("ABCDEFGHIJKLMNPQRS"),
    "msp_category": ["micro", "small", "medium"],
    "collateral_type": list(COLLATERAL_TYPES),
    "collateral_subtype": [s for subs in COLLATERAL_TYPES.values() for s in subs],
}
NUMERIC = [
    "company_age_months", "revenue_last_year", "revenue_growth_yoy", "net_margin",
    "equity_ratio", "current_ratio", "debt_to_revenue", "taxes_paid_last_year", "tax_arrears_amount",
    "accounts_blocked_flag", "registry_risk_flag", "bankruptcy_flag",
    "fssp_open_amount", "arbitr_defendant_amount_12m", "bki_total_debt", "bki_max_dpd_12m",
    "amount", "term_months", "rate", "collateral_value",
]
# Монотонность: −1 — признак ↑ → шанс ↓, +1 — признак ↑ → шанс ↑. Все признаки суммы — в одну сторону
# (меньше сумма → выше шанс), залог — в другую. Срок и ставку не ограничиваем.
MONOTONE = {"amount": -1, "log_amount": -1, "amount_to_revenue": -1, "dsr": -1,
            "collateral_value": +1, "collateral_ratio": +1}


def make_X(rows: pd.DataFrame) -> pd.DataFrame:
    """rows — поля Company + поля Offer (из CSV или JSON). Пропуски (и вид залога без залога) остаются NaN."""
    X = rows[NUMERIC].astype(float)  # null → NaN, true/false → 1/0
    for col, cats in CATEGORIES.items():
        X[col] = pd.Categorical(rows[col], categories=cats)  # одинаковые коды категорий в обучении и в сервисе
    rev = X["revenue_last_year"]
    X["log_revenue"] = np.log(rev)
    X["tax_burden"] = X["taxes_paid_last_year"] / rev
    X["bki_debt_to_revenue"] = X["bki_total_debt"] / rev
    X["has_bki"] = X["bki_total_debt"].notna().astype(float)
    X["has_fin"] = X["net_margin"].notna().astype(float)
    X["product_type"] = pd.Categorical(rows["product_type"], categories=PRODUCT_TYPES)
    # Предложение
    a, t, r_m = X["amount"], X["term_months"], X["rate"] / 1200
    X["log_amount"] = np.log(a)
    X["amount_to_revenue"] = a / rev
    X["collateral_ratio"] = X["collateral_value"] / a
    payment = a * r_m / (1 - (1 + r_m) ** (-t))            # аннуитетный платёж в месяц
    X["dsr"] = payment * np.minimum(12, t) / rev           # платежи за год / выручка
    return X


# Формальные признаки отказа (REJECT_RULES.md): такие заявки получают шанс 0, модель на них не учится
GOV_OKVED = set("ACDEFHIJQS")
MIN_AGE_PRODUCTS = {"INVESTMENT", "SECURED_RE", "CREDIT_LINE_REV", "GOV_1764"}


def reject_mask(rows: pd.DataFrame) -> np.ndarray:
    """rows — поля Company + Offer. True — заявка не проходит хотя бы одно правило из REJECT_RULES.md."""
    p = rows["product_type"]
    age = rows["company_age_months"]
    rev = rows["revenue_last_year"].astype(float)
    gov = p == "GOV_1764"
    return (rows["accounts_blocked_flag"].astype(bool)                                     # 1
            | rows["bankruptcy_flag"].astype(bool)                                         # 2
            | (age < 3)                                                                    # 3
            | ((age < 12) & p.isin(MIN_AGE_PRODUCTS))                                      # 4
            | (gov & (rows["tax_arrears_amount"] > 50_000))                                # 5
            | (gov & ~rows["okved_section"].isin(GOV_OKVED))                               # 6
            | ((p == "FACTORING") & (rev < 20_000_000))                                    # 7
            | (rows["amount"].astype(float) > rev)).to_numpy()                             # 8


# ---- Быстрый путь для сервиса: признаки сразу в numpy, без pandas ----
# pandas на одной строке тратит ≈ 5 мс, numpy — ≈ 0.05 мс. Значения и порядок — как в make_X
# (train.py сверяет оба пути); порядок проверяется при загрузке модели.
FAST_ORDER = (NUMERIC + list(CATEGORIES) + ["log_revenue", "tax_burden", "bki_debt_to_revenue", "has_bki", "has_fin",
                                            "product_type", "log_amount", "amount_to_revenue", "collateral_ratio", "dsr"])
CAT_INDEX = {col: {v: i for i, v in enumerate(cats)} for col, cats in CATEGORIES.items()}
CAT_INDEX["product_type"] = {p: i for i, p in enumerate(PRODUCT_TYPES)}
COMPANY_NUMERIC = NUMERIC[:16]                               # без amount, term_months, rate, collateral_value


def _num(v):
    return np.nan if v is None else float(v)                 # null → NaN, true/false → 1/0


def _code(col, v):
    return float(CAT_INDEX[col].get(v, np.nan)) if v is not None else np.nan


def features_np(company: dict, offers: list) -> np.ndarray:
    """Признаки для модели: строка на каждое предложение одной компании."""
    n = len(offers)
    X = np.empty((n, len(FAST_ORDER)))
    X[:, :16] = [_num(company[k]) for k in COMPANY_NUMERIC]
    a = np.array([o["amount"] for o in offers], dtype=float)
    t = np.array([o["term_months"] for o in offers], dtype=float)
    r = np.array([o["rate"] for o in offers], dtype=float)
    c = np.array([o["collateral_value"] for o in offers], dtype=float)
    X[:, 16], X[:, 17], X[:, 18], X[:, 19] = a, t, r, c
    X[:, 20] = _code("legal_form", company["legal_form"])
    X[:, 21] = _code("okved_section", company["okved_section"])
    X[:, 22] = _code("msp_category", company["msp_category"])
    X[:, 23] = [_code("collateral_type", o["collateral_type"]) for o in offers]
    X[:, 24] = [_code("collateral_subtype", o["collateral_subtype"]) for o in offers]
    rev, taxes, bki, margin = X[0, 1], X[0, 7], X[0, 14], X[0, 3]
    X[:, 25] = np.log(rev)
    X[:, 26] = taxes / rev
    X[:, 27] = bki / rev
    X[:, 28] = float(not np.isnan(bki))
    X[:, 29] = float(not np.isnan(margin))
    X[:, 30] = [_code("product_type", o["product_type"]) for o in offers]
    r_m = r / 1200
    X[:, 31] = np.log(a)
    X[:, 32] = a / rev
    X[:, 33] = c / a
    payment = a * r_m / (1 - (1 + r_m) ** (-t))
    X[:, 34] = payment * np.minimum(12, t) / rev
    return X


def reject_np(company: dict, offers: list) -> np.ndarray:
    """reject_mask для одной компании без pandas."""
    age, rev = company["company_age_months"], float(company["revenue_last_year"])
    always = bool(company["accounts_blocked_flag"]) or bool(company["bankruptcy_flag"]) or age < 3   # 1–3
    gov_bad = company["tax_arrears_amount"] > 50_000 or company["okved_section"] not in GOV_OKVED   # 5–6
    return np.array([always or (age < 12 and o["product_type"] in MIN_AGE_PRODUCTS)                 # 4
                     or (o["product_type"] == "GOV_1764" and gov_bad)
                     or (o["product_type"] == "FACTORING" and rev < 20_000_000)                     # 7
                     or o["amount"] > rev for o in offers])                                          # 8


def monotone_constraints(columns) -> list:
    return [MONOTONE.get(c, 0) for c in columns]


def load() -> lgb.Booster:
    model = lgb.Booster(model_file=str(ARTIFACTS / "approval.txt"))
    assert model.feature_name() == FAST_ORDER, "порядок признаков модели и features_np разошёлся"
    return model


def predict_rows(model, company: dict, offers: list) -> np.ndarray:
    """Шанс одобрения для нескольких предложений одной компании — одним вызовом модели."""
    p = model.predict(features_np(company, offers), num_threads=1)  # один поток: не мешает параллельным запросам
    return np.where(reject_np(company, offers), 0.0, p)


def approval_probability(model, company: dict, offer: dict) -> float:
    return round(float(predict_rows(model, company, [offer])[0]), 4)


def round2_grid(lo, hi):
    """Все «круглые» суммы (2 значащие цифры) в [lo, hi]: 1.0 млн, 1.1 млн, …, 9.9 млн, 10 млн, 11 млн, …"""
    out = []
    for k in range(int(np.floor(np.log10(lo))) - 1, int(np.floor(np.log10(hi)))):
        out += [m * 10 ** k for m in range(10, 100) if lo <= m * 10 ** k <= hi]
    return out


def search_space(company: dict, offer: dict):
    """Суммы (по возрастанию, ≤ исходной), сроки и залоги (≤ исходного) для поиска альтернативы."""
    p, a0, c0 = offer["product_type"], offer["amount"], offer["collateral_value"]
    cat = CATALOG[p]
    terms = [t for t in cat["terms"]
             if not (p == "GOV_1764" and company["msp_category"] == "micro" and t > GOV_MICRO_MAX_TERM)]
    amounts = sorted(set(round2_grid(cat["amount"][0], a0)) | {a0})
    colls = sorted({int(round(c0 * s)) for s in COLL_STEPS}) if c0 > 0 else [0]
    if cat["collateral"] == "secured":
        colls = [c for c in colls if c > 0]
    return amounts, terms, colls


def make_offer(offer: dict, a, t, c) -> dict:
    """Вариант исходного предложения: тот же продукт и ставка, вид залога — исходный (без залога — null)."""
    return {"product_type": offer["product_type"], "amount": a, "term_months": t, "rate": offer["rate"],
            "collateral_value": c, "collateral_type": offer["collateral_type"] if c else None,
            "collateral_subtype": offer["collateral_subtype"] if c else None}


def max_amount(offer: dict, c) -> float:
    """У SECURED_RE сумма ограничена залогом (LTV); у остальных — только исходной суммой."""
    return SECURED_MAX_LTV * c if CATALOG[offer["product_type"]]["collateral"] == "secured" else np.inf


def candidates(company: dict, offer: dict) -> list:
    """Все варианты (полный перебор) — для проверки быстрого поиска в train.py."""
    amounts, terms, colls = search_space(company, offer)
    return [make_offer(offer, a, t, c) for a in amounts for t in terms for c in colls if a <= max_amount(offer, c)]


def likelyhood(offer: dict, source: dict) -> float:
    d = (W_AMOUNT * abs(np.log(offer["amount"] / source["amount"]))
         + W_TERM * abs(np.log(offer["term_months"] / source["term_months"]))
         + W_COLL * abs(offer["collateral_value"] - source["collateral_value"]) / source["amount"])
    return float(np.exp(-d))


def find_alternative(model, company: dict, offer: dict, gamma: float) -> dict:
    """Ответ /alternative: самое похожее предложение того же продукта с шансом больше gamma."""
    p0 = approval_probability(model, company, offer)
    if p0 > gamma:
        return {"source_approval_probability": p0, "offer": offer, "likelyhood": 1.0, "approval_probability": p0}

    # Шанс не растёт с суммой (монотонность модели, правило 8), а похожесть падает с удалением от исходной суммы.
    # Значит, для каждой пары (срок, залог) лучший вариант — наибольшая сумма с шансом > gamma: ищем её бинарным
    # поиском сразу для всех пар (≈ 7 шагов по ≤ 25 вариантов вместо перебора сотен). Результат — как у перебора.
    amounts, terms, colls = search_space(company, offer)
    pairs = [(t, c) for t in terms for c in colls]
    lo = np.full(len(pairs), -1)                                         # индекс наибольшей проходящей суммы
    hi = np.array([np.searchsorted(amounts, max_amount(offer, c), side="right") - 1 for _, c in pairs])
    passed_p = {}
    while (todo := np.flatnonzero(lo < hi)).size:
        mid = (lo[todo] + hi[todo] + 1) // 2
        probs = predict_rows(model, company, [make_offer(offer, amounts[m], *pairs[k]) for k, m in zip(todo, mid)])
        for k, m, p in zip(todo, mid, probs):
            p = round(float(p), 4)
            if p > gamma:
                lo[k] = m
                passed_p[k, m] = p
            else:
                hi[k] = m - 1
    best = None
    for k in np.flatnonzero(lo >= 0):
        o, p = make_offer(offer, amounts[lo[k]], *pairs[k]), passed_p[k, lo[k]]
        key = (likelyhood(o, offer), p)  # самое похожее, при равенстве — с большим шансом
        if best is None or key > best[0]:
            best = (key, o, p)
    if best is None:
        return {"source_approval_probability": p0, "offer": None, "likelyhood": None, "approval_probability": None}
    (lk, _), o, p = best
    return {"source_approval_probability": p0, "offer": o, "likelyhood": round(lk, 4), "approval_probability": p}
