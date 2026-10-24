"""Мок-данные в объектах API.md: строка CSV → Company и Offer; разбиение train/test по ИНН.

Разбиение детерминировано и зависит только от ИНН. При обучении моделей исключайте тестовую часть
(`~test_mask(df)`), тогда метрики мок-бэкенда считаются на компаниях, которых модель не видела.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pandas as pd

from contract import BOOL_FIELDS, COMPANY_FIELDS, FLOAT_FIELDS, INT_FIELDS

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "applications.csv"
TEST_SHARE = 0.05


def load_applications(path=DATA_PATH):
    return pd.read_csv(path, dtype={"inn": str})


def is_test(inn: str) -> bool:
    h = int.from_bytes(hashlib.sha256(inn.encode()).digest()[:8], "big")
    return h % 1000 < TEST_SHARE * 1000


def test_mask(df):
    return df["inn"].map(is_test).to_numpy(dtype=bool)


def _is_null(v):
    return v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v))


def company_from_row(row) -> dict:
    """row — словарь колонок CSV. Флаги 0/1 → true/false, пусто → null."""
    out = {}
    for f in COMPANY_FIELDS:
        v = row[f]
        if _is_null(v):
            out[f] = None
        elif f in INT_FIELDS:
            out[f] = int(v)
        elif f in FLOAT_FIELDS:
            out[f] = float(v)
        elif f in BOOL_FIELDS:
            out[f] = bool(int(v))
        else:
            out[f] = str(v)
    return out


def offer_from_row(row) -> dict:
    return {
        "product_type": str(row["product_type"]),
        "amount": int(row["amount"]),
        "term_months": int(row["term_months"]),
        "rate": float(row["rate"]),
        "collateral_value": int(row["collateral_value"]),
        "collateral_type": None if _is_null(row["collateral_type"]) else str(row["collateral_type"]),
        "collateral_subtype": None if _is_null(row["collateral_subtype"]) else str(row["collateral_subtype"]),
    }
