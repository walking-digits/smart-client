"""Обучение модели 1 на мок-данных (../data/applications.csv). В Docker-образ не входит.

Из папки ML_Part/model1 (≈ 4 минуты):
    python train.py
Сохраняет модели в artifacts/ — их и кладём в git.

    oftenhood   таблица «компания × 10 продуктов», target = приходила ли компания за продуктом; бинарный LightGBM
    amount      log(amount / revenue), LightGBM L1 (медиана)
    rate        rate без GOV_1764 (там ставка фиксирована), L1
    collateral  collateral_value / amount, 0 без залога, только продукты с залогом, L1
    terms       самый частый срок продукта (без модели)
Учимся на всех заявках, кроме 5% тестовых компаний (их проверяет мок-бэкенд).
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent / "mock"))  # загрузка данных и разбиение train/test
from contract import CATALOG, COMPANY_FIELDS, PRODUCT_TYPES, validate_offer  # noqa: E402
from data import company_from_row, load_applications, test_mask  # noqa: E402
from model import ARTIFACTS, COLL_MIN_RATIO, GOV_MICRO, load, make_X, predict  # noqa: E402

PARAMS = {
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "seed": 42,
    "verbose": -1,
}
N_FOLDS = 5


def fit_cv(params, X, y, groups):
    """GroupKFold по ИНН → OOF-прогноз; финальная модель на всех данных со средним числом деревьев."""
    oof, rounds = np.zeros(len(y)), []
    for tr, va in GroupKFold(N_FOLDS).split(X, y, groups):
        m = lgb.train(params, lgb.Dataset(X.iloc[tr], y[tr]), num_boost_round=5000,
                      valid_sets=[lgb.Dataset(X.iloc[va], y[va])],
                      callbacks=[lgb.early_stopping(100, verbose=False)])
        oof[va] = m.predict(X.iloc[va], num_iteration=m.best_iteration)
        rounds.append(m.best_iteration)
    final = lgb.train(params, lgb.Dataset(X, y), num_boost_round=int(np.mean(rounds)))
    return oof, final


def train_oftenhood(df):
    companies = df.drop_duplicates("inn")[COMPANY_FIELDS].reset_index(drop=True)
    rows = companies.loc[companies.index.repeat(len(PRODUCT_TYPES))].reset_index(drop=True)
    rows["product_type"] = PRODUCT_TYPES * len(companies)
    applied = set(zip(df["inn"], df["product_type"]))
    y = np.array([(i, p) in applied for i, p in zip(rows["inn"], rows["product_type"])], dtype=float)

    oof, model = fit_cv({**PARAMS, "objective": "binary"}, make_X(rows), y, rows["inn"])
    prior = pd.Series(y).groupby(rows["product_type"]).transform("mean").to_numpy()
    P, Y = oof.reshape(-1, len(PRODUCT_TYPES)), y.reshape(-1, len(PRODUCT_TYPES))
    top3 = np.argsort(-P, axis=1)[:, :3]
    idx = np.arange(len(P))[:, None]
    print(f"oftenhood: logloss {log_loss(y, oof):.4f} (частота продукта: {log_loss(y, prior):.4f}), "
          f"AUC {roc_auc_score(y, oof):.3f}, top-1 {Y[idx[:, 0], P.argmax(1)].mean():.1%}, "
          f"recall@3 {(Y[idx, top3].sum(1) / Y.sum(1)).mean():.1%}")
    model.save_model(str(ARTIFACTS / "oftenhood.txt"))


def train_offer_params(df):
    X = make_X(df)
    prod = df["product_type"]
    amount = df["amount"].to_numpy(dtype=float)
    with_coll = prod.map(lambda p: CATALOG[p]["collateral"] != "zero").to_numpy()
    tasks = {
        "amount": (np.ones(len(df), dtype=bool), np.log(amount / df["revenue_last_year"].to_numpy(dtype=float))),
        "rate": ((prod != "GOV_1764").to_numpy(), df["rate"].to_numpy(dtype=float)),
        "collateral": (with_coll, df["collateral_value"].to_numpy(dtype=float) / amount),
    }
    for name, (mask, y) in tasks.items():
        y = y[mask]
        oof, model = fit_cv({**PARAMS, "objective": "l1"}, X[mask], y, df["inn"][mask])
        base = pd.Series(y).groupby(prod[mask].to_numpy()).transform("median").to_numpy()  # без учёта компании
        if name == "amount":
            print(f"amount: ошибка ×{np.exp(np.mean(np.abs(oof - y))):.2f} "
                  f"(медиана по продукту: ×{np.exp(np.mean(np.abs(base - y))):.2f})")
        elif name == "rate":
            print(f"rate: MAE {np.mean(np.abs(oof - y)):.2f} п.п. (медиана по продукту: {np.mean(np.abs(base - y)):.2f})")
        else:
            print(f"collateral: есть ли залог угадали {np.mean((oof >= COLL_MIN_RATIO) == (y > 0)):.1%} "
                  f"(медиана по продукту: {np.mean((base >= COLL_MIN_RATIO) == (y > 0)):.1%})")
        model.save_model(str(ARTIFACTS / f"offer_{name}.txt"))

    terms = df.groupby("product_type")["term_months"].agg(lambda s: int(s.mode()[0])).to_dict()
    gov_micro = df[(prod == "GOV_1764") & (df["msp_category"] == "micro")]
    terms[GOV_MICRO] = int(gov_micro["term_months"].mode()[0])
    (ARTIFACTS / "offer_terms.json").write_text(json.dumps(terms, indent=2), encoding="utf-8")
    print(f"terms: {terms}")


def check_contract():
    """Предложения для 500 тестовых компаний должны проходить контракт."""
    models = load()
    test = load_applications()
    test = test[test_mask(test)].drop_duplicates("inn").head(500)
    bad = [(r["inn"], err) for r in test.to_dict("records")
           for it in predict(models, company_from_row(r))
           for err in validate_offer(it["offer"], r["msp_category"])]
    print(f"Проверка контракта на 500 тестовых компаниях: нарушений {len(bad)}", *bad[:5], sep="\n  ")


if __name__ == "__main__":
    data = load_applications()
    data = data[~test_mask(data)].reset_index(drop=True)
    print(f"Заявок: {len(data):,}, компаний: {data['inn'].nunique():,}")
    ARTIFACTS.mkdir(exist_ok=True)
    train_oftenhood(data)
    train_offer_params(data)
    check_contract()
