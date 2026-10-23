#!/usr/bin/env bash
# Тренировочные запросы к ML-сервисам (API.md): 5 пользователей, запросы ко всем ручкам: /offers — по одному на пользователя, /approval и /alternative — по 10.
# Сначала запустить оба контейнера (README.md). Отправить всё: bash examples.sh
# Один запрос: вставить в терминал блок «Пользователи», функцию post и нужную строку post.

M1=localhost:8000   # model1: /offers
M2=localhost:8001   # model2: /approval, /alternative

post() {  # post <адрес> <описание> <тело запроса>
  echo "== $1 — $2"
  curl -s -X POST "$1" -H "Content-Type: application/json" -d "$3"
  echo; echo
}

# ---- Пользователи (объект Company) ----
# ИП, торговля, выручка 13.8 млн, кредитная история без просрочек
IP_TRADE='{"inn": "520892877806", "legal_form": "IE", "company_age_months": 63, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13831730, "revenue_growth_yoy": null, "net_margin": null, "equity_ratio": null, "current_ratio": null, "debt_to_revenue": null, "taxes_paid_last_year": 168463, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2947713, "bki_max_dpd_12m": 0}'
# ООО micro, строительство, выручка 52 млн, прибыльное
LLC_BUILD='{"inn": "5005243165", "legal_form": "LLC", "company_age_months": 190, "okved_section": "F", "msp_category": "micro", "revenue_last_year": 51563357, "revenue_growth_yoy": -0.291, "net_margin": 0.098, "equity_ratio": 0.143, "current_ratio": 1.07, "debt_to_revenue": 0.069, "taxes_paid_last_year": 901964, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}'
# ООО small, производство, выручка 320 млн, работает 13 мес.
LLC_MANUF='{"inn": "2354526588", "legal_form": "LLC", "company_age_months": 13, "okved_section": "C", "msp_category": "small", "revenue_last_year": 320387991, "revenue_growth_yoy": -0.168, "net_margin": 0.073, "equity_ratio": 0.422, "current_ratio": 0.763, "debt_to_revenue": 0.054, "taxes_paid_last_year": 15806788, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}'
# ООО medium, транспорт, выручка 2 млрд
LLC_TRANS='{"inn": "4337532384", "legal_form": "LLC", "company_age_months": 38, "okved_section": "H", "msp_category": "medium", "revenue_last_year": 2000000000, "revenue_growth_yoy": 0.36, "net_margin": 0.036, "equity_ratio": 0.094, "current_ratio": 0.363, "debt_to_revenue": 0.0, "taxes_paid_last_year": 60524032, "tax_arrears_amount": 107695, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 28126022, "bki_total_debt": 26904067, "bki_max_dpd_12m": 0}'
# ООО micro, торговля, выручка 13.4 млн: налоговый долг, просрочка 42 дня, долг у приставов
LLC_RISKY='{"inn": "2300783148", "legal_form": "LLC", "company_age_months": 99, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13358585, "revenue_growth_yoy": 0.287, "net_margin": 0.104, "equity_ratio": 0.575, "current_ratio": 2.505, "debt_to_revenue": 0.124, "taxes_paid_last_year": 609263, "tax_arrears_amount": 100177, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 95898, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2282570, "bki_max_dpd_12m": 42}'

# ---- /offers ----
post $M1/offers "ИП, торговля" '{"company": '"$IP_TRADE"'}'
post $M1/offers "ООО, стройка" '{"company": '"$LLC_BUILD"'}'
post $M1/offers "ООО, производство" '{"company": '"$LLC_MANUF"'}'
post $M1/offers "ООО, транспорт" '{"company": '"$LLC_TRANS"'}'
post $M1/offers "ООО, рискованное" '{"company": '"$LLC_RISKY"'}'

