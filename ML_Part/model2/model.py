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


def monotone_constraints(columns) -> list:
    return [MONOTONE.get(c, 0) for c in columns]


def load() -> lgb.Booster:
    return lgb.Booster(model_file=str(ARTIFACTS / "approval.txt"))


def predict_rows(model, company: dict, offers: list) -> np.ndarray:
    """Шанс одобрения для нескольких предложений одной компании — одним вызовом модели."""
    rows = pd.DataFrame([{**company, **o} for o in offers])
    p = model.predict(make_X(rows), num_threads=1)  # один поток: не мешает параллельным запросам
    return np.where(reject_mask(rows), 0.0, p)


def approval_probability(model, company: dict, offer: dict) -> float:
    return round(float(predict_rows(model, company, [offer])[0]), 4)


def round2_grid(lo, hi):
    """Все «круглые» суммы (2 значащие цифры) в [lo, hi]: 1.0 млн, 1.1 млн, …, 9.9 млн, 10 млн, 11 млн, …"""
    out = []
    for k in range(int(np.floor(np.log10(lo))) - 1, int(np.floor(np.log10(hi)))):
        out += [m * 10 ** k for m in range(10, 100) if lo <= m * 10 ** k <= hi]
    return out


def candidates(company: dict, offer: dict) -> list:
    """Предложения того же продукта: сумма ≤ исходной, любой допустимый срок, залог ≤ исходного
    (того же вида; без залога — вид null), ставка та же."""
    p, a0, c0 = offer["product_type"], offer["amount"], offer["collateral_value"]
    cat = CATALOG[p]
    terms = [t for t in cat["terms"]
             if not (p == "GOV_1764" and company["msp_category"] == "micro" and t > GOV_MICRO_MAX_TERM)]
    amounts = sorted(set(round2_grid(cat["amount"][0], a0)) | {a0})
    colls = sorted({int(round(c0 * s)) for s in COLL_STEPS}) if c0 > 0 else [0]
    if cat["collateral"] == "secured":
        colls = [c for c in colls if c > 0]
    out = []
    for a in amounts:
        for t in terms:
            for c in colls:
                if cat["collateral"] == "secured" and a > SECURED_MAX_LTV * c:
                    continue
                kind = {"collateral_type": offer["collateral_type"] if c else None,
                        "collateral_subtype": offer["collateral_subtype"] if c else None}
                out.append({"product_type": p, "amount": a, "term_months": t, "rate": offer["rate"],
                            "collateral_value": c, **kind})
    return out


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

    cands = candidates(company, offer)
    probs = predict_rows(model, company, cands)
    best = None
    for o, p in zip(cands, probs):
        p = round(float(p), 4)
        if p > gamma:
            key = (likelyhood(o, offer), p)  # самое похожее, при равенстве — с большим шансом
            if best is None or key > best[0]:
                best = (key, o, p)
    if best is None:
        return {"source_approval_probability": p0, "offer": None, "likelyhood": None, "approval_probability": None}
    (lk, _), o, p = best
    return {"source_approval_probability": p0, "offer": o, "likelyhood": round(lk, 4), "approval_probability": p}
