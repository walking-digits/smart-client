#!/usr/bin/env python3
"""Заглушка ML-сервиса: те же ручки и форматы, что в API.md, но без моделей.

Нужна, чтобы проверить мок-бэкенд и формат ответов, пока моделей нет, и как точка отсчёта для метрик.
Валидация настоящая (contract.py), прогнозы — константы:
    /approval    — доля одобрения продукта в мок-данных (dataset_meta.json);
    /offers      — типичное предложение по каталогу генератора, oftenhood — базовый вес спроса продукта;
    /alternative — исходное предложение, если оно проходит порог, иначе null.

    python mock/ml_stub.py --port 8000
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import generate_data as gd  # noqa: E402

from contract import (CATALOG, GOV_MICRO_MAX_AMOUNT, GOV_MICRO_MAX_TERM, GOV_RATE, PRODUCT_TYPES,  # noqa: E402
                      is_number, validate_company, validate_offer)

TYPICAL_LTV = 0.6  # SECURED_RE: залог = amount / 0.6, в пределах лимита 0.7
APPROVAL_RATE = json.loads((ROOT / "data" / "dataset_meta.json").read_text(encoding="utf-8"))[
    "approval_rate_by_product"]


class ValidationError(Exception):
    pass


def require(body, *keys):
    if not isinstance(body, dict):
        raise ValidationError("тело запроса должно быть объектом")
    missing = [k for k in keys if k not in body]
    if missing:
        raise ValidationError(f"нет поля: {', '.join(missing)}")


def check(errors):
    if errors:
        raise ValidationError("; ".join(errors))


def typical_offer(company, product):
    j = gd.P[product]
    rev = company["revenue_last_year"]
    micro = company["msp_category"] == "micro"
    lo, hi = CATALOG[product]["amount"]
    if product == "BUSINESS_CARD":
        base, hi = 300_000, min(hi, max(lo, 0.15 * rev))
    else:
        base = gd.AMT_RATIO[j] * max(rev, 1)
    gov_micro = product == "GOV_1764" and micro
    if gov_micro:
        hi = GOV_MICRO_MAX_AMOUNT
    amount = int(min(max(float(gd.round2(base)), lo), hi))
    term = int(gd.BASE_TERM[j])
    if gov_micro:
        term = min(term, GOV_MICRO_MAX_TERM)
    rate = GOV_RATE[company["msp_category"]] if product == "GOV_1764" else float(gd.BASE_RATE[j])
    collateral = int(gd.ceil2(amount / TYPICAL_LTV)) if product == "SECURED_RE" else 0
    return {"product_type": product, "amount": amount, "term_months": term, "rate": rate,
            "collateral_value": collateral}


def approval_probability(company, offer):
    return APPROVAL_RATE[offer["product_type"]]


def handle_offers(body):
    require(body, "company")
    company = body["company"]
    check(validate_company(company))
    offers = [{"offer": typical_offer(company, p), "oftenhood": round(float(gd.PRODUCT_W[gd.P[p]]), 4)}
              for p in PRODUCT_TYPES]
    offers.sort(key=lambda o: -o["oftenhood"])
    return {"offers": offers}


def parse_company_offer(body, *extra):
    require(body, "company", "offer", *extra)
    company, offer = body["company"], body["offer"]
    check(validate_company(company))
    check(validate_offer(offer, company["msp_category"]))
    return company, offer


def handle_approval(body):
    company, offer = parse_company_offer(body)
    return {"approval_probability": approval_probability(company, offer)}


def handle_alternative(body):
    company, offer = parse_company_offer(body, "gamma")
    gamma = body["gamma"]
    if not (is_number(gamma) and 0 <= gamma <= 1):
        raise ValidationError(f"gamma={gamma!r}: нужно число 0…1")
    p = approval_probability(company, offer)
    if p > gamma:
        return {"source_approval_probability": p, "offer": offer, "likelyhood": 1.0, "approval_probability": p}
    return {"source_approval_probability": p, "offer": None, "likelyhood": None, "approval_probability": None}


ROUTES = {"/offers": handle_offers, "/approval": handle_approval, "/alternative": handle_alternative}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        route = ROUTES.get(self.path)
        if route is None:
            return self.reply(404, {"error": {"code": "NOT_FOUND", "message": f"нет ручки {self.path}"}})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null")
            self.reply(200, route(body))
        except (ValidationError, ValueError) as e:
            self.reply(422, {"error": {"code": "VALIDATION_ERROR", "message": str(e)}})
        except Exception:
            traceback.print_exc()
            self.reply(500, {"error": {"code": "INTERNAL_ERROR", "message": "внутренняя ошибка"}})

    def reply(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description="Заглушка ML-сервиса (API.md)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    print(f"Заглушка ML-сервиса: http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