# ---- /approval ----
post $M2/approval "ИП: экспресс-кредит 1.5 млн на 12 мес." '{"company": '"$IP_TRADE"', "offer": {"product_type": "EXPRESS_UNSECURED", "amount": 1500000, "term_months": 12, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
post $M2/approval "ИП: бизнес-карта 300 тыс." '{"company": '"$IP_TRADE"', "offer": {"product_type": "BUSINESS_CARD", "amount": 300000, "term_months": 36, "rate": 25.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
post $M2/approval "стройка: оборотный 10 млн под спецтехнику" '{"company": '"$LLC_BUILD"', "offer": {"product_type": "WORKING_CAPITAL", "amount": 10000000, "term_months": 24, "rate": 20.0, "collateral_value": 12000000, "collateral_type": "VEHICLES", "collateral_subtype": "SPECIAL_MACHINERY"}}'
post $M2/approval "стройка: льготный 1764, 8 млн под склад" '{"company": '"$LLC_BUILD"', "offer": {"product_type": "GOV_1764", "amount": 8000000, "term_months": 36, "rate": 17.5, "collateral_value": 9000000, "collateral_type": "REAL_ESTATE", "collateral_subtype": "WAREHOUSE"}}'
post $M2/approval "производство: инвест 100 млн под оборудование" '{"company": '"$LLC_MANUF"', "offer": {"product_type": "INVESTMENT", "amount": 100000000, "term_months": 60, "rate": 18.0, "collateral_value": 110000000, "collateral_type": "EQUIPMENT", "collateral_subtype": "PRODUCTION_EQUIPMENT"}}'
post $M2/approval "производство: кредитная линия 40 млн под сырьё" '{"company": '"$LLC_MANUF"', "offer": {"product_type": "CREDIT_LINE_REV", "amount": 40000000, "term_months": 18, "rate": 20.0, "collateral_value": 45000000, "collateral_type": "INVENTORY", "collateral_subtype": "RAW_MATERIALS"}}'
post $M2/approval "транспорт: под залог склада 100 млн" '{"company": '"$LLC_TRANS"', "offer": {"product_type": "SECURED_RE", "amount": 100000000, "term_months": 120, "rate": 17.0, "collateral_value": 150000000, "collateral_type": "REAL_ESTATE", "collateral_subtype": "WAREHOUSE"}}'
post $M2/approval "рискованное: оборотный 3 млн без залога" '{"company": '"$LLC_RISKY"', "offer": {"product_type": "WORKING_CAPITAL", "amount": 3000000, "term_months": 12, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
post $M2/approval "производство: лизинг 20 млн на 36 мес." '{"company": '"$LLC_MANUF"', "offer": {"product_type": "LEASING", "amount": 20000000, "term_months": 36, "rate": 12.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
post $M2/approval "транспорт: факторинг 300 млн" '{"company": '"$LLC_TRANS"', "offer": {"product_type": "FACTORING", "amount": 300000000, "term_months": 6, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'

# ---- /alternative ----
post $M2/alternative "ИП: экспресс 4 млн, порог 0.7" '{"company": '"$IP_TRADE"', "offer": {"product_type": "EXPRESS_UNSECURED", "amount": 4000000, "term_months": 12, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.7}'
post $M2/alternative "ИП: бизнес-карта, порог 0.5" '{"company": '"$IP_TRADE"', "offer": {"product_type": "BUSINESS_CARD", "amount": 300000, "term_months": 36, "rate": 25.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.5}'
post $M2/alternative "стройка: оборотный 30 млн без залога, порог 0.7" '{"company": '"$LLC_BUILD"', "offer": {"product_type": "WORKING_CAPITAL", "amount": 30000000, "term_months": 12, "rate": 20.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.7}'
post $M2/alternative "производство: инвест 250 млн под оборудование, порог 0.8" '{"company": '"$LLC_MANUF"', "offer": {"product_type": "INVESTMENT", "amount": 250000000, "term_months": 60, "rate": 18.0, "collateral_value": 100000000, "collateral_type": "EQUIPMENT", "collateral_subtype": "PRODUCTION_EQUIPMENT"}, "gamma": 0.8}'
post $M2/alternative "транспорт: под залог офиса 140 млн, порог 0.9" '{"company": '"$LLC_TRANS"', "offer": {"product_type": "SECURED_RE", "amount": 140000000, "term_months": 36, "rate": 17.0, "collateral_value": 200000000, "collateral_type": "REAL_ESTATE", "collateral_subtype": "OFFICE"}, "gamma": 0.9}'
post $M2/alternative "транспорт: факторинг 300 млн, порог 0.7" '{"company": '"$LLC_TRANS"', "offer": {"product_type": "FACTORING", "amount": 300000000, "term_months": 6, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.7}'
post $M2/alternative "рискованное: оборотный 6 млн, порог 0.6" '{"company": '"$LLC_RISKY"', "offer": {"product_type": "WORKING_CAPITAL", "amount": 6000000, "term_months": 24, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.6}'
post $M2/alternative "рискованное: экспресс 5 млн, порог 0.95" '{"company": '"$LLC_RISKY"', "offer": {"product_type": "EXPRESS_UNSECURED", "amount": 5000000, "term_months": 36, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.95}'
post $M2/alternative "стройка: льготный 1764, 10 млн без залога, порог 0.85" '{"company": '"$LLC_BUILD"', "offer": {"product_type": "GOV_1764", "amount": 10000000, "term_months": 36, "rate": 17.5, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.85}'
post $M2/alternative "производство: кредитная линия 60 млн под сырьё, порог 0.8" '{"company": '"$LLC_MANUF"', "offer": {"product_type": "CREDIT_LINE_REV", "amount": 60000000, "term_months": 36, "rate": 20.0, "collateral_value": 45000000, "collateral_type": "INVENTORY", "collateral_subtype": "RAW_MATERIALS"}, "gamma": 0.8}'
