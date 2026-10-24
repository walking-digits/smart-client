#!/usr/bin/env python3
"""Мок Backend: отправляет в ML-сервис запросы по контракту API.md и проверяет ответы.

Компании и заявки берутся из data/applications.csv. По умолчанию — только тестовая часть
(разбиение по ИНН, см. data.is_test), чтобы метрики не считались на обучающих данных.

    python mock/mock_backend.py --url http://localhost:8000 --scenario all --n 300

Сценарии:
    offers       POST /offers: 10 продуктов по одному, сортировка по oftenhood, допустимые предложения;
                 метрики — попадание в продукты, на которые компания реально подавала заявки
    approval     POST /approval: вероятность 0…1; метрики по колонке approved (AUC, logloss)
    alternative  POST /alternative: порог gamma, залог не больше исходного, согласованность с /approval
    errors       заведомо неверные запросы: ждём 422 VALIDATION_ERROR (и 200 на контрольные)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib import error, request

import numpy as np
import pandas as pd

from contract import PRODUCT_TYPES, is_prob, validate_offer
from data import company_from_row, load_applications, offer_from_row, test_mask

GAMMAS = [0.5, 0.7, 0.9]
TOL = 1e-3  # допуск при сравнении вероятностей из разных ручек


class Client:
    def __init__(self, url, timeout):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def post(self, path, body):
        req = request.Request(self.url + path, data=json.dumps(body, ensure_ascii=False).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
        t0 = time.perf_counter()
        try:
            with request.urlopen(req, timeout=self.timeout) as r:
                status, raw = r.status, r.read()
        except error.HTTPError as e:
            status, raw = e.code, e.read()
        ms = (time.perf_counter() - t0) * 1000
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = raw.decode("utf-8", "replace")[:200]
        return status, payload, ms


def record(label, path, body, status, resp, ms, violations, **extra):
    return {"label": label, "path": path, "request": body, "status": status, "response": resp,
            "ms": ms, "violations": violations, **extra}


# --------------------------------------------------------------------------- #
# offers
# --------------------------------------------------------------------------- #
def check_offers(client, case):
    body = {"company": case["company"]}
    status, resp, ms = client.post("/offers", body)
    v, ranking = [], []
    if status != 200:
        v.append(f"HTTP {status}: {resp}")
    else:
        items = resp.get("offers") if isinstance(resp, dict) else None
        if not isinstance(items, list):
            v.append("в ответе нет массива offers")
            items = []
        elif len(items) != len(PRODUCT_TYPES):
            v.append(f"offers: {len(items)} элементов, нужно {len(PRODUCT_TYPES)}")
        scores = []
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                v.append(f"offers[{i}]: не объект")
                continue
            s = it.get("oftenhood")
            if is_prob(s):
                scores.append(s)
            else:
                v.append(f"offers[{i}].oftenhood={s!r} вне 0…1")
            v += [f"offers[{i}]: {e}" for e in validate_offer(it.get("offer"), case["company"]["msp_category"],
                                                              with_collateral_type=False)]
            if isinstance(it.get("offer"), dict):
                ranking.append(it["offer"].get("product_type"))
        if sorted(map(str, ranking)) != sorted(PRODUCT_TYPES):
            v.append(f"продукты не по одному на каждый из 10: {ranking}")
        if len(scores) == len(items) and any(a < b for a, b in zip(scores, scores[1:])):
            v.append("offers не отсортированы по убыванию oftenhood")
    return record(case["label"], "/offers", body, status, resp, ms, v, ranking=ranking, wanted=case["wanted"])


def summary_offers(recs):
    ok = [r for r in recs if not r["violations"]]
    if not ok:
        return []
    top1 = np.mean([r["ranking"][0] in r["wanted"] for r in ok])
    rec3 = np.mean([len(set(r["ranking"][:3]) & r["wanted"]) / len(r["wanted"]) for r in ok])
    return [f"top-1 среди реальных заявок компании: {top1:.1%}; recall@3: {rec3:.1%}"]


# --------------------------------------------------------------------------- #
# approval
# --------------------------------------------------------------------------- #
def check_approval(client, case):
    body = {"company": case["company"], "offer": case["offer"]}
    status, resp, ms = client.post("/approval", body)
    v, p = [], None
    if status != 200:
        v.append(f"HTTP {status}: {resp}")
    else:
        p = resp.get("approval_probability") if isinstance(resp, dict) else None
        if not is_prob(p):
            v.append(f"approval_probability={p!r} вне 0…1")
            p = None
    return record(case["label"], "/approval", body, status, resp, ms, v, p=p, y=case["y"])


def roc_auc(y, p):
    y = np.asarray(y, dtype=bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = pd.Series(p).rank().to_numpy()
    return (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def summary_approval(recs):
    ok = [r for r in recs if r["p"] is not None]
    if not ok:
        return []
    y = np.array([r["y"] for r in ok])
    p = np.array([r["p"] for r in ok])
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    logloss = -np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))
    return [f"AUC {roc_auc(y, p):.3f}; logloss {logloss:.3f}; Brier {np.mean((p - y) ** 2):.3f}; "
            f"средний прогноз {p.mean():.3f}, факт {y.mean():.3f}"]


# --------------------------------------------------------------------------- #
# alternative
# --------------------------------------------------------------------------- #
def approval_of(client, company, offer):
    status, resp, _ = client.post("/approval", {"company": company, "offer": offer})
    return resp.get("approval_probability") if status == 200 and isinstance(resp, dict) else None


def check_alternative(client, case):
    company, src, gamma = case["company"], case["offer"], case["gamma"]
    body = {"company": company, "offer": src, "gamma": gamma}
    status, resp, ms = client.post("/alternative", body)
    v = []
    extra = {"gamma": gamma, "source_pass": None, "found": None, "likelyhood": None}
    if status != 200 or not isinstance(resp, dict):
        v.append(f"HTTP {status}: {resp}")
        return record(case["label"], "/alternative", body, status, resp, ms, v, **extra)

    missing = [k for k in ("source_approval_probability", "offer", "likelyhood", "approval_probability")
               if k not in resp]
    if missing:
        v.append(f"нет полей: {', '.join(missing)}")
        return record(case["label"], "/alternative", body, status, resp, ms, v, **extra)

    sp, alt, lk, ap = (resp[k] for k in ("source_approval_probability", "offer", "likelyhood",
                                         "approval_probability"))
    if not is_prob(sp):
        v.append(f"source_approval_probability={sp!r} вне 0…1")
    else:
        extra["source_pass"] = sp > gamma
        p_src = approval_of(client, company, src)
        if p_src is not None and abs(p_src - sp) > TOL:
            v.append(f"source_approval_probability={sp} ≠ /approval={p_src}")

    if alt is None:
        extra["found"] = False
        if lk is not None or ap is not None:
            v.append("offer = null, но likelyhood / approval_probability не null")
        if extra["source_pass"]:
            v.append(f"исходное проходит порог ({sp} > {gamma}), но offer = null")
    else:
        extra["found"] = True
        v += [f"offer: {e}" for e in validate_offer(alt, company["msp_category"])]
        if not is_prob(lk):
            v.append(f"likelyhood={lk!r} вне 0…1")
        else:
            extra["likelyhood"] = lk
        if not is_prob(ap):
            v.append(f"approval_probability={ap!r} вне 0…1")
        else:
            if ap <= gamma:
                v.append(f"approval_probability={ap} не больше gamma={gamma}")
            if isinstance(alt, dict) and not validate_offer(alt, company["msp_category"]):
                p_alt = approval_of(client, company, alt)
                if p_alt is not None and abs(p_alt - ap) > TOL:
                    v.append(f"approval_probability={ap} ≠ /approval={p_alt}")
        if isinstance(alt, dict) and alt.get("product_type") != src["product_type"]:
            v.append(f"сменился продукт: {src['product_type']} → {alt.get('product_type')}")
        if isinstance(alt, dict) and alt.get("collateral_value") and \
                (alt.get("collateral_type"), alt.get("collateral_subtype")) != \
                (src["collateral_type"], src["collateral_subtype"]):
            v.append("сменился вид залога")
        if isinstance(alt, dict) and isinstance(alt.get("collateral_value"), int) \
                and alt["collateral_value"] > src["collateral_value"]:
            v.append(f"залог вырос: {src['collateral_value']} → {alt['collateral_value']}")
        if extra["source_pass"]:
            if alt != src:
                v.append("исходное проходит порог, но вернулось другое предложение")
            if is_prob(lk) and abs(lk - 1) > TOL:
                v.append(f"исходное проходит порог, но likelyhood={lk}, ждали 1")
    return record(case["label"], "/alternative", body, status, resp, ms, v, **extra)


def summary_alternative(recs):
    ok = [r for r in recs if not r["violations"] and r["source_pass"] is not None]
    if not ok:
        return []
    passed = [r for r in ok if r["source_pass"]]
    rest = [r for r in ok if not r["source_pass"]]
    lines = [f"исходное проходит порог: {len(passed)} из {len(ok)}"]
    if rest:
        found = [r for r in rest if r["found"]]
        line = f"остальным найдена альтернатива: {len(found)} из {len(rest)}"
        if found:
            line += f", средний likelyhood {np.mean([r['likelyhood'] for r in found]):.3f}"
        lines.append(line)
    return lines


# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #
def error_cases(company):
    """company — валидная Company ООО micro. Возвращает (название, path, тело, ожидаемый HTTP)."""
    no_type = {"collateral_type": None, "collateral_subtype": None}
    ok_offer = {"product_type": "WORKING_CAPITAL", "amount": 5_000_000, "term_months": 24,
                "rate": 20.0, "collateral_value": 0, **no_type}
    gov_offer = {"product_type": "GOV_1764", "amount": 5_000_000, "term_months": 24,
                 "rate": 17.5, "collateral_value": 0, **no_type}
    coll_offer = {**ok_offer, "collateral_value": 6_000_000, "collateral_type": "REAL_ESTATE",
                  "collateral_subtype": "WAREHOUSE"}

    def co(**kw):
        return {**company, **kw}

    def without(d, key):
        return {k: v for k, v in d.items() if k != key}

    def off(base=ok_offer, **kw):
        return {**base, **kw}

    A, O, X = "/approval", "/offers", "/alternative"
    return [
        ("контроль: /offers", O, {"company": company}, 200),
        ("контроль: /approval", A, {"company": company, "offer": ok_offer}, 200),
        ("контроль: /approval GOV_1764 micro", A, {"company": company, "offer": gov_offer}, 200),
        ("контроль: /alternative", X, {"company": company, "offer": ok_offer, "gamma": 0.9}, 200),
        ("контроль: /approval с залогом", A, {"company": company, "offer": coll_offer}, 200),
        ("нет поля company", O, {}, 422),
        ("в Company нет revenue_last_year", O, {"company": without(company, "revenue_last_year")}, 422),
        ("revenue_last_year = null", O, {"company": co(revenue_last_year=None)}, 422),
        ("company_age_months строкой", A, {"company": co(company_age_months="103"), "offer": ok_offer}, 422),
        ("флаг числом 1 вместо true", A, {"company": co(accounts_blocked_flag=1), "offer": ok_offer}, 422),
        ("legal_form = OOO", A, {"company": co(legal_form="OOO"), "offer": ok_offer}, 422),
        ("ИП с 10-значным ИНН", A, {"company": co(legal_form="IE"), "offer": ok_offer}, 422),
        ("нет поля offer", A, {"company": company}, 422),
        ("в Offer нет rate", A, {"company": company, "offer": without(ok_offer, "rate")}, 422),
        ("неизвестный product_type", A, {"company": company, "offer": off(product_type="MORTGAGE")}, 422),
        ("term_months=7 для WORKING_CAPITAL", A, {"company": company, "offer": off(term_months=7)}, 422),
        ("amount ниже минимума", A, {"company": company, "offer": off(amount=100_000)}, 422),
        ("amount дробный", A, {"company": company, "offer": off(amount=5_000_000.5)}, 422),
        ("rate вне коридора", A, {"company": company, "offer": off(rate=45.0)}, 422),
        ("rate с двумя знаками", A, {"company": company, "offer": off(rate=20.05)}, 422),
        ("залог у OVERDRAFT", A, {"company": company, "offer": off(
            product_type="OVERDRAFT", term_months=12, rate=21.5, collateral_value=1_000_000)}, 422),
        ("SECURED_RE: amount > 0.7 × залог", A, {"company": company, "offer": off(
            product_type="SECURED_RE", amount=10_000_000, term_months=60, rate=17.0,
            collateral_value=12_000_000)}, 422),
        ("SECURED_RE без залога", A, {"company": company, "offer": off(
            product_type="SECURED_RE", amount=10_000_000, term_months=60, rate=17.0)}, 422),
        ("GOV_1764 micro: сумма 20 млн", A, {"company": company, "offer": off(gov_offer, amount=20_000_000)}, 422),
        ("GOV_1764 micro: срок 60", A, {"company": company, "offer": off(gov_offer, term_months=60)}, 422),
        ("GOV_1764 micro: ставка 16.75", A, {"company": company, "offer": off(gov_offer, rate=16.75)}, 422),
        ("залог без вида", A, {"company": company, "offer": off(coll_offer, collateral_type=None,
                                                                collateral_subtype=None)}, 422),
        ("в Offer нет collateral_type", A, {"company": company, "offer": without(coll_offer, "collateral_type")}, 422),
        ("частный вид не из общего", A, {"company": company, "offer": off(coll_offer, collateral_subtype="TRUCK")}, 422),
        ("вид залога без залога", A, {"company": company, "offer": off(collateral_type="VEHICLES",
                                                                      collateral_subtype="CAR")}, 422),
        ("SECURED_RE под транспорт", A, {"company": company, "offer": off(
            product_type="SECURED_RE", amount=10_000_000, term_months=60, rate=17.0, collateral_value=20_000_000,
            collateral_type="VEHICLES", collateral_subtype="TRUCK")}, 422),
        ("/alternative: gamma = 1.5", X, {"company": company, "offer": ok_offer, "gamma": 1.5}, 422),
        ("/alternative: нет gamma", X, {"company": company, "offer": ok_offer}, 422),
    ]


def check_error(client, case):
    label, path, body, expected = case
    status, resp, ms = client.post(path, body)
    v = []
    if status != expected:
        v.append(f"HTTP {status}, ждали {expected}: {resp}")
    elif expected == 422:
        err = resp.get("error") if isinstance(resp, dict) else None
        if not (isinstance(err, dict) and err.get("code") == "VALIDATION_ERROR"
                and isinstance(err.get("message"), str)):
            v.append(f"формат ошибки не {{'error': {{'code': 'VALIDATION_ERROR', 'message': ...}}}}: {resp}")
    return record(label, path, body, status, resp, ms, v)


# --------------------------------------------------------------------------- #
# Запуск
# --------------------------------------------------------------------------- #
def build_cases(scenario, df, n, rng, gamma):
    if scenario == "errors":
        llc_micro = df[(df["legal_form"] == "LLC") & (df["msp_category"] == "micro")]
        return error_cases(company_from_row(llc_micro.iloc[0].to_dict()))
    if scenario == "offers":
        wanted = df.groupby("inn")["product_type"].agg(set)
        first = df.drop_duplicates("inn")
        rows = first.iloc[rng.choice(len(first), min(n, len(first)), replace=False)].to_dict("records")
        return [{"label": r["inn"], "company": company_from_row(r), "wanted": wanted[r["inn"]]} for r in rows]
    rows = df.iloc[rng.choice(len(df), min(n, len(df)), replace=False)].to_dict("records")
    cases = [{"label": f"{r['inn']} {r['product_type']}", "company": company_from_row(r),
              "offer": offer_from_row(r), "y": int(r["approved"])} for r in rows]
    if scenario == "alternative":
        for c in cases:
            c["gamma"] = gamma if gamma is not None else float(rng.choice(GAMMAS))
    return cases


SCENARIOS = {
    "offers": (check_offers, summary_offers),
    "approval": (check_approval, summary_approval),
    "alternative": (check_alternative, summary_alternative),
    "errors": (check_error, lambda recs: []),
}


def main():
    ap = argparse.ArgumentParser(description="Мок Backend: запросы к ML-сервису по API.md")
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="all")
    ap.add_argument("--n", type=int, default=300, help="запросов на сценарий (кроме errors)")
    ap.add_argument("--split", choices=["test", "train", "all"], default="test")
    ap.add_argument("--gamma", type=float, default=None, help=f"для /alternative; по умолчанию случайно из {GAMMAS}")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--show", type=int, default=5, help="сколько нарушений печатать на сценарий")
    ap.add_argument("--dump", default=None, help="JSONL со всеми запросами и ответами")
    args = ap.parse_args()

    df = load_applications()
    if args.split != "all":
        m = test_mask(df)
        df = df[m if args.split == "test" else ~m]
    rng = np.random.default_rng(args.seed)
    client = Client(args.url, args.timeout)

    try:
        client.post("/approval", {})
    except OSError as e:
        sys.exit(f"ML-сервис недоступен по {args.url}: {e}")

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    dump = open(args.dump, "w", encoding="utf-8") if args.dump else None
    total_bad = 0
    print(f"ML-сервис: {args.url}; данные: {args.split}, {df['inn'].nunique():,} компаний, {len(df):,} заявок")
    for name in names:
        check, summarize = SCENARIOS[name]
        cases = build_cases(name, df, args.n, rng, args.gamma)
        with ThreadPoolExecutor(args.workers) as ex:
            recs = list(ex.map(lambda c: check(client, c), cases))
        bad = [r for r in recs if r["violations"]]
        total_bad += len(bad)
        ms = np.array([r["ms"] for r in recs])
        print(f"\n== {name}: запросов {len(recs)}, без нарушений {len(recs) - len(bad)}, с нарушениями {len(bad)}; "
              f"время p50 {np.percentile(ms, 50):.0f} мс, p95 {np.percentile(ms, 95):.0f} мс")
        for line in summarize(recs):
            print(f"   {line}")
        for r in bad[:args.show]:
            print(f"   ✗ {r['label']}: {'; '.join(r['violations'][:3])}")
        if len(bad) > args.show:
            print(f"   … ещё {len(bad) - args.show}")
        if dump:
            for r in recs:
                dump.write(json.dumps({"scenario": name, **{k: v for k, v in r.items() if k != "wanted"}},
                                      ensure_ascii=False, default=str) + "\n")
    if dump:
        dump.close()
    print(f"\nИтого запросов с нарушениями контракта: {total_bad}")
    sys.exit(1 if total_bad else 0)


if __name__ == "__main__":
    main()
