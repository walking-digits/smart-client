#!/usr/bin/env python3
"""Генератор синтетического датасета заявок МСБ на кредитные продукты.

Основан на спецификации «Генератор мок-данных: датасет заявок» v1.1; отличия v1.2–v1.4 — в README:
    * ключ компании — inn (с контрольными цифрами ФНС); 10 продуктов вместо 12;
    * в CSV 19 признаков компании из 30: только доступные по ИНН и влияющие на решение
      (остальные генерируются внутри для согласованности, но не пишутся);
    * заявка: product_type, amount, term_months, rate, collateral_value; одобрение зависит от всех них;
    * история (v1.4): компания приходит за продуктами несколько раз, продукт может повторяться;
      после отказа часто подаёт повторно на тот же продукт с меньшей суммой, залогом или длинным сроком.
Зависимости: только numpy и pandas. Детерминирован по --seed.

Запуск (≈ 500 000 строк):
    python generate_data.py --n-companies 130000 --seed 42 --out data/applications.csv

Параметры, не заданные спецификацией явно (выбраны разумные значения, см. README):
    * employees_count у IE ограничен сверху 15 (иначе micro может нарушить лимит 15 чел.);
    * «Geometric(p)» в owner_other_companies_count — число неудач до успеха (>= 0),
      т.е. 1 + Geometric даёт значения >= 1;
    * у IE с ненулевым owner_other_companies_count используется 1 + Geometric(0.5);
    * authorized_capital ограничен снизу 10 000 ₽ (законный минимум для ООО);
    * для LLC без отчётности в формуле налогов m = mean_okved (как у IE);
    * пропуски employees_count у IE (20%) ставятся сразу после расчёта выручки,
      все последующие шаги считают пустое значение как 0;
    * typical_amount — clip без шума и без round2;
    * если цель по одобрению недостижима (доля строк без жёсткого отказа мала),
      цель снижается до floor(0.9 * доля_допустимых, 2 знака).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

GENERATOR_VERSION = "1.4"

# --------------------------------------------------------------------------- #
# Справочники
# --------------------------------------------------------------------------- #
REGION_MAIN = {
    "77": 0.14, "50": 0.08, "78": 0.07, "23": 0.05, "66": 0.035, "16": 0.03,
    "52": 0.025, "54": 0.025, "63": 0.023, "61": 0.023, "02": 0.022, "74": 0.02,
    "24": 0.018, "59": 0.018,
}
REGION_REST = (
    "01 03 04 05 06 07 08 09 10 11 12 13 14 15 17 18 19 21 22 25 26 27 28 29 30 31 "
    "32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 51 53 55 56 57 58 60 62 "
    "64 65 67 68 69 70 71 72 73 75 76 79 82 86 87 89 92"
).split()

OKVED_P = {
    "G": 0.30, "F": 0.12, "H": 0.10, "M": 0.09, "C": 0.07, "L": 0.07, "S": 0.06,
    "I": 0.05, "J": 0.04, "A": 0.03,
    **{s: 0.07 / 8 for s in "BDEKNPQR"},
}
EPS_OKVED = {"G": 0.3, "C": 0.2, "F": 0.1, "J": -0.1, "M": -0.1, "S": -0.2}
EPS_REGION = {"77": 0.25, "78": 0.15, "50": 0.10}
MEAN_MARGIN = {"G": 0.03, "F": 0.05, "H": 0.05, "C": 0.06, "A": 0.06, "L": 0.08,
               "M": 0.10, "J": 0.12, "S": 0.10, "I": 0.05}
MEAN_MARGIN_DEFAULT = 0.05
TURNOVER_M = {"G": 4.0, "I": 3.5, "H": 3.0, "M": 3.0, "J": 3.0, "S": 3.0, "F": 2.5,
              "C": 1.8, "A": 1.2, "L": 0.4}
TURNOVER_DEFAULT = 2.5
MEAN_Q = {"G": 0.90, "F": 0.80, "M": 0.80, "J": 0.80, "S": 0.75, "I": 0.65,
          "C": 0.55, "H": 0.45, "A": 0.45, "L": 0.30}
MEAN_Q_DEFAULT = 0.65

# Сегменты: 0 = IE micro, 1 = LLC micro, 2 = LLC small, 3 = LLC medium
SEG_MEDIAN = np.array([3e6, 9e6, 250e6, 1.1e9])
SEG_SIGMA = np.array([1.2, 1.3, 0.6, 0.35])
SEG_LO = np.array([1e5, 3e5, 1.2e8, 8e8])
SEG_HI = np.array([1.2e8, 1.2e8, 8e8, 2e9])

REGIMES = ["USN_INCOME", "USN_INCOME_EXPENSE", "OSN", "AUSN", "PSN", "NPD", "ESHN"]
R = {r: i for i, r in enumerate(REGIMES)}
REGIME_W_IE = np.array([0.48, 0.12, 0.04, 0.08, 0.18, 0.07, 0.03])
REGIME_W_LLC = np.array([0.35, 0.30, 0.22, 0.08, 0.0, 0.0, 0.05])
TAX_RATE_FIXED = {"USN_INCOME": 0.04, "AUSN": 0.03, "PSN": 0.01, "NPD": 0.04, "ESHN": 0.01}

# 10 продуктов. BANK_GUARANTEE и TENDER_LOAN из спецификации v1.1 убраны (v1.2): они доступны
# только компаниям с госконтрактами (~7%), предлагать их остальным бесполезно.
PRODUCTS = [
    "OVERDRAFT", "BUSINESS_CARD", "EXPRESS_UNSECURED", "WORKING_CAPITAL",
    "CREDIT_LINE_REV", "LEASING", "INVESTMENT", "SECURED_RE", "GOV_1764", "FACTORING",
]
P = {p: i for i, p in enumerate(PRODUCTS)}
# Базовые веса спроса из спецификации без двух убранных продуктов, нормированные на сумму 1.
PRODUCT_W = np.array([0.17, 0.12, 0.14, 0.15, 0.06, 0.07, 0.05, 0.04, 0.06, 0.04])
PRODUCT_W = PRODUCT_W / PRODUCT_W.sum()
APPROVAL_TARGET = {
    "OVERDRAFT": 0.62, "BUSINESS_CARD": 0.70, "EXPRESS_UNSECURED": 0.55,
    "WORKING_CAPITAL": 0.58, "CREDIT_LINE_REV": 0.55, "LEASING": 0.68,
    "INVESTMENT": 0.45, "SECURED_RE": 0.50, "GOV_1764": 0.42, "FACTORING": 0.70,
}
# ratio к revenue (для BUSINESS_CARD — фикс. медиана 300 000)
AMT_RATIO = np.array([0.05, 0.0, 0.08, 0.20, 0.15, 0.20, 0.50, 0.40, 0.20, 0.15])
AMT_MIN = np.array([1e5, 5e4, 3e5, 5e5, 5e5, 5e5, 1e6, 1e6, 5e5, 1e6])
AMT_MAX = np.array([5e7, 5e6, 1.5e7, 1e8, 6e7, 1e8, 5e8, 1.5e8, 5e8, 5e8])

# Срок и ставка: каталог base pipeline (типичные значения) и допустимые сроки по продуктам.
BASE_TERM = np.array([12, 36, 24, 24, 18, 36, 60, 60, 36, 6])
BASE_RATE = np.array([21.5, 25.0, 24.0, 20.0, 20.0, 12.0, 18.0, 17.0, 16.75, 24.0])
TERM_GRID = [
    [3, 6, 12],                  # OVERDRAFT
    [12, 24, 36],                # BUSINESS_CARD
    [6, 12, 24, 36],             # EXPRESS_UNSECURED
    [6, 12, 18, 24, 36],         # WORKING_CAPITAL
    [12, 18, 24, 36],            # CREDIT_LINE_REV
    [12, 24, 36, 48, 60],        # LEASING
    [24, 36, 60, 84, 120],       # INVESTMENT
    [36, 60, 84, 120],           # SECURED_RE
    [12, 24, 36, 60],            # GOV_1764
    [1, 2, 3, 4, 6],             # FACTORING
]
# Программа 1764 (ПП РФ от 30.12.2018 № 1764): ставка фиксирована — ключевая (14%) + 2.75 для малых и
# средних, ключевая + 3.5 для микро (сумма до 10 млн, срок до 3 лет); только приоритетные отрасли.
FIXED_RATE_PRODUCTS = ["GOV_1764"]
GOV_RATE_SMALL_MEDIUM = 16.75
GOV_RATE_MICRO = 17.5
GOV_MICRO_MAX_TERM = 36
# Приоритетные отрасли: сельское хозяйство, обработка, энергетика, водоснабжение и отходы, строительство,
# транспорт, общепит, связь, здравоохранение, бытовые услуги (торговля — только ДФО/моногорода, не моделируем).
GOV_OKVED = list("ACDEFHIJQS")

# Залог: collateral_value — стоимость обеспечения, ₽ (0 — без залога).
# Доля заявок с залогом по продуктам (у ИП ×0.6, у ООО ×1.2, максимум 1); у SECURED_RE залог всегда.
COLLATERAL_P = {"WORKING_CAPITAL": 0.40, "CREDIT_LINE_REV": 0.35, "INVESTMENT": 0.60,
                "SECURED_RE": 1.0, "GOV_1764": 0.50}
NO_COLLATERAL_PRODUCTS = [p for p in ["OVERDRAFT", "BUSINESS_CARD", "EXPRESS_UNSECURED", "LEASING", "FACTORING"]]
SECURED_RE_MAX_LTV = 0.70          # amount ≤ 70% стоимости залога
COLLATERAL_COEF = 0.6              # T19: COLLATERAL_COEF × min(collateral_value / amount, 2)
# Ставка: rate = BASE_RATE × exp(RATE_SIGMA·N(0,1) − RATE_RISK_COEF·z_quality), clip 0.6…1.6 × BASE_RATE.
# z_quality — стандартизованная «надёжность» компании (сумма вкладов T1–T13): надёжным ставка ниже.
RATE_SIGMA = 0.12
RATE_RISK_COEF = 0.10
# Срок: крупнее сумма относительно типичной → чаще берут длинный срок.
TERM_AMOUNT_COEF = 0.8
# Вклады в logit одобрения:
TERM_COEF = -0.4                 # T16: TERM_COEF × clip(ln(term / BASE_TERM), −1.5, 1.5) — длинный горизонт риска
RATE_COEF = 1.5                  # T17: RATE_COEF × clip(ln(rate / BASE_RATE), −0.5, 0.5) — риск заложен в цену
# T18: долговая нагрузка нового кредита (только кредиты с графиком погашения):
#   DSR = годовой аннуитетный платёж / выручка; вклад DSR_COEF × clip(DSR − DSR_FREE, 0, 0.6)
DSR_PRODUCTS = ["EXPRESS_UNSECURED", "WORKING_CAPITAL", "LEASING", "INVESTMENT", "SECURED_RE", "GOV_1764"]
DSR_FREE = 0.25
DSR_COEF = -3.0
# T14: AMOUNT_COEF × clip(ln(amount / typical), AMOUNT_CLIP_LO, 2). v1.4: сумма ниже типичной даёт
# небольшой плюс (в v1.1 нижний клип 0) — иначе снижение суммы при повторной заявке не помогало бы.
AMOUNT_COEF = -1.0
AMOUNT_CLIP_LO = -0.5

# История заявок (v1.4). Обращение — компания пришла за продуктом; в обращении 1–3 попытки (заявки).
NEEDS_LAMBDA = np.array([1.8, 2.4, 3.5, 4.5])  # обращений = 1 + Poisson(λ): IE, LLC micro, small, medium
MAX_NEEDS = 12
RETRY_P = [0.55, 0.35]             # вероятность повторной заявки после 1-го и 2-го отказа
RETRY_CUT_P = 0.8                  # при повторе снижают сумму…
RETRY_CUT = (0.45, 0.85)           # …в столько раз
RETRY_COLLATERAL_P = 0.35          # добавляют залог (если продукт допускает и залога не было)
RETRY_TERM_P = 0.3                 # берут следующий, более длинный срок из сетки
RETRY_DAYS = (7, 45)               # через сколько дней после отказа
COLLATERAL_ADD_PRODUCTS = ["WORKING_CAPITAL", "CREDIT_LINE_REV", "INVESTMENT", "GOV_1764"]
# T15: шум логита делится на общий для всех попыток обращения и свой у каждой попытки
# (в сумме σ = 0.5, как в v1.1): повтор с теми же условиями почти так же вероятно получит отказ.
NOISE_NEED_SIGMA = 0.4
NOISE_ATTEMPT_SIGMA = 0.3
SNAPSHOT_DATE = np.datetime64("2026-10-01")  # дата выгрузки; признаки компании — на эту дату
HISTORY_DAYS = 365                           # заявки за последний год (не раньше регистрации)
DAYS_PER_MONTH = 30.4

# Признаки компании в выходном CSV (v1.3): только доступные по ИНН и влияющие на спрос/одобрение.
# Остальные колонки спецификации v1.1 генерируются внутри (нужны для согласованности), но не пишутся.
FEATURE_COLUMNS = [
    "legal_form", "company_age_months", "okved_section", "msp_category",
    "revenue_last_year", "revenue_growth_yoy", "net_margin",
    "equity_ratio", "current_ratio", "debt_to_revenue",
    "taxes_paid_last_year", "tax_arrears_amount",
    "accounts_blocked_flag", "registry_risk_flag", "bankruptcy_flag",
    "fssp_open_amount", "arbitr_defendant_amount_12m",
    "bki_total_debt", "bki_max_dpd_12m",
]
OFFER_COLUMNS = ["product_type", "amount", "term_months", "rate", "collateral_value"]
COLUMNS = ["application_id", "application_date", "inn"] + FEATURE_COLUMNS + OFFER_COLUMNS + ["approved"]
FLAG_COLS = ["accounts_blocked_flag", "registry_risk_flag", "bankruptcy_flag", "approved"]
MONEY_COLS = ["revenue_last_year", "taxes_paid_last_year", "tax_arrears_amount",
              "fssp_open_amount", "arbitr_defendant_amount_12m",
              "bki_total_debt", "amount", "collateral_value"]
# Пусты у IE во внутренней таблице компаний (проверка 2.9)
IE_EMPTY_COLS = ["revenue_growth_yoy", "net_margin", "total_assets", "equity_ratio",
                 "current_ratio", "debt_to_revenue", "authorized_capital"]
# У IE в выходном CSV эти колонки всегда пусты или 0 — в файл ИП не пишутся
IE_DROP_COLS = ["revenue_growth_yoy", "net_margin", "equity_ratio", "current_ratio",
                "debt_to_revenue", "registry_risk_flag"]
LOW_TAX_BURDEN = 0.005             # налоги < 0.5% выручки — признак фирмы-однодневки (Банк России)
NOMINAL_TAX_FACTOR = 0.1           # номинальные компании платят налогов в 10 раз меньше
GROWTH_COEF = 1.0                  # T20: GROWTH_COEF × clip(revenue_growth_yoy, −0.5, 0.5)
LOW_TAX_COEF = -0.8                # T21: если taxes / revenue < LOW_TAX_BURDEN


# --------------------------------------------------------------------------- #
# Вспомогательные функции
# --------------------------------------------------------------------------- #
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def logit(p):
    p = np.asarray(p, dtype=float)
    return np.log(p / (1.0 - p))


def lognorm(rng, median, sigma, size):
    """LogN(m, σ) = m · exp(σ · N(0,1))."""
    return median * np.exp(sigma * rng.standard_normal(size))


def negbin(rng, mu, size, r=2):
    return rng.negative_binomial(r, r / (r + mu), size)


def ceil2(x):
    """Округление вверх до 2 значащих цифр (для стоимости залога: LTV не превышает лимит)."""
    x = np.asarray(x, dtype=float)
    unit = 10.0 ** (np.floor(np.log10(x)) - 1)
    return np.rint(np.ceil(x / unit) * unit)


def round2(x):
    """Округление до 2 значащих цифр."""
    x = np.asarray(x, dtype=float)
    unit = 10.0 ** (np.floor(np.log10(x)) - 1)
    return np.rint(np.round(x / unit) * unit)


def zscore(x):
    sd = x.std()
    return (x - x.mean()) / (sd if sd > 0 else 1.0)


def zscore_by_group(x, groups):
    out = np.empty_like(x, dtype=float)
    for g in np.unique(groups):  # цикл по сегментам (4 шт.), не по строкам
        m = groups == g
        out[m] = zscore(x[m])
    return out


def lookup(keys, mapping, default=0.0):
    return np.array([mapping.get(k, default) for k in np.unique(keys)])[
        np.unique(keys, return_inverse=True)[1]
    ]


def to_int(x):
    return np.rint(x).astype(np.int64)


def nullable_int(x, mask_null):
    arr = pd.array(np.where(mask_null, 0, np.rint(np.nan_to_num(x))).astype(np.int64), dtype="Int64")
    arr[mask_null] = pd.NA
    return arr


INN_W10 = np.array([2, 4, 10, 3, 5, 9, 4, 6, 8])          # контрольная цифра ИНН юрлица
INN_W11 = np.array([7, 2, 4, 10, 3, 5, 9, 4, 6, 8])       # 11-я цифра ИНН физлица/ИП
INN_W12 = np.array([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])    # 12-я цифра ИНН физлица/ИП


def inn_check_digit(digits, weights):
    return (digits[:, :len(weights)] * weights).sum(axis=1) % 11 % 10


def inn_digits(inn):
    """Массив строк ИНН одной длины → матрица цифр (n, L)."""
    inn = np.asarray(inn, dtype=str)
    return np.frombuffer("".join(inn).encode(), dtype=np.uint8).reshape(len(inn), -1).astype(np.int64) - 48


def inn_is_valid(inn):
    """Векторная проверка контрольных цифр ИНН (10 или 12 цифр)."""
    inn = pd.Series(inn, dtype=str)
    ok = inn.str.fullmatch(r"\d{10}|\d{12}").to_numpy(dtype=bool, copy=True)
    for L in (10, 12):
        m = ok & (inn.str.len() == L).to_numpy()
        if not m.any():
            continue
        d = inn_digits(inn[m].to_numpy())
        if L == 10:
            good = d[:, 9] == inn_check_digit(d, INN_W10)
        else:
            good = (d[:, 10] == inn_check_digit(d, INN_W11)) & (d[:, 11] == inn_check_digit(d, INN_W12))
        ok[np.flatnonzero(m)] = good
    return ok


def make_inn(rng, is_ie, region):
    """Случайный уникальный ИНН с корректными контрольными цифрами (алгоритм ФНС):
    LLC — region_code + 7 случайных цифр + 1 контрольная (10 цифр),
    IE  — region_code + 8 случайных цифр + 2 контрольные (12 цифр)."""
    def draw(idx):
        out = np.empty(len(idx), dtype=object)
        reg = region[idx].astype(np.int64)
        for ie_val, n_rand in ((True, 8), (False, 7)):  # цикл по двум формам, не по строкам
            m = is_ie[idx] == ie_val
            k = int(m.sum())
            d = np.column_stack([reg[m] // 10, reg[m] % 10, rng.integers(0, 10, (k, n_rand))])
            if ie_val:
                d = np.column_stack([d, inn_check_digit(d, INN_W11)])
                d = np.column_stack([d, inn_check_digit(d, INN_W12)])
            else:
                d = np.column_stack([d, inn_check_digit(d, INN_W10)])
            L = d.shape[1]
            num = (d * 10 ** np.arange(L - 1, -1, -1, dtype=np.int64)).sum(axis=1)
            out[m] = np.char.zfill(num.astype(str), L)
        return out

    inn = draw(np.arange(len(is_ie)))
    while True:  # перегенерация редких совпадений (обычно 0–2 итерации)
        dup = pd.Series(inn).duplicated().to_numpy()
        if not dup.any():
            return inn
        idx = np.flatnonzero(dup)
        inn[idx] = draw(idx)


def round3(x):
    return np.round(x, 3) + 0.0  # + 0.0 убирает «-0.0»


def spearman(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = ~(np.isnan(a) | np.isnan(b))
    ra = pd.Series(a[ok]).rank().to_numpy()
    rb = pd.Series(b[ok]).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


# --------------------------------------------------------------------------- #
# Генерация компаний (раздел 2.3)
# --------------------------------------------------------------------------- #
def generate_companies(rng, n):
    # ---- Шаг 1. Базовые атрибуты ----
    is_ie = rng.random(n) < 0.62
    young = rng.random(n) < 0.25
    age_young = rng.integers(1, 25, n)
    age_old = np.minimum(np.rint(24 + rng.gamma(1.6, 60.0, n)), 360)
    age = np.where(young, age_young, age_old).astype(np.int64)

    main_codes = list(REGION_MAIN)
    main_p = np.array(list(REGION_MAIN.values()))
    rest_share = 1.0 - main_p.sum()  # 0.421 (в спецификации указано 40.3%, см. README)
    reg_codes = main_codes + REGION_REST
    reg_p = np.concatenate([main_p, np.full(len(REGION_REST), rest_share / len(REGION_REST))])
    region = rng.choice(np.array(reg_codes), n, p=reg_p / reg_p.sum())

    ok_letters = np.array(list(OKVED_P))
    ok_p = np.array(list(OKVED_P.values()))
    okved = rng.choice(ok_letters, n, p=ok_p / ok_p.sum())

    okved_extra = np.clip(rng.poisson(2.0, n), 0, 15)

    msp_llc = rng.choice(np.array(["micro", "small", "medium"]), n, p=[0.93, 0.06, 0.01])
    msp = np.where(is_ie, "micro", msp_llc)
    seg = np.select([is_ie, msp == "micro", msp == "small"], [0, 1, 2], 3)

    # ---- Шаг 2. Сотрудники и выручка ----
    ie_has_staff = rng.random(n) >= 0.72
    emp_ie = np.minimum(np.where(ie_has_staff, 1 + negbin(rng, 2, n), 0), 15)
    emp_llc_micro = np.minimum(1 + negbin(rng, 4, n), 15)
    emp_small = np.clip(np.rint(lognorm(rng, 30, 0.5, n)), 16, 100)
    emp_medium = np.clip(np.rint(lognorm(rng, 140, 0.3, n)), 101, 250)
    emp = np.choose(seg, [emp_ie, emp_llc_micro, emp_small, emp_medium]).astype(float)

    z_emp = zscore_by_group(np.log1p(emp), seg)
    z_age_seg = zscore_by_group(np.log1p(age.astype(float)), seg)
    eps_ok = lookup(okved, EPS_OKVED)
    eps_reg = lookup(region, EPS_REGION)
    rev = SEG_MEDIAN[seg] * np.exp(
        0.4 * z_emp + 0.2 * z_age_seg + eps_ok + eps_reg + SEG_SIGMA[seg] * rng.standard_normal(n)
    )
    rev = np.clip(rev, SEG_LO[seg], SEG_HI[seg])
    rev = np.where(age < 12, rev * age / 12.0, rev)
    rev = np.maximum(1, to_int(rev))
    revf = rev.astype(float)

    # 20% IE — employees пусто (после расчёта выручки)
    emp_null = is_ie & (rng.random(n) < 0.20)
    emp0 = np.where(emp_null, 0.0, emp)  # пусто считается 0

    # ---- Система налогообложения ----
    W = np.where(is_ie[:, None], REGIME_W_IE[None, :], REGIME_W_LLC[None, :]).copy()
    is_a = okved == "A"
    W[:, R["ESHN"]] *= np.where(is_a, 8.0, 0.0)
    W[:, R["AUSN"]] *= (rev <= 60e6) & (emp0 <= 5)
    W[:, R["NPD"]] *= is_ie & (rev <= 2.4e6) & (emp0 == 0)
    W[:, R["PSN"]] *= is_ie & (rev <= 60e6) & (emp0 <= 15)
    usn_ok = rev <= 490e6
    W[:, R["USN_INCOME"]] *= usn_ok
    W[:, R["USN_INCOME_EXPENSE"]] *= usn_ok
    none_ok = W.sum(axis=1) == 0
    W[none_ok, R["OSN"]] = 1.0
    cw = np.cumsum(W / W.sum(axis=1, keepdims=True), axis=1)
    reg_idx = np.minimum((cw < rng.random(n)[:, None]).sum(axis=1), len(REGIMES) - 1)
    regime = np.array(REGIMES)[reg_idx]

    # ---- Шаг 3. Баланс (только LLC с отчётностью) ----
    has_fin = ~is_ie & (rng.random(n) >= 0.03)
    agef = age.astype(float)

    growth = np.where(agef < 36, rng.normal(0.25, 0.5, n), rng.normal(0.08, 0.30, n))
    growth = np.clip(growth, -0.7, 3.0)
    growth = np.where(has_fin & (age >= 12), growth, np.nan)

    mean_m = lookup(okved, MEAN_MARGIN, MEAN_MARGIN_DEFAULT)
    m = np.clip(rng.normal(mean_m, 0.08), -0.5, 0.5)

    turnover = np.clip(lognorm(rng, lookup(okved, TURNOVER_M, TURNOVER_DEFAULT), 0.4, n), 0.3, 20)
    A = revf / turnover

    e = np.clip(0.15 + 0.05 * np.log1p(agef / 12) + 1.2 * m + rng.normal(0, 0.25, n), -1.0, 0.95)
    E = e * A
    L = A - E
    s = np.where(rng.random(n) < 0.35, 0.0, rng.beta(1.2, 3.0, n))
    borrowed = L * s
    u = rng.uniform(0, 0.6, n)
    r1400 = borrowed * u
    r1510 = borrowed - r1400
    r1500 = L - r1400

    mq = lookup(okved, MEAN_Q, MEAN_Q_DEFAULT)
    q = rng.beta(8 * mq, 8 * (1 - mq))
    r1200 = q * A
    r1100 = A - r1200

    cr = np.clip(r1200 / r1500, 0.1, 10)
    dtr = np.clip((r1400 + r1510) / revf, 0, 3)

    # Инвариант баланса: 1100 + 1200 = 1600 = 1300 + 1400 + 1500 (±1%)
    A_int = np.maximum(1, to_int(A))
    fa = has_fin
    assert np.all(np.abs(r1100[fa] + r1200[fa] - A_int[fa]) <= 0.01 * A_int[fa]), "баланс: актив"
    assert np.all(np.abs(E[fa] + r1400[fa] + r1500[fa] - A_int[fa]) <= 0.01 * A_int[fa]), "баланс: пассив"

    borrowed = np.where(has_fin, borrowed, 0.0)
    m_out = np.where(has_fin, m, np.nan)
    e_out = np.where(has_fin, e, np.nan)
    cr_out = np.where(has_fin, cr, np.nan)
    dtr_out = np.where(has_fin, dtr, np.nan)

    # ---- Шаг 4. Налоги ----
    m_tax = np.where(has_fin, m, mean_m)
    rate = np.zeros(n)
    for name, r in TAX_RATE_FIXED.items():
        rate[regime == name] = r
    pos_m = np.maximum(m_tax, 0)
    rate = np.where(regime == "USN_INCOME_EXPENSE", np.maximum(0.01, 0.15 * pos_m), rate)
    rate = np.where(regime == "OSN", 0.01 + 0.2 * pos_m, rate)
    taxes = (revf * rate * lognorm(rng, 1.0, 0.3, n)
             + emp0 * 120_000 * lognorm(rng, 1.0, 0.3, n)
             + np.where(is_ie & (regime != "NPD"), 57_000, 0))
    taxes = to_int(taxes)

    # ---- Шаг 5. Дисциплина и риск-флаги ----
    z_age = zscore(np.log(agef))
    Q = 0.25 * z_age + np.sqrt(1 - 0.25 ** 2) * rng.standard_normal(n)
    stress = has_fin & ((m < 0) | (e < 0))
    st = stress.astype(float)

    f_ta = rng.random(n) < sigmoid(logit(0.15) - 0.8 * Q + 0.6 * st)
    ta = np.where(f_ta, to_int(np.clip(lognorm(rng, 40_000, 1.5, n), 1_000, 5_000_000)), 0)

    base_fssp = np.where(is_ie, 0.14, 0.09)
    f_fssp = rng.random(n) < sigmoid(logit(base_fssp) - 0.9 * Q + 0.5 * st + 0.8 * (ta > 0))
    fssp_amt = np.clip(lognorm(rng, 60_000, 1.3, n) * (revf / 1e7) ** 0.3, 5_000, 50_000_000)
    fssp = np.where(f_fssp, to_int(fssp_amt), 0)

    base_arb = np.array([0.03, 0.10, 0.30, 0.55])[seg]
    f_arb = rng.random(n) < sigmoid(logit(base_arb) - 0.5 * Q + 0.5 * st)
    arb_amt = np.minimum(np.maximum(lognorm(rng, 0.02 * revf, 1.0, n), 50_000), 0.5 * revf)
    arb = np.where(f_arb, np.maximum(1, to_int(arb_amt)), 0)

    blocked = rng.random(n) < sigmoid(logit(0.02) - 1.0 * Q + 1.4 * (ta > 0))
    bankrupt = rng.random(n) < sigmoid(logit(0.005) - 1.2 * Q + 1.0 * blocked + 0.5 * st)

    nominal = ~is_ie & (rng.random(n) < 0.05)
    unreliable = ~is_ie & (rng.random(n) < np.where(nominal, 0.5, 0.015))
    mass_addr = ~is_ie & (rng.random(n) < np.where(nominal, 0.6, 0.02))
    director = ~is_ie & (rng.random(n) < np.where(nominal, 0.3, 0.005))

    p_zero = np.where(is_ie, 0.85, np.where(nominal, 0.30, 0.70))
    geo_p = np.where(nominal, 0.3, 0.5)
    owners = np.where(rng.random(n) < p_zero, 0, rng.geometric(geo_p))  # = 1 + (неудачи)
    owners = np.minimum(owners, 20)

    u_cap = rng.random(n)
    cap_choice = rng.choice(np.array([20_000, 50_000, 100_000]), n)
    cap_micro = np.select([u_cap < 0.85, u_cap < 0.95], [10_000, cap_choice],
                          np.maximum(10_000, to_int(lognorm(rng, 500_000, 1.0, n))))
    cap_big = np.maximum(10_000, to_int(lognorm(rng, 1_000_000, 1.0, n)))
    auth_cap = np.where(seg == 1, cap_micro, cap_big).astype(float)
    auth_cap[is_ie] = np.nan

    # ---- Шаг 6. Госконтракты и РНП ----
    p_gov = np.array([0.04, 0.10, 0.30, 0.45])[seg]
    p_gov = np.where(np.isin(okved, list("FCMQ")), np.minimum(p_gov * 1.8, 0.9), p_gov)
    p_gov = np.where(age < 24, p_gov * 0.5, p_gov)
    has_gov = rng.random(n) < p_gov
    gov_amt = np.minimum(np.maximum(lognorm(rng, 0.25 * revf, 1.0, n), 100_000), 3 * revf)
    gov = np.where(has_gov, np.maximum(1, to_int(gov_amt)), 0)
    rnp = has_gov & (rng.random(n) < 0.02)

    # ---- Шаг 7. Кредитная история ----
    p_bki = np.where(is_ie, 0.30, 0.45)
    p_bki = np.where(age < 12, p_bki * 0.3, p_bki)
    p_bki = np.where(has_fin & (dtr > 0.05), p_bki * 1.6, p_bki)
    p_bki = np.where(has_fin & (dtr == 0), p_bki * 0.6, p_bki)
    p_bki = np.minimum(p_bki, 0.9)
    has_bki = rng.random(n) < p_bki

    debt_fin = np.where(
        borrowed > 0,
        borrowed * lognorm(rng, 1.0, 0.4, n),
        np.where(rng.random(n) < 0.5, 0.0, revf * lognorm(rng, 0.02, 1.0, n)),
    )
    debt_other = np.where(rng.random(n) < 0.15, 0.0, revf * lognorm(rng, 0.08, 1.0, n))
    bki_debt = np.minimum(np.where(has_fin, debt_fin, debt_other), 0.8 * revf)

    has_dpd = rng.random(n) < sigmoid(logit(0.17) - 0.8 * Q + 0.4 * st)
    bucket = rng.choice(3, n, p=[0.55, 0.25, 0.20])
    dpd_val = np.choose(bucket, [rng.integers(1, 30, n), rng.integers(30, 90, n),
                                 rng.integers(90, 366, n)])
    dpd = np.where(has_dpd, dpd_val, 0)

    inn = make_inn(rng, is_ie, region)
    # Номинальные («пустые») компании почти не платят налогов: налоговая нагрузка < 0.5% выручки
    taxes = np.where(nominal, to_int(taxes * NOMINAL_TAX_FACTOR), taxes)
    registry_risk = unreliable | mass_addr | director

    df = pd.DataFrame({
        "inn": inn,
        "legal_form": np.where(is_ie, "IE", "LLC"),
        "company_age_months": age,
        "region_code": region,
        "okved_section": okved,
        "okved_extra_count": okved_extra.astype(np.int64),
        "msp_category": msp,
        "employees_count": nullable_int(emp, emp_null),
        "tax_regime": regime,
        "revenue_last_year": rev,
        "revenue_growth_yoy": round3(growth),
        "net_margin": round3(m_out),
        "total_assets": nullable_int(A_int, ~has_fin),
        "equity_ratio": round3(e_out),
        "current_ratio": round3(cr_out),
        "debt_to_revenue": round3(dtr_out),
        "taxes_paid_last_year": taxes,
        "tax_arrears_amount": ta.astype(np.int64),
        "accounts_blocked_flag": blocked.astype(np.int64),
        "unreliable_info_flag": unreliable.astype(np.int64),
        "mass_address_flag": mass_addr.astype(np.int64),
        "director_risk_flag": director.astype(np.int64),
        "registry_risk_flag": registry_risk.astype(np.int64),
        "owner_other_companies_count": owners.astype(np.int64),
        "authorized_capital": nullable_int(auth_cap, is_ie),
        "fssp_open_amount": fssp.astype(np.int64),
        "arbitr_defendant_amount_12m": arb.astype(np.int64),
        "bankruptcy_flag": bankrupt.astype(np.int64),
        "gov_contracts_amount_3y": gov.astype(np.int64),
        "rnp_flag": rnp.astype(np.int64),
        "bki_total_debt": nullable_int(bki_debt, ~has_bki),
        "bki_max_dpd_12m": nullable_int(dpd, ~has_bki),
    })
    internal = {"has_fin": has_fin, "stress": stress, "r1100": r1100, "r1200": r1200,
                "r1300": E, "r1400": r1400, "r1500": r1500, "A": A_int}
    return df, internal


# --------------------------------------------------------------------------- #
# Заявки (2.4) и одобрение (2.5)
# --------------------------------------------------------------------------- #
def col(df, name):
    return df[name].to_numpy(dtype=float, na_value=np.nan)


def generate_applications(rng, comp):
    n = len(comp)
    is_ie = (comp["legal_form"] == "IE").to_numpy()
    age = col(comp, "company_age_months")
    okved = comp["okved_section"].to_numpy(dtype=str)
    rev = col(comp, "revenue_last_year")
    msp = comp["msp_category"].to_numpy(dtype=str)
    micro = msp == "micro"
    ta = col(comp, "tax_arrears_amount")

    # ---- Обращения: сколько раз компания приходила и за каким продуктом ----
    # Продукт обращения — выборка из softmax(ln w + adj) с возвращением: продукт может повторяться.
    seg = np.select([is_ie, micro, msp == "small"], [0, 1, 2], 3)
    k = np.minimum(1 + rng.poisson(NEEDS_LAMBDA[seg]), MAX_NEEDS)

    def isin(letters):
        return np.isin(okved, list(letters))

    adj = np.zeros((n, len(PRODUCTS)))
    adj[:, P["OVERDRAFT"]] = 0.4 * isin("GS") - 0.8 * (age < 6)
    adj[:, P["BUSINESS_CARD"]] = 0.7 * (is_ie | (rev < 10e6)) - 0.8 * (rev > 200e6)
    adj[:, P["EXPRESS_UNSECURED"]] = 0.6 * micro + 0.4 * (age < 24) - 1.0 * (rev > 200e6)
    adj[:, P["WORKING_CAPITAL"]] = 0.5 * isin("GC") + 0.3 * (rev > 30e6)
    adj[:, P["CREDIT_LINE_REV"]] = 0.8 * (~is_ie & (rev > 30e6)) - 0.8 * is_ie
    adj[:, P["LEASING"]] = 0.8 * isin("HFAC")
    adj[:, P["INVESTMENT"]] = 0.8 * ((age >= 36) & isin("CAH")) - 1.0 * (age < 12)
    adj[:, P["SECURED_RE"]] = 0.6 * (age >= 36) - 0.5 * is_ie
    adj[:, P["GOV_1764"]] = np.where(isin(GOV_OKVED), 0.8, -3.0) - 3.0 * (ta > 50_000)
    adj[:, P["FACTORING"]] = 1.0 * (isin("GC") & (rev > 50e6)) - 2.5 * (rev < 20e6)

    logits = np.log(PRODUCT_W)[None, :] + adj
    ci = np.repeat(np.arange(n), k)  # обращение → компания
    g = -np.log(-np.log(rng.random((len(ci), len(PRODUCTS)))))
    prod = np.argmax(logits[ci] + g, axis=1)
    nr = len(ci)

    # ---- Запрашиваемая сумма (первая попытка) ----
    rev_r = rev[ci]
    base = AMT_RATIO[prod] * rev_r
    bc = prod == P["BUSINESS_CARD"]
    base[bc] = 300_000
    lo = AMT_MIN[prod].copy()
    hi = AMT_MAX[prod].copy()
    hi[bc] = np.minimum(5e6, np.maximum(5e4, 0.15 * rev_r[bc]))
    hi[(prod == P["GOV_1764"]) & micro[ci]] = 10e6
    sig = np.where(bc, 0.6, 0.4)
    typical = np.minimum(np.maximum(base, lo), hi)
    raw = base * np.exp(sig * rng.standard_normal(nr))
    amount = round2(np.minimum(np.maximum(raw, lo), hi)).astype(np.int64)

    # ---- Жёсткие отказы: зависят только от компании и продукта, одинаковы для всех попыток ----
    hard = hard_rejects(comp.iloc[ci], prod)

    # ---- Надёжность компании: нужна и для ставки, и для одобрения ----
    # Используются только признаки, которые есть в выходном CSV (T13 по госконтрактам убран,
    # T10 считается по объединённому флагу, добавлены T20 рост выручки и T21 налоговая нагрузка).
    c = comp.iloc[ci]
    age_r = col(c, "company_age_months")
    m = col(c, "net_margin")
    e = col(c, "equity_ratio")
    dtr = col(c, "debt_to_revenue")
    cr = col(c, "current_ratio")
    ta_r = col(c, "tax_arrears_amount")
    fssp = col(c, "fssp_open_amount")
    arb = col(c, "arbitr_defendant_amount_12m")
    dpd = col(c, "bki_max_dpd_12m")
    bki = col(c, "bki_total_debt")
    z = np.nan_to_num
    T_company = [
        0.6 * np.clip(np.log(age_r / 24), -1.5, 1.5),
        0.5 * np.clip(np.log(rev_r / 1e7) / 2, -1.5, 1.5),
        z(0.4 * np.clip(m / 0.1, -2, 3)),
        -1.0 * (e < 0),
        z(-0.6 * np.clip(dtr, 0, 2)),
        z(-0.8 * np.maximum(0, 1 - cr)),
        np.select([ta_r > 50_000, ta_r > 0], [-1.2, -0.4], 0.0),
        -0.6 * (fssp > 0) - 0.4 * (fssp > 0.01 * rev_r),
        -0.5 * (arb > 0) - 0.5 * (arb > 0.05 * rev_r),
        -1.2 * col(c, "registry_risk_flag"),                                     # T10
        np.select([np.isnan(dpd), dpd == 0, dpd < 30, dpd < 90], [-0.2, 0.3, -0.5, -1.5], -3.0),  # T11
        z(-0.8 * np.minimum(bki / rev_r, 1)),                                   # T12
        z(GROWTH_COEF * np.clip(col(c, "revenue_growth_yoy"), -0.5, 0.5)),       # T20
        LOW_TAX_COEF * (col(c, "taxes_paid_last_year") / rev_r < LOW_TAX_BURDEN),  # T21
    ]
    z_quality = zscore(np.sum(T_company, axis=0))

    # ---- Срок: чем крупнее сумма относительно типичной, тем чаще берут длинный срок ----
    grid_len = np.array([len(g) for g in TERM_GRID])
    grid = np.zeros((len(PRODUCTS), grid_len.max()), dtype=np.int64)
    for j, g in enumerate(TERM_GRID):
        grid[j, :len(g)] = g
    L = grid_len[prod][:, None]
    slot = np.arange(grid.shape[1])[None, :]
    pos = (slot - (L - 1) / 2) / ((L - 1) / 2)          # −1 (самый короткий) … +1 (самый длинный)
    amt_z = np.clip(np.log(amount / typical) / 0.4, -2, 2)[:, None]
    w = np.exp(TERM_AMOUNT_COEF * amt_z * pos) * (slot < L)
    cw = np.cumsum(w / w.sum(axis=1, keepdims=True), axis=1)
    term_idx = np.minimum((cw < rng.random(nr)[:, None]).sum(axis=1), grid_len[prod] - 1)
    term = grid[prod, term_idx]
    gov_micro = (prod == P["GOV_1764"]) & micro[ci]
    term = np.where(gov_micro, np.minimum(term, GOV_MICRO_MAX_TERM), term)

    # ---- Ставка: каталог × шум, надёжным ниже; по госпрограмме фиксирована. Одна на обращение ----
    base_rate = BASE_RATE[prod].copy()
    base_rate[gov_micro] = GOV_RATE_MICRO
    rate = base_rate * np.exp(RATE_SIGMA * rng.standard_normal(nr) - RATE_RISK_COEF * z_quality)
    rate = np.round(np.clip(rate, 0.6 * base_rate, 1.6 * base_rate), 1)
    rate = np.where(np.isin(prod, [P[p] for p in FIXED_RATE_PRODUCTS]), base_rate, rate)

    # ---- Залог ----
    p_coll = np.array([COLLATERAL_P.get(p, 0.0) for p in PRODUCTS])[prod]
    p_coll = np.where(p_coll < 1, np.minimum(p_coll * np.where(is_ie[ci], 0.6, 1.2), 1.0), p_coll)
    has_coll = rng.random(nr) < p_coll
    coll_raw = amount * lognorm(rng, 1.1, 0.35, nr)
    ltv = rng.uniform(0.4, SECURED_RE_MAX_LTV, nr)
    coll_raw = np.where(prod == P["SECURED_RE"], amount / ltv, coll_raw)
    collateral = np.where(has_coll, ceil2(coll_raw), 0).astype(np.int64)

    dsr_on = np.isin(prod, [P[p] for p in DSR_PRODUCTS])

    def offer_score(idx, amt, trm, coll):
        """T14, T16–T19 для обращений idx с параметрами заявки amt, trm, coll."""
        r_m = rate[idx] / 1200
        payment = amt * r_m / (1 - (1 + r_m) ** (-trm.astype(float)))
        dsr = payment * np.minimum(12, trm) / rev_r[idx]                   # долговая нагрузка (DSR)
        return (AMOUNT_COEF * np.clip(np.log(amt / typical[idx]), AMOUNT_CLIP_LO, 2)            # T14: сумма
                + TERM_COEF * np.clip(np.log(trm / BASE_TERM[prod[idx]]), -1.5, 1.5)            # T16: срок
                + RATE_COEF * np.clip(np.log(rate[idx] / base_rate[idx]), -0.5, 0.5)            # T17: ставка
                + DSR_COEF * np.clip(dsr - DSR_FREE, 0, 0.6) * dsr_on[idx]                      # T18: нагрузка
                + COLLATERAL_COEF * np.minimum(coll / amt, 2.0))                                # T19: залог

    # ---- Первая попытка и калибровка b_p (цели одобрения — по первым попыткам) ----
    need_score = np.sum(T_company, axis=0) + rng.normal(0, NOISE_NEED_SIGMA, nr)       # T15: общий шум
    score = (need_score + offer_score(np.arange(nr), amount, term, collateral)
             + rng.normal(0, NOISE_ATTEMPT_SIGMA, nr))                                 # T15: шум попытки
    b_p, eff_target, eligible = {}, {}, {}
    p_final = np.zeros(nr)
    for j, name in enumerate(PRODUCTS):
        sel = prod == j
        if not sel.any():
            continue
        ok = (~hard[sel]).astype(float)
        eligible[name] = float(ok.mean())
        cap = np.floor(0.9 * ok.mean() * 100) / 100
        target = min(APPROVAL_TARGET[name], cap)
        eff_target[name] = float(target)
        lo_b, hi_b = -10.0, 10.0
        for _ in range(40):
            b = (lo_b + hi_b) / 2
            share = np.mean(sigmoid(score[sel] + b) * ok)
            lo_b, hi_b = (b, hi_b) if share < target else (lo_b, b)
        b_p[name] = (lo_b + hi_b) / 2
        p_final[sel] = sigmoid(score[sel] + b_p[name]) * ok
    approved = (rng.random(nr) < p_final) & ~hard
    b_vec = np.array([b_p.get(p, 0.0) for p in PRODUCTS])[prod]

    # ---- Даты: первая попытка — за последний год, но не раньше регистрации ----
    window = np.minimum(HISTORY_DAYS, age[ci] * DAYS_PER_MONTH)
    off = rng.random(nr) * window                                                      # дней до выгрузки

    # ---- Повторные попытки после отказа: тот же продукт, меньше сумма / залог / длиннее срок ----
    coll_add = [P[p] for p in COLLATERAL_ADD_PRODUCTS]
    idx, a, t, cv, appr, o = np.arange(nr), amount, term, collateral, approved, off
    parts = [(idx, np.ones(nr, dtype=np.int64), a, t, cv, appr, o)]
    for attempt, p_retry in enumerate(RETRY_P, start=2):
        retry = ~appr & (rng.random(len(idx)) < p_retry)
        idx, a, t, cv, o = idx[retry], a[retry], t[retry], cv[retry], o[retry]
        mr = len(idx)
        pr = prod[idx]
        cut = rng.random(mr) < RETRY_CUT_P
        a = np.where(cut, np.maximum(AMT_MIN[pr], round2(a * rng.uniform(*RETRY_CUT, mr))), a).astype(np.int64)
        add = np.isin(pr, coll_add) & (cv == 0) & (rng.random(mr) < RETRY_COLLATERAL_P)
        cv = np.where(add, ceil2(a * lognorm(rng, 1.1, 0.35, mr)), cv).astype(np.int64)
        gpos = np.argmax(grid[pr] == t[:, None], axis=1)
        nxt = grid[pr, np.minimum(gpos + 1, grid_len[pr] - 1)]
        nxt = np.where(gov_micro[idx] & (nxt > GOV_MICRO_MAX_TERM), t, nxt)
        t = np.where(rng.random(mr) < RETRY_TERM_P, nxt, t)
        o = np.maximum(0.0, o - rng.uniform(*RETRY_DAYS, mr))
        s = need_score[idx] + offer_score(idx, a, t, cv) + rng.normal(0, NOISE_ATTEMPT_SIGMA, mr) + b_vec[idx]
        appr = (rng.random(mr) < sigmoid(s)) & ~hard[idx]
        parts.append((idx, np.full(mr, attempt, dtype=np.int64), a, t, cv, appr, o))

    need, attempt, amt_all, term_all, coll_all, appr_all, off_all = (
        np.concatenate([q[i] for q in parts]) for i in range(7))
    days = np.rint(off_all).astype(np.int64)
    order = np.lexsort((attempt, need, -days))  # по дате; в один день — по обращению и номеру попытки
    need, attempt, amt_all, term_all, coll_all, appr_all, days = (
        x[order] for x in (need, attempt, amt_all, term_all, coll_all, appr_all, days))

    apps = comp.iloc[ci[need]].reset_index(drop=True)
    apps["application_id"] = np.arange(1, len(apps) + 1, dtype=np.int64)
    apps["application_date"] = (SNAPSHOT_DATE - days.astype("timedelta64[D]")).astype(str)
    apps["product_type"] = np.array(PRODUCTS)[prod[need]]
    apps["amount"] = amt_all
    apps["term_months"] = term_all
    apps["rate"] = rate[need]
    apps["collateral_value"] = coll_all
    apps["approved"] = appr_all.astype(np.int64)
    calib = {"b_p": b_p, "effective_target": eff_target, "eligible_share": eligible,
             "attempt": attempt, "n_needs": int(nr)}
    return apps[COLUMNS], calib


def hard_rejects(c, prod):
    """Правила H1–H3, H5, H6 (H4 относился к убранным BANK_GUARANTEE/TENDER_LOAN).
    c — строки компаний, выровненные с prod (индексы продуктов)."""
    age = col(c, "company_age_months")
    ta = col(c, "tax_arrears_amount")
    rev = col(c, "revenue_last_year")
    okved = c["okved_section"].to_numpy(dtype=str)
    h1 = (col(c, "accounts_blocked_flag") == 1) | (col(c, "bankruptcy_flag") == 1)
    h2 = age < 3
    h3 = (age < 12) & np.isin(prod, [P["INVESTMENT"], P["SECURED_RE"], P["CREDIT_LINE_REV"], P["GOV_1764"]])
    h5 = (prod == P["GOV_1764"]) & ((ta > 50_000) | ~np.isin(okved, GOV_OKVED))
    h6 = (prod == P["FACTORING"]) & (rev < 20e6)
    return h1 | h2 | h3 | h5 | h6


# --------------------------------------------------------------------------- #
# Пайплайн
# --------------------------------------------------------------------------- #
def generate(n_companies, seed):
    rng = np.random.default_rng(seed)
    comp, internal = generate_companies(rng, n_companies)
    apps, calib = generate_applications(rng, comp)
    return comp, apps, calib, internal


def to_csv_bytes(df):
    return df.to_csv(index=False, lineterminator="\n").encode("utf-8")


# --------------------------------------------------------------------------- #
# Проверки (2.9) и контрольные значения (2.8)
# --------------------------------------------------------------------------- #
def run_asserts(comp, apps, internal):
    assert list(apps.columns) == COLUMNS and len(COLUMNS) == 28, "состав/порядок колонок"
    assert apps["application_id"].is_unique, "application_id не уникален"
    days = (SNAPSHOT_DATE - pd.to_datetime(apps["application_date"]).to_numpy().astype("datetime64[D]")
            ).astype(np.int64)
    assert (days >= 0).all() and (days <= HISTORY_DAYS + RETRY_DAYS[1]).all(), "дата заявки вне окна"
    assert (days <= apps["company_age_months"] * DAYS_PER_MONTH + 1).all(), "заявка раньше регистрации"
    assert apps["application_date"].is_monotonic_increasing, "заявки не по дате"
    assert apps["product_type"].isin(PRODUCTS).all(), "неизвестный product_type"
    for c in FLAG_COLS:
        assert apps[c].isin([0, 1]).all(), f"{c} не 0/1"
    for c in MONEY_COLS + ["company_age_months", "bki_max_dpd_12m", "term_months"]:
        assert pd.api.types.is_integer_dtype(apps[c]), f"{c} не целое"
    assert (apps["amount"] > 0).all() and (apps["revenue_last_year"] > 0).all()

    inn = comp["inn"].astype(str)
    inn_len = np.where(comp["legal_form"] == "IE", 12, 10)
    assert inn.is_unique and (inn.str.len() == inn_len).all(), "inn: уникальность и длина"
    assert inn_is_valid(inn).all(), "inn: контрольные цифры"
    assert (inn.str[:2] == comp["region_code"]).all(), "inn: первые 2 цифры = region_code"

    prod = apps["product_type"].map(P).to_numpy()
    term_ok = [t in TERM_GRID[j] for j, t in zip(*np.unique(np.c_[prod, apps["term_months"]], axis=0).T)]
    assert all(term_ok), "term_months вне сетки продукта"
    base_rate = BASE_RATE[prod]
    tol = 0.06  # округление ставки до 0.1
    gov = prod == P["GOV_1764"]
    assert ((apps["rate"] >= 0.6 * base_rate - tol) & (apps["rate"] <= 1.6 * base_rate + tol))[~gov].all(), "rate"
    gov_micro = gov & (apps["msp_category"] == "micro").to_numpy()
    rate_arr = apps["rate"].to_numpy()
    assert (rate_arr[gov_micro] == GOV_RATE_MICRO).all(), "ставка 1764 для micro"
    assert (rate_arr[gov & ~gov_micro] == GOV_RATE_SMALL_MEDIUM).all(), "ставка 1764 для small/medium"
    assert (apps["term_months"].to_numpy()[gov_micro] <= GOV_MICRO_MAX_TERM).all(), "срок 1764 для micro"

    coll = apps["collateral_value"].to_numpy()
    amt = apps["amount"].to_numpy()
    assert (coll >= 0).all(), "collateral_value >= 0"
    assert (coll[np.isin(prod, [P[p] for p in NO_COLLATERAL_PRODUCTS])] == 0).all(), "залог у беззалогового продукта"
    sre = prod == P["SECURED_RE"]
    assert (coll[sre] > 0).all() and (amt[sre] <= SECURED_RE_MAX_LTV * coll[sre]).all(), "SECURED_RE: LTV"

    assert (apps["approved"].to_numpy()[hard_rejects(apps, prod)] == 0).all(), "H1–H6"

    emp = col(comp, "employees_count")
    rev = col(comp, "revenue_last_year")
    has_emp = ~np.isnan(emp)
    for cat, emax, rmax in [("micro", 15, 120e6), ("small", 100, 800e6), ("medium", 250, 2e9)]:
        s = (comp["msp_category"] == cat).to_numpy()
        assert (emp[s & has_emp] <= emax).all() and (rev[s] <= rmax).all(), f"msp {cat}"

    reg = comp["tax_regime"].to_numpy()
    ie = (comp["legal_form"] == "IE").to_numpy()
    e0 = np.nan_to_num(emp)
    assert ((rev <= 60e6) & (e0 <= 5))[reg == "AUSN"].all(), "AUSN"
    assert (ie & (rev <= 2.4e6) & (e0 == 0))[reg == "NPD"].all(), "NPD"
    assert (ie & (rev <= 60e6) & (e0 <= 15))[reg == "PSN"].all(), "PSN"
    assert (comp["okved_section"].to_numpy()[reg == "ESHN"] == "A").all(), "ESHN"
    assert (rev[np.isin(reg, ["USN_INCOME", "USN_INCOME_EXPENSE"])] <= 490e6).all(), "USN"

    for c in IE_EMPTY_COLS:
        assert comp.loc[ie, c].isna().all(), f"IE: {c} не пусто"
    for c in ["unreliable_info_flag", "mass_address_flag", "director_risk_flag"]:
        assert (comp.loc[ie, c] == 0).all(), f"IE: {c} != 0"

    assert (comp.loc[comp["rnp_flag"] == 1, "gov_contracts_amount_3y"] > 0).all(), "rnp_flag"
    assert (comp["bki_total_debt"].isna() == comp["bki_max_dpd_12m"].isna()).all(), "bki пустоты"

    f = internal["has_fin"]
    A = internal["A"][f]
    assert np.all(np.abs(internal["r1100"][f] + internal["r1200"][f] - A) <= 0.01 * A)
    assert np.all(np.abs(internal["r1300"][f] + internal["r1400"][f] + internal["r1500"][f] - A) <= 0.01 * A)


def correlations(comp):
    llc = (comp["legal_form"] == "LLC").to_numpy()
    rev = col(comp, "revenue_last_year")
    lrev = np.log(rev)
    dtr = col(comp, "debt_to_revenue")
    bki_r = col(comp, "bki_total_debt") / rev
    both = (dtr > 0) & (bki_r > 0)
    return [
        ("Spearman ln(rev)~ln(total_assets), LLC",
         spearman(lrev[llc], np.log(col(comp, "total_assets")[llc])), 0.85, None),
        ("Spearman ln(rev)~ln(1+employees), все",
         spearman(lrev, np.log1p(col(comp, "employees_count"))), 0.30, None),
        ("Spearman ln(rev)~ln(taxes+1)",
         spearman(lrev, np.log1p(col(comp, "taxes_paid_last_year"))), 0.70, None),
        ("Spearman net_margin~equity_ratio, LLC",
         spearman(col(comp, "net_margin")[llc], col(comp, "equity_ratio")[llc]), 0.20, None),
        ("Spearman equity_ratio~current_ratio, LLC",
         spearman(col(comp, "equity_ratio")[llc], col(comp, "current_ratio")[llc]), 0.20, None),
        ("Spearman debt_to_revenue~bki/rev (оба > 0)",
         spearman(dtr[both], bki_r[both]), 0.50, None),
        ("Spearman ln(age)~ln(rev)",
         spearman(np.log(col(comp, "company_age_months")), lrev), 0.10, 0.40),
    ]


def control_values(comp, apps, internal, calib):
    """Возвращает список (название, значение, lo, hi)."""
    first = calib["attempt"] == 1
    retry = ~first
    per_product = apps.groupby(["inn", "product_type"]).size()
    repeat_inn = per_product[per_product > 1].index.get_level_values("inn").unique()
    ie = (comp["legal_form"] == "IE").to_numpy()
    llc = ~ie
    msp = comp["msp_category"]
    fin = internal["has_fin"]
    rev = col(comp, "revenue_last_year")
    has_bki = comp["bki_total_debt"].notna().to_numpy()
    dpd = col(comp, "bki_max_dpd_12m")
    e = col(comp, "equity_ratio")
    cr = col(comp, "current_ratio")
    ta_pos = col(comp, "tax_arrears_amount") > 0
    stress = internal["stress"]
    stress_ratio = ta_pos[llc & stress].mean() / ta_pos[llc & ~stress].mean()
    rows = [
        ("Доля IE", ie.mean(), 0.60, 0.64),
        ("Доля micro", (msp == "micro").mean(), 0.963, 0.983),
        ("Доля small", (msp == "small").mean(), 0.013, 0.033),
        ("Доля medium", (msp == "medium").mean(), 0.0, 0.014),
        ("Заявок на компанию", len(apps) / len(comp), 3.6, 4.4),
        ("Доля повторных попыток (после отказа)", retry.mean(), 0.12, 0.25),
        ("Одобрение повторных попыток", apps["approved"].to_numpy()[retry].mean(), 0.30, 0.60),
        ("Компаний с ≥ 2 заявками на один продукт", len(repeat_inn) / len(comp), 0.45, 0.75),
        ("Общая доля одобрения", apps["approved"].mean(), 0.50, 0.65),
        ("accounts_blocked_flag", comp["accounts_blocked_flag"].mean(), 0.02, 0.04),
        ("bankruptcy_flag", comp["bankruptcy_flag"].mean(), 0.002, 0.008),
        ("unreliable_info_flag (LLC)", comp.loc[llc, "unreliable_info_flag"].mean(), 0.03, 0.05),
        ("mass_address_flag (LLC)", comp.loc[llc, "mass_address_flag"].mean(), 0.04, 0.06),
        ("director_risk_flag (LLC)", comp.loc[llc, "director_risk_flag"].mean(), 0.01, 0.03),
        ("Доля без кредитной истории", 1 - has_bki.mean(), 0.65, 0.70),
        ("dpd > 0 среди имеющих историю", (dpd[has_bki] > 0).mean(), 0.15, 0.19),
        ("Доля с госконтрактами", (comp["gov_contracts_amount_3y"] > 0).mean(), 0.07, 0.10),
        ("Доля пустых net_margin", comp["net_margin"].isna().mean(), 0.61, 0.65),
        ("Медиана выручки IE, млн", np.median(rev[ie]) / 1e6, 2.25, 3.75),
        ("Медиана выручки LLC micro, млн",
         np.median(rev[llc & (msp == "micro").to_numpy()]) / 1e6, 6.75, 11.25),
        ("Доля LLC с equity_ratio < 0", (e[fin] < 0).mean(), 0.08, 0.15),
        ("Медиана equity_ratio (LLC)", np.median(e[fin]), 0.15, 0.45),
        ("Медиана current_ratio (LLC)", np.median(cr[fin]), 0.95, 1.25),
        ("Доля current_ratio < 1 (LLC)", (cr[fin] < 1).mean(), 0.35, 0.45),
        ("Налоговый долг LLC: stress=1 / stress=0", stress_ratio, 1.5, 3.0),
    ]
    share = apps.loc[first, "product_type"].value_counts(normalize=True)
    rate = apps[first].groupby("product_type")["approved"].mean()
    for j, p in enumerate(PRODUCTS):
        rows.append((f"Доля обращений {p}", share.get(p, 0.0), PRODUCT_W[j] - 0.05, PRODUCT_W[j] + 0.05))
    for p in PRODUCTS:
        t = calib["effective_target"].get(p, APPROVAL_TARGET[p])
        rows.append((f"Одобрение {p}, 1-я попытка (цель {t:.2f})", rate.get(p, np.nan), t - 0.02, t + 0.02))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Генератор мок-данных заявок МСБ (spec v1.1, v1.4)")
    ap.add_argument("--n-companies", type=int, default=130_000)  # ≈ 500 000 строк
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="data/applications.csv")
    args = ap.parse_args()

    t0 = time.perf_counter()
    comp, apps, calib, internal = generate(args.n_companies, args.seed)
    t_gen = time.perf_counter() - t0

    run_asserts(comp, apps, internal)

    corr = correlations(comp)
    for name, v, lo, hi in corr:
        assert v >= lo and (hi is None or v <= hi), f"{name} = {v:.3f} вне диапазона"

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = to_csv_bytes(apps)
    out.write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()

    # Разбивка по типу заявителя. У ИП колонки, пустые/нулевые по определению, не пишем.
    is_ie_row = apps["legal_form"] == "IE"
    apps_ie = apps[is_ie_row].drop(columns=IE_DROP_COLS)
    apps_llc = apps[~is_ie_row]
    stem = out.with_suffix("")
    ie_path = Path(f"{stem}_ie.csv")
    llc_path = Path(f"{stem}_llc.csv")
    ie_path.write_bytes(to_csv_bytes(apps_ie))
    llc_path.write_bytes(to_csv_bytes(apps_llc))

    # Детерминизм: повторная генерация с тем же seed даёт идентичный файл
    _, apps2, _, _ = generate(args.n_companies, args.seed)
    assert hashlib.sha256(to_csv_bytes(apps2)).hexdigest() == sha, "результат не детерминирован"

    rates = apps.groupby("product_type")["approved"].mean()
    first = calib["attempt"] == 1
    rates_first = apps[first].groupby("product_type")["approved"].mean()
    meta = {
        "seed": args.seed,
        "generator_version": GENERATOR_VERSION,
        "n_companies": int(len(comp)),
        "n_rows": int(len(apps)),
        "columns": COLUMNS,
        "n_rows_ie": int(len(apps_ie)),
        "n_rows_llc": int(len(apps_llc)),
        "columns_ie": list(apps_ie.columns),
        "snapshot_date": str(SNAPSHOT_DATE),
        "n_needs": calib["n_needs"],
        "n_rows_by_attempt": {str(a): int(c) for a, c in zip(*np.unique(calib["attempt"], return_counts=True))},
        "approval_rate_by_product": {p: round(float(rates[p]), 4) for p in PRODUCTS if p in rates},
        "approval_rate_first_attempt_by_product": {p: round(float(rates_first[p]), 4)
                                                   for p in PRODUCTS if p in rates_first},
        "approval_rate_retry": round(float(apps["approved"].to_numpy()[~first].mean()), 4),
        "approval_target_spec": APPROVAL_TARGET,
        "approval_target_effective": calib["effective_target"],
        "eligible_share_by_product": {k: round(v, 4) for k, v in calib["eligible_share"].items()},
        "intercept_b_p": {k: round(v, 4) for k, v in calib["b_p"].items()},
        "approval_rate_total": round(float(apps["approved"].mean()), 4),
        "csv_sha256": sha,
    }
    meta_path = out.parent / "dataset_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Сводка ----
    print(f"Компаний: {len(comp):,}, обращений: {calib['n_needs']:,}, строк: {len(apps):,}, "
          f"генерация: {t_gen:.1f} с")
    print(f"CSV: {out}  sha256={sha[:16]}…\n     {ie_path} ({len(apps_ie):,}), {llc_path} ({len(apps_llc):,})\nMeta: {meta_path}\n")
    print("Контрольные значения (2.8):")
    n_warn = 0
    for name, v, lo, hi in control_values(comp, apps, internal, calib):
        ok = lo <= v <= hi
        n_warn += not ok
        print(f"  [{'OK  ' if ok else 'WARN'}] {name:<48} {v:8.3f}   ожид. {lo:.3f}…{hi:.3f}")
    print("Корреляции (assert):")
    for name, v, lo, hi in corr:
        rng_s = f"≥ {lo:.2f}" if hi is None else f"{lo:.2f}…{hi:.2f}"
        print(f"  [OK  ] {name:<48} {v:8.3f}   ожид. {rng_s}")
    for p, t in calib["effective_target"].items():
        if t < APPROVAL_TARGET[p]:
            print(f"  ! цель одобрения {p} снижена {APPROVAL_TARGET[p]:.2f} → {t:.2f} "
                  f"(без жёсткого отказа {calib['eligible_share'][p]:.1%} строк)")
    print(f"\nВсе assert-проверки (2.9) пройдены. WARN по ориентирам: {n_warn}.")


if __name__ == "__main__":
    main()
