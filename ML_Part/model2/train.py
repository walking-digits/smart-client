"""Обучение модели 2 (шанс одобрения) на мок-данных (../data/applications.csv). В Docker-образ не входит.

Из папки ML_Part/model2 (≈ несколько минут):
    python train.py
Сохраняет модель в artifacts/approval.txt — её и кладём в git.

Бинарный LightGBM, target = approved, все заявки (жёсткие отказы проверяются до вызова сервиса,
модель всё равно выучит их сама). Монотонность по сумме и залогу — см. MONOTONE в model.py.
Учимся на всех заявках, кроме 5% тестовых компаний (их проверяет мок-бэкенд).
"""
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent / "mock"))  # загрузка данных и разбиение train/test
from contract import validate_offer  # noqa: E402
from data import company_from_row, load_applications, offer_from_row, test_mask  # noqa: E402
from model import ARTIFACTS, find_alternative, load, make_X, monotone_constraints, predict_rows  # noqa: E402

PARAMS = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "monotone_constraints_method": "intermediate",
    "seed": 42,
    "verbose": -1,
}
N_FOLDS = 5


def train(df):
    X, y, groups = make_X(df), df["approved"].to_numpy(dtype=float), df["inn"]
    params = {**PARAMS, "monotone_constraints": monotone_constraints(X.columns)}

    oof, rounds = np.zeros(len(y)), []
    for tr, va in GroupKFold(N_FOLDS).split(X, y, groups):
        m = lgb.train(params, lgb.Dataset(X.iloc[tr], y[tr]), num_boost_round=5000,
                      valid_sets=[lgb.Dataset(X.iloc[va], y[va])],
                      callbacks=[lgb.early_stopping(100, verbose=False)])
        oof[va] = m.predict(X.iloc[va], num_iteration=m.best_iteration)
        rounds.append(m.best_iteration)

    prior = pd.Series(y).groupby(df["product_type"].to_numpy()).transform("mean").to_numpy()
    print(f"approval: AUC {roc_auc_score(y, oof):.3f} (доля одобрения продукта: {roc_auc_score(y, prior):.3f}), "
          f"logloss {log_loss(y, oof):.4f} (доля продукта: {log_loss(y, prior):.4f}), деревьев {int(np.mean(rounds))}")
    print("Калибровка (децили прогноза): прогноз → факт")
    for _, g in pd.DataFrame({"p": oof, "y": y}).groupby(pd.qcut(oof, 10, duplicates="drop"), observed=True):
        print(f"  {g.p.mean():.3f} → {g.y.mean():.3f}")

    model = lgb.train(params, lgb.Dataset(X, y), num_boost_round=int(np.mean(rounds)))
    model.save_model(str(ARTIFACTS / "approval.txt"))


def check(n=300):
    """На тестовых заявках: шанс не растёт с суммой и не падает с залогом; /alternative соблюдает контракт."""
    model = load()
    test = load_applications()
    test = test[test_mask(test)].sample(n, random_state=0).to_dict("records")
    bad_mono, bad_alt, found = 0, [], 0
    for r in test:
        c, o = company_from_row(r), offer_from_row(r)
        amounts = [{**o, "amount": int(o["amount"] * f)} for f in (1.0, 0.8, 0.6, 0.4)]   # сумма ↓
        colls = [{**o, "collateral_value": int(o["amount"] * f)} for f in (0, 0.5, 1, 2)]  # залог ↑
        bad_mono += bool(np.any(np.diff(predict_rows(model, c, amounts)) < -1e-9))
        bad_mono += bool(np.any(np.diff(predict_rows(model, c, colls)) < -1e-9))
        res = find_alternative(model, c, o, 0.7)
        alt = res["offer"]
        if alt is not None and alt is not o:
            found += 1
            errs = validate_offer(alt, c["msp_category"])
            if alt["product_type"] != o["product_type"] or alt["collateral_value"] > o["collateral_value"] \
                    or res["approval_probability"] <= 0.7 or errs:
                bad_alt.append((r["inn"], res, errs))
    print(f"Проверка на {n} тестовых заявках: нарушений монотонности {bad_mono}; "
          f"/alternative (gamma 0.7): найдено {found}, нарушений {len(bad_alt)}", *bad_alt[:3], sep="\n  ")


if __name__ == "__main__":
    data = load_applications()
    data = data[~test_mask(data)].reset_index(drop=True)
    print(f"Заявок: {len(data):,}, компаний: {data['inn'].nunique():,}, доля одобрения: {data['approved'].mean():.3f}")
    ARTIFACTS.mkdir(exist_ok=True)
    train(data)
    check()
