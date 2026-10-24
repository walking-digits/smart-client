"""Модель 1 для /offers: признаки компании, загрузка обученных моделей, прогноз.

Используется и сервисом (app.py), и обучением (train.py) — признаки считаются в одном месте.
"""
from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from contract import CATALOG, GOV_MICRO_MAX_AMOUNT, GOV_MICRO_MAX_TERM, GOV_RATE, PRODUCT_TYPES, SECURED_MAX_LTV

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
OFFER_MODELS = ["amount", "rate", "collateral"]
COLL_MIN_RATIO = 0.25          # прогноз «залог / сумма» ниже — залога нет (реальные отношения от ≈ 0.5)
GOV_MICRO = "GOV_1764_micro"   # ключ срока GOV_1764 для micro (у них не больше 36 мес.)

CATEGORIES = {
    "legal_form": ["LLC", "IE"],
    "okved_section": list("ABCDEFGHIJKLMNPQRS"),
    "msp_category": ["micro", "small", "medium"],
}
# Укрупнённые группы отраслей: похожие по структуре отрасли делят данные (особенно редкие разделы ОКВЭД)
OKVED_GROUP = {
    "B": "industry", "C": "industry", "D": "industry", "E": "industry",   # производство, добыча, энергетика
    "F": "construction",
    "G": "trade",
    "H": "transport",
    "A": "agriculture",
    "I": "services", "S": "services",                                    # общепит и бытовые услуги
    "J": "knowledge", "M": "knowledge", "K": "knowledge",                 # ИТ, профессиональные услуги, финансы
    "L": "property", "N": "property",                                    # недвижимость и аренда
    "P": "social", "Q": "social", "R": "social",                         # образование, медицина, культура
}
NUMERIC = [
    "company_age_months", "revenue_last_year", "revenue_growth_yoy", "net_margin",
    "equity_ratio", "current_ratio", "debt_to_revenue", "taxes_paid_last_year", "tax_arrears_amount",
    "accounts_blocked_flag", "registry_risk_flag", "bankruptcy_flag",
    "fssp_open_amount", "arbitr_defendant_amount_12m", "bki_total_debt", "bki_max_dpd_12m",
]


def make_X(rows: pd.DataFrame) -> pd.DataFrame:
    """rows — поля Company (из CSV или JSON) + product_type. Пропуски остаются NaN."""
    X = rows[NUMERIC].astype(float)  # null → NaN, true/false → 1/0
    for col, cats in CATEGORIES.items():
        X[col] = pd.Categorical(rows[col], categories=cats)  # одинаковые коды категорий в обучении и в сервисе
    X["okved_group"] = pd.Categorical(rows["okved_section"].map(OKVED_GROUP),
                                      categories=sorted(set(OKVED_GROUP.values())))
    rev = X["revenue_last_year"]
    X["log_revenue"] = np.log(rev)
    X["tax_burden"] = X["taxes_paid_last_year"] / rev
    X["bki_debt_to_revenue"] = X["bki_total_debt"] / rev
    X["has_bki"] = X["bki_total_debt"].notna().astype(float)
    X["has_fin"] = X["net_margin"].notna().astype(float)
    X["product_type"] = pd.Categorical(rows["product_type"], categories=PRODUCT_TYPES)
    return X


def round2(x):
    """До 2 значащих цифр: 16 437 000 → 16 000 000."""
    unit = 10 ** (np.floor(np.log10(x)) - 1)
    return np.round(x / unit) * unit


def ceil2(x):
    """Вверх до 2 значащих цифр (для залога: LTV не превышает лимит)."""
    unit = 10 ** (np.floor(np.log10(x)) - 1)
    return np.ceil(x / unit) * unit


def load() -> dict:
    models = {name: lgb.Booster(model_file=str(ARTIFACTS / f"offer_{name}.txt")) for name in OFFER_MODELS}
    models["oftenhood"] = lgb.Booster(model_file=str(ARTIFACTS / "oftenhood.txt"))
    models["terms"] = json.loads((ARTIFACTS / "offer_terms.json").read_text(encoding="utf-8"))
    return models


def predict(models: dict, company: dict) -> list:
    """company — объект Company. Возвращает 10 элементов {"offer", "oftenhood"} по убыванию oftenhood."""
    rows = pd.DataFrame([company] * len(PRODUCT_TYPES))
    rows["product_type"] = PRODUCT_TYPES
    X = make_X(rows)
    msp = company["msp_category"]

    # 10 строк: одного потока хватает, лишние только мешают параллельным запросам
    oftenhood = models["oftenhood"].predict(X, num_threads=1)
    amount = company["revenue_last_year"] * np.exp(models["amount"].predict(X, num_threads=1))
    rate = models["rate"].predict(X, num_threads=1)
    coll_ratio = models["collateral"].predict(X, num_threads=1)

    items = []
    for i, p in enumerate(PRODUCT_TYPES):
        c = CATALOG[p]
        gov_micro = p == "GOV_1764" and msp == "micro"
        lo, hi = c["amount"]
        if gov_micro:
            hi = GOV_MICRO_MAX_AMOUNT
        a = int(np.clip(round2(np.clip(amount[i], lo, hi)), lo, hi))
        term = models["terms"][GOV_MICRO if gov_micro else p]
        if gov_micro:
            term = min(term, GOV_MICRO_MAX_TERM)
        r = GOV_RATE[msp] if c["rate"] is None else round(float(np.clip(rate[i], *c["rate"])), 1)
        if c["collateral"] == "zero" or (c["collateral"] == "any" and coll_ratio[i] < COLL_MIN_RATIO):
            coll = 0
        elif c["collateral"] == "secured":
            coll = int(ceil2(max(a * coll_ratio[i], a / SECURED_MAX_LTV)))
        else:
            coll = int(ceil2(a * coll_ratio[i]))
        offer = {"product_type": p, "amount": a, "term_months": int(term), "rate": r, "collateral_value": coll}
        items.append({"offer": offer, "oftenhood": round(float(oftenhood[i]), 4)})
    return sorted(items, key=lambda it: -it["oftenhood"])
