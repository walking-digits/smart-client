"""Контракт ML-сервиса из API.md: поля Company, каталог продуктов (раздел 5) и проверки.

Нужен мок-бэкенду (проверка ответов) и заглушке ML-сервиса (ответ 422). Можно импортировать
и в настоящий сервис, чтобы правила валидации были одни и те же.
"""
from __future__ import annotations

import math

PRODUCT_TYPES = [
    "OVERDRAFT", "BUSINESS_CARD", "EXPRESS_UNSECURED", "WORKING_CAPITAL",
    "CREDIT_LINE_REV", "LEASING", "INVESTMENT", "SECURED_RE", "GOV_1764", "FACTORING",
]
LEGAL_FORMS = ("LLC", "IE")
MSP_CATEGORIES = ("micro", "small", "medium")
OKVED_SECTIONS = tuple("ABCDEFGHIJKLMNPQRS")

# Поля Company в порядке API.md, раздел 1
COMPANY_FIELDS = [
    "inn", "legal_form", "company_age_months", "okved_section", "msp_category",
    "revenue_last_year", "revenue_growth_yoy", "net_margin", "equity_ratio", "current_ratio",
    "debt_to_revenue", "taxes_paid_last_year", "tax_arrears_amount",
    "accounts_blocked_flag", "registry_risk_flag", "bankruptcy_flag",
    "fssp_open_amount", "arbitr_defendant_amount_12m", "bki_total_debt", "bki_max_dpd_12m",
]
ENUM_FIELDS = {"legal_form": LEGAL_FORMS, "okved_section": OKVED_SECTIONS, "msp_category": MSP_CATEGORIES}
INT_FIELDS = ["company_age_months", "revenue_last_year", "taxes_paid_last_year", "tax_arrears_amount",
              "fssp_open_amount", "arbitr_defendant_amount_12m", "bki_total_debt", "bki_max_dpd_12m"]
FLOAT_FIELDS = ["revenue_growth_yoy", "net_margin", "equity_ratio", "current_ratio", "debt_to_revenue"]
BOOL_FIELDS = ["accounts_blocked_flag", "registry_risk_flag", "bankruptcy_flag"]
NULLABLE_FIELDS = set(FLOAT_FIELDS) | {"bki_total_debt", "bki_max_dpd_12m"}
OFFER_FIELDS = ["product_type", "amount", "term_months", "rate", "collateral_value"]
# Вид залога: в /approval и /alternative обязательны (null без залога); /offers их не возвращает
COLLATERAL_FIELDS = ["collateral_type", "collateral_subtype"]
COLLATERAL_TYPES = {
    "REAL_ESTATE": ["APARTMENT", "HOUSE", "OFFICE", "RETAIL_SPACE", "WAREHOUSE", "INDUSTRIAL_BUILDING", "LAND"],
    "VEHICLES": ["CAR", "TRUCK", "SPECIAL_MACHINERY"],
    "EQUIPMENT": ["PRODUCTION_EQUIPMENT", "TRADE_EQUIPMENT"],
    "INVENTORY": ["GOODS", "RAW_MATERIALS"],
    "FINANCIAL": ["DEPOSIT", "BONDS", "SHARES", "RECEIVABLES"],
}

# Раздел 5. collateral: "zero" — всегда 0, "any" — ≥ 0, "secured" — > 0 и amount ≤ 0.7 × collateral_value.
# rate None — ставка фиксирована программой (GOV_RATE).
CATALOG = {
    "OVERDRAFT":         {"amount": (100_000, 50_000_000),  "terms": (3, 6, 12),            "rate": (12.9, 34.4), "collateral": "zero"},
    "BUSINESS_CARD":     {"amount": (50_000, 5_000_000),    "terms": (12, 24, 36),          "rate": (15.0, 40.0), "collateral": "zero"},
    "EXPRESS_UNSECURED": {"amount": (300_000, 15_000_000),  "terms": (6, 12, 24, 36),       "rate": (14.4, 38.4), "collateral": "zero"},
    "WORKING_CAPITAL":   {"amount": (500_000, 100_000_000), "terms": (6, 12, 18, 24, 36),   "rate": (12.0, 32.0), "collateral": "any"},
    "CREDIT_LINE_REV":   {"amount": (500_000, 60_000_000),  "terms": (12, 18, 24, 36),      "rate": (12.0, 32.0), "collateral": "any"},
    "LEASING":           {"amount": (500_000, 100_000_000), "terms": (12, 24, 36, 48, 60),  "rate": (7.2, 19.2),  "collateral": "zero"},
    "INVESTMENT":        {"amount": (1_000_000, 500_000_000), "terms": (24, 36, 60, 84, 120), "rate": (10.8, 28.8), "collateral": "any"},
    "SECURED_RE":        {"amount": (1_000_000, 150_000_000), "terms": (36, 60, 84, 120),   "rate": (10.2, 27.2), "collateral": "secured"},
    "GOV_1764":          {"amount": (500_000, 500_000_000), "terms": (12, 24, 36, 60),      "rate": None,         "collateral": "any"},
    "FACTORING":         {"amount": (1_000_000, 500_000_000), "terms": (1, 2, 3, 4, 6),     "rate": (14.4, 38.4), "collateral": "zero"},
}
GOV_MICRO_MAX_AMOUNT = 10_000_000
GOV_MICRO_MAX_TERM = 36
GOV_RATE = {"micro": 17.5, "small": 16.75, "medium": 16.75}
SECURED_MAX_LTV = 0.7


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_number(v):
    return (is_int(v) or isinstance(v, float)) and math.isfinite(v)


def is_prob(v):
    return is_number(v) and 0 <= v <= 1


def validate_company(company) -> list[str]:
    """Пустой список — Company соответствует контракту; иначе — тексты ошибок."""
    if not isinstance(company, dict):
        return ["company должен быть объектом"]
    errors = [f"company.{f}: нет поля" for f in COMPANY_FIELDS if f not in company]
    for f in COMPANY_FIELDS:
        if f not in company:
            continue
        v = company[f]
        if v is None:
            if f not in NULLABLE_FIELDS:
                errors.append(f"company.{f}: не может быть null")
            continue
        if f == "inn":
            ok = isinstance(v, str) and v.isascii() and v.isdigit() and len(v) in (10, 12)
        elif f in ENUM_FIELDS:
            ok = isinstance(v, str) and v in ENUM_FIELDS[f]
        elif f in INT_FIELDS:
            ok = is_int(v)
        elif f in FLOAT_FIELDS:
            ok = is_number(v)
        else:
            ok = isinstance(v, bool)
        if not ok:
            errors.append(f"company.{f}={v!r}: неверный тип или значение")
    if not errors:
        want = 10 if company["legal_form"] == "LLC" else 12
        if len(company["inn"]) != want:
            errors.append(f"company.inn: у {company['legal_form']} должно быть {want} цифр")
    return errors


def validate_offer(offer, msp_category, with_collateral_type=True) -> list[str]:
    """Проверка Offer по разделу 5. msp_category — из Company (лимиты GOV_1764 для micro).
    with_collateral_type=False — для предложений из /offers (там вида залога нет)."""
    if not isinstance(offer, dict):
        return ["offer должен быть объектом"]
    fields = OFFER_FIELDS + COLLATERAL_FIELDS if with_collateral_type else OFFER_FIELDS
    missing = [f"offer.{f}: нет поля" for f in fields if f not in offer]
    if missing:
        return missing
    p = offer["product_type"]
    if not isinstance(p, str) or p not in CATALOG:
        return [f"product_type={p!r} неизвестен"]
    amount, term, rate, coll = (offer[f] for f in OFFER_FIELDS[1:])
    errors = [f"offer.{name}={v!r}: неверный тип"
              for name, v, ok in (("amount", amount, is_int(amount)), ("term_months", term, is_int(term)),
                                  ("rate", rate, is_number(rate)), ("collateral_value", coll, is_int(coll)))
              if not ok]
    if errors:
        return errors

    c = CATALOG[p]
    gov_micro = p == "GOV_1764" and msp_category == "micro"
    lo, hi = c["amount"]
    if gov_micro:
        hi = GOV_MICRO_MAX_AMOUNT
    if not lo <= amount <= hi:
        errors.append(f"amount={amount} вне {lo}…{hi} для {p}")
    terms = tuple(t for t in c["terms"] if t <= GOV_MICRO_MAX_TERM) if gov_micro else c["terms"]
    if term not in terms:
        errors.append(f"term_months={term} недопустим для {p}")
    if c["rate"] is None:
        if rate != GOV_RATE.get(msp_category):
            errors.append(f"rate={rate} для {p} у {msp_category} должна быть {GOV_RATE.get(msp_category)}")
    else:
        lo_r, hi_r = c["rate"]
        if not lo_r <= rate <= hi_r:
            errors.append(f"rate={rate} вне {lo_r}…{hi_r} для {p}")
        if abs(rate * 10 - round(rate * 10)) > 1e-6:
            errors.append(f"rate={rate}: больше 1 знака после запятой")
    if coll < 0:
        errors.append(f"collateral_value={coll} < 0")
    elif c["collateral"] == "zero" and coll != 0:
        errors.append(f"collateral_value={coll}: у {p} залога нет, должно быть 0")
    elif c["collateral"] == "secured" and (coll == 0 or amount > SECURED_MAX_LTV * coll):
        errors.append(f"{p}: нужен залог и amount ≤ {SECURED_MAX_LTV} × collateral_value")
    if with_collateral_type:
        errors += validate_collateral_type(p, coll, offer["collateral_type"], offer["collateral_subtype"])
    return errors


def validate_collateral_type(product, coll, ctype, csub) -> list[str]:
    if coll == 0:
        return [] if ctype is None and csub is None else ["collateral_type и collateral_subtype: без залога — null"]
    if not isinstance(ctype, str) or ctype not in COLLATERAL_TYPES:
        return [f"collateral_type={ctype!r} неизвестен"]
    if csub not in COLLATERAL_TYPES[ctype]:
        return [f"collateral_subtype={csub!r} не относится к {ctype}"]
    if product == "SECURED_RE" and ctype != "REAL_ESTATE":
        return ["SECURED_RE: залог — только REAL_ESTATE"]
    return []
