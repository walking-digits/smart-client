# Тренировочные запросы к ML-сервисам

5 тренировочных пользователей и запросы к ручкам: `/offers` — по одному на пользователя,
`/approval` и `/alternative` — по 10. Формат — [API.md](API.md). Перед запросами запустить оба
контейнера ([README.md](README.md)); каждую команду можно скопировать в терминал как есть.

## Пользователи

| Пользователь | ИНН | Кто |
|---|---|---|
| `IP_TRADE` | 520892877806 | ИП, торговля, выручка 13.8 млн, кредитная история без просрочек |
| `LLC_BUILD` | 5005243165 | ООО micro, строительство, выручка 52 млн, прибыльное |
| `LLC_MANUF` | 2354526588 | ООО small, производство, выручка 320 млн, работает 13 мес. |
| `LLC_TRANS` | 4337532384 | ООО medium, транспорт, выручка 2 млрд |
| `LLC_RISKY` | 2300783148 | ООО micro, торговля, выручка 13.4 млн: налоговый долг, просрочка 42 дня, долг у приставов |

## `POST /offers`

**1. ИП, торговля** (`IP_TRADE`)

```bash
curl -X POST localhost:8000/offers -H 'Content-Type: application/json' -d '{"company": {"inn": "520892877806", "legal_form": "IE", "company_age_months": 63, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13831730, "revenue_growth_yoy": null, "net_margin": null, "equity_ratio": null, "current_ratio": null, "debt_to_revenue": null, "taxes_paid_last_year": 168463, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2947713, "bki_max_dpd_12m": 0}}'
```

**2. ООО, стройка** (`LLC_BUILD`)

```bash
curl -X POST localhost:8000/offers -H 'Content-Type: application/json' -d '{"company": {"inn": "5005243165", "legal_form": "LLC", "company_age_months": 190, "okved_section": "F", "msp_category": "micro", "revenue_last_year": 51563357, "revenue_growth_yoy": -0.291, "net_margin": 0.098, "equity_ratio": 0.143, "current_ratio": 1.07, "debt_to_revenue": 0.069, "taxes_paid_last_year": 901964, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}}'
```

**3. ООО, производство** (`LLC_MANUF`)

```bash
curl -X POST localhost:8000/offers -H 'Content-Type: application/json' -d '{"company": {"inn": "2354526588", "legal_form": "LLC", "company_age_months": 13, "okved_section": "C", "msp_category": "small", "revenue_last_year": 320387991, "revenue_growth_yoy": -0.168, "net_margin": 0.073, "equity_ratio": 0.422, "current_ratio": 0.763, "debt_to_revenue": 0.054, "taxes_paid_last_year": 15806788, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}}'
```

**4. ООО, транспорт** (`LLC_TRANS`)

```bash
curl -X POST localhost:8000/offers -H 'Content-Type: application/json' -d '{"company": {"inn": "4337532384", "legal_form": "LLC", "company_age_months": 38, "okved_section": "H", "msp_category": "medium", "revenue_last_year": 2000000000, "revenue_growth_yoy": 0.36, "net_margin": 0.036, "equity_ratio": 0.094, "current_ratio": 0.363, "debt_to_revenue": 0.0, "taxes_paid_last_year": 60524032, "tax_arrears_amount": 107695, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 28126022, "bki_total_debt": 26904067, "bki_max_dpd_12m": 0}}'
```

**5. ООО, рискованное** (`LLC_RISKY`)

```bash
curl -X POST localhost:8000/offers -H 'Content-Type: application/json' -d '{"company": {"inn": "2300783148", "legal_form": "LLC", "company_age_months": 99, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13358585, "revenue_growth_yoy": 0.287, "net_margin": 0.104, "equity_ratio": 0.575, "current_ratio": 2.505, "debt_to_revenue": 0.124, "taxes_paid_last_year": 609263, "tax_arrears_amount": 100177, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 95898, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2282570, "bki_max_dpd_12m": 42}}'
```

## `POST /approval`

**1. ИП: экспресс-кредит 1.5 млн на 12 мес.** (`IP_TRADE`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "520892877806", "legal_form": "IE", "company_age_months": 63, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13831730, "revenue_growth_yoy": null, "net_margin": null, "equity_ratio": null, "current_ratio": null, "debt_to_revenue": null, "taxes_paid_last_year": 168463, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2947713, "bki_max_dpd_12m": 0}, "offer": {"product_type": "EXPRESS_UNSECURED", "amount": 1500000, "term_months": 12, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
```

**2. ИП: бизнес-карта 300 тыс.** (`IP_TRADE`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "520892877806", "legal_form": "IE", "company_age_months": 63, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13831730, "revenue_growth_yoy": null, "net_margin": null, "equity_ratio": null, "current_ratio": null, "debt_to_revenue": null, "taxes_paid_last_year": 168463, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2947713, "bki_max_dpd_12m": 0}, "offer": {"product_type": "BUSINESS_CARD", "amount": 300000, "term_months": 36, "rate": 25.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
```

**3. стройка: оборотный 10 млн под спецтехнику** (`LLC_BUILD`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "5005243165", "legal_form": "LLC", "company_age_months": 190, "okved_section": "F", "msp_category": "micro", "revenue_last_year": 51563357, "revenue_growth_yoy": -0.291, "net_margin": 0.098, "equity_ratio": 0.143, "current_ratio": 1.07, "debt_to_revenue": 0.069, "taxes_paid_last_year": 901964, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "WORKING_CAPITAL", "amount": 10000000, "term_months": 24, "rate": 20.0, "collateral_value": 12000000, "collateral_type": "VEHICLES", "collateral_subtype": "SPECIAL_MACHINERY"}}'
```

**4. стройка: льготный 1764, 8 млн под склад** (`LLC_BUILD`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "5005243165", "legal_form": "LLC", "company_age_months": 190, "okved_section": "F", "msp_category": "micro", "revenue_last_year": 51563357, "revenue_growth_yoy": -0.291, "net_margin": 0.098, "equity_ratio": 0.143, "current_ratio": 1.07, "debt_to_revenue": 0.069, "taxes_paid_last_year": 901964, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "GOV_1764", "amount": 8000000, "term_months": 36, "rate": 17.5, "collateral_value": 9000000, "collateral_type": "REAL_ESTATE", "collateral_subtype": "WAREHOUSE"}}'
```

**5. производство: инвест 100 млн под оборудование** (`LLC_MANUF`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "2354526588", "legal_form": "LLC", "company_age_months": 13, "okved_section": "C", "msp_category": "small", "revenue_last_year": 320387991, "revenue_growth_yoy": -0.168, "net_margin": 0.073, "equity_ratio": 0.422, "current_ratio": 0.763, "debt_to_revenue": 0.054, "taxes_paid_last_year": 15806788, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "INVESTMENT", "amount": 100000000, "term_months": 60, "rate": 18.0, "collateral_value": 110000000, "collateral_type": "EQUIPMENT", "collateral_subtype": "PRODUCTION_EQUIPMENT"}}'
```

**6. производство: кредитная линия 40 млн под сырьё** (`LLC_MANUF`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "2354526588", "legal_form": "LLC", "company_age_months": 13, "okved_section": "C", "msp_category": "small", "revenue_last_year": 320387991, "revenue_growth_yoy": -0.168, "net_margin": 0.073, "equity_ratio": 0.422, "current_ratio": 0.763, "debt_to_revenue": 0.054, "taxes_paid_last_year": 15806788, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "CREDIT_LINE_REV", "amount": 40000000, "term_months": 18, "rate": 20.0, "collateral_value": 45000000, "collateral_type": "INVENTORY", "collateral_subtype": "RAW_MATERIALS"}}'
```

**7. транспорт: под залог склада 100 млн** (`LLC_TRANS`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "4337532384", "legal_form": "LLC", "company_age_months": 38, "okved_section": "H", "msp_category": "medium", "revenue_last_year": 2000000000, "revenue_growth_yoy": 0.36, "net_margin": 0.036, "equity_ratio": 0.094, "current_ratio": 0.363, "debt_to_revenue": 0.0, "taxes_paid_last_year": 60524032, "tax_arrears_amount": 107695, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 28126022, "bki_total_debt": 26904067, "bki_max_dpd_12m": 0}, "offer": {"product_type": "SECURED_RE", "amount": 100000000, "term_months": 120, "rate": 17.0, "collateral_value": 150000000, "collateral_type": "REAL_ESTATE", "collateral_subtype": "WAREHOUSE"}}'
```

**8. рискованное: оборотный 3 млн без залога** (`LLC_RISKY`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "2300783148", "legal_form": "LLC", "company_age_months": 99, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13358585, "revenue_growth_yoy": 0.287, "net_margin": 0.104, "equity_ratio": 0.575, "current_ratio": 2.505, "debt_to_revenue": 0.124, "taxes_paid_last_year": 609263, "tax_arrears_amount": 100177, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 95898, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2282570, "bki_max_dpd_12m": 42}, "offer": {"product_type": "WORKING_CAPITAL", "amount": 3000000, "term_months": 12, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
```

**9. производство: лизинг 20 млн на 36 мес.** (`LLC_MANUF`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "2354526588", "legal_form": "LLC", "company_age_months": 13, "okved_section": "C", "msp_category": "small", "revenue_last_year": 320387991, "revenue_growth_yoy": -0.168, "net_margin": 0.073, "equity_ratio": 0.422, "current_ratio": 0.763, "debt_to_revenue": 0.054, "taxes_paid_last_year": 15806788, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "LEASING", "amount": 20000000, "term_months": 36, "rate": 12.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
```

**10. транспорт: факторинг 300 млн** (`LLC_TRANS`)

```bash
curl -X POST localhost:8001/approval -H 'Content-Type: application/json' -d '{"company": {"inn": "4337532384", "legal_form": "LLC", "company_age_months": 38, "okved_section": "H", "msp_category": "medium", "revenue_last_year": 2000000000, "revenue_growth_yoy": 0.36, "net_margin": 0.036, "equity_ratio": 0.094, "current_ratio": 0.363, "debt_to_revenue": 0.0, "taxes_paid_last_year": 60524032, "tax_arrears_amount": 107695, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 28126022, "bki_total_debt": 26904067, "bki_max_dpd_12m": 0}, "offer": {"product_type": "FACTORING", "amount": 300000000, "term_months": 6, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}}'
```

## `POST /alternative`

**1. ИП: экспресс 4 млн, порог 0.7** (`IP_TRADE`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "520892877806", "legal_form": "IE", "company_age_months": 63, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13831730, "revenue_growth_yoy": null, "net_margin": null, "equity_ratio": null, "current_ratio": null, "debt_to_revenue": null, "taxes_paid_last_year": 168463, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2947713, "bki_max_dpd_12m": 0}, "offer": {"product_type": "EXPRESS_UNSECURED", "amount": 4000000, "term_months": 12, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.7}'
```

**2. ИП: бизнес-карта, порог 0.5** (`IP_TRADE`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "520892877806", "legal_form": "IE", "company_age_months": 63, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13831730, "revenue_growth_yoy": null, "net_margin": null, "equity_ratio": null, "current_ratio": null, "debt_to_revenue": null, "taxes_paid_last_year": 168463, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2947713, "bki_max_dpd_12m": 0}, "offer": {"product_type": "BUSINESS_CARD", "amount": 300000, "term_months": 36, "rate": 25.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.5}'
```

**3. стройка: оборотный 30 млн без залога, порог 0.7** (`LLC_BUILD`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "5005243165", "legal_form": "LLC", "company_age_months": 190, "okved_section": "F", "msp_category": "micro", "revenue_last_year": 51563357, "revenue_growth_yoy": -0.291, "net_margin": 0.098, "equity_ratio": 0.143, "current_ratio": 1.07, "debt_to_revenue": 0.069, "taxes_paid_last_year": 901964, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "WORKING_CAPITAL", "amount": 30000000, "term_months": 12, "rate": 20.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.7}'
```

**4. производство: инвест 250 млн под оборудование, порог 0.8** (`LLC_MANUF`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "2354526588", "legal_form": "LLC", "company_age_months": 13, "okved_section": "C", "msp_category": "small", "revenue_last_year": 320387991, "revenue_growth_yoy": -0.168, "net_margin": 0.073, "equity_ratio": 0.422, "current_ratio": 0.763, "debt_to_revenue": 0.054, "taxes_paid_last_year": 15806788, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "INVESTMENT", "amount": 250000000, "term_months": 60, "rate": 18.0, "collateral_value": 100000000, "collateral_type": "EQUIPMENT", "collateral_subtype": "PRODUCTION_EQUIPMENT"}, "gamma": 0.8}'
```

**5. транспорт: под залог офиса 140 млн, порог 0.9** (`LLC_TRANS`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "4337532384", "legal_form": "LLC", "company_age_months": 38, "okved_section": "H", "msp_category": "medium", "revenue_last_year": 2000000000, "revenue_growth_yoy": 0.36, "net_margin": 0.036, "equity_ratio": 0.094, "current_ratio": 0.363, "debt_to_revenue": 0.0, "taxes_paid_last_year": 60524032, "tax_arrears_amount": 107695, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 28126022, "bki_total_debt": 26904067, "bki_max_dpd_12m": 0}, "offer": {"product_type": "SECURED_RE", "amount": 140000000, "term_months": 36, "rate": 17.0, "collateral_value": 200000000, "collateral_type": "REAL_ESTATE", "collateral_subtype": "OFFICE"}, "gamma": 0.9}'
```

**6. транспорт: факторинг 300 млн, порог 0.7** (`LLC_TRANS`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "4337532384", "legal_form": "LLC", "company_age_months": 38, "okved_section": "H", "msp_category": "medium", "revenue_last_year": 2000000000, "revenue_growth_yoy": 0.36, "net_margin": 0.036, "equity_ratio": 0.094, "current_ratio": 0.363, "debt_to_revenue": 0.0, "taxes_paid_last_year": 60524032, "tax_arrears_amount": 107695, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 28126022, "bki_total_debt": 26904067, "bki_max_dpd_12m": 0}, "offer": {"product_type": "FACTORING", "amount": 300000000, "term_months": 6, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.7}'
```

**7. рискованное: оборотный 6 млн, порог 0.6** (`LLC_RISKY`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "2300783148", "legal_form": "LLC", "company_age_months": 99, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13358585, "revenue_growth_yoy": 0.287, "net_margin": 0.104, "equity_ratio": 0.575, "current_ratio": 2.505, "debt_to_revenue": 0.124, "taxes_paid_last_year": 609263, "tax_arrears_amount": 100177, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 95898, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2282570, "bki_max_dpd_12m": 42}, "offer": {"product_type": "WORKING_CAPITAL", "amount": 6000000, "term_months": 24, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.6}'
```

**8. рискованное: экспресс 5 млн, порог 0.95** (`LLC_RISKY`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "2300783148", "legal_form": "LLC", "company_age_months": 99, "okved_section": "G", "msp_category": "micro", "revenue_last_year": 13358585, "revenue_growth_yoy": 0.287, "net_margin": 0.104, "equity_ratio": 0.575, "current_ratio": 2.505, "debt_to_revenue": 0.124, "taxes_paid_last_year": 609263, "tax_arrears_amount": 100177, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 95898, "arbitr_defendant_amount_12m": 0, "bki_total_debt": 2282570, "bki_max_dpd_12m": 42}, "offer": {"product_type": "EXPRESS_UNSECURED", "amount": 5000000, "term_months": 36, "rate": 24.0, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.95}'
```

**9. стройка: льготный 1764, 10 млн без залога, порог 0.85** (`LLC_BUILD`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "5005243165", "legal_form": "LLC", "company_age_months": 190, "okved_section": "F", "msp_category": "micro", "revenue_last_year": 51563357, "revenue_growth_yoy": -0.291, "net_margin": 0.098, "equity_ratio": 0.143, "current_ratio": 1.07, "debt_to_revenue": 0.069, "taxes_paid_last_year": 901964, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "GOV_1764", "amount": 10000000, "term_months": 36, "rate": 17.5, "collateral_value": 0, "collateral_type": null, "collateral_subtype": null}, "gamma": 0.85}'
```

**10. производство: кредитная линия 60 млн под сырьё, порог 0.8** (`LLC_MANUF`)

```bash
curl -X POST localhost:8001/alternative -H 'Content-Type: application/json' -d '{"company": {"inn": "2354526588", "legal_form": "LLC", "company_age_months": 13, "okved_section": "C", "msp_category": "small", "revenue_last_year": 320387991, "revenue_growth_yoy": -0.168, "net_margin": 0.073, "equity_ratio": 0.422, "current_ratio": 0.763, "debt_to_revenue": 0.054, "taxes_paid_last_year": 15806788, "tax_arrears_amount": 0, "accounts_blocked_flag": false, "registry_risk_flag": false, "bankruptcy_flag": false, "fssp_open_amount": 0, "arbitr_defendant_amount_12m": 0, "bki_total_debt": null, "bki_max_dpd_12m": null}, "offer": {"product_type": "CREDIT_LINE_REV", "amount": 60000000, "term_months": 36, "rate": 20.0, "collateral_value": 45000000, "collateral_type": "INVENTORY", "collateral_subtype": "RAW_MATERIALS"}, "gamma": 0.8}'
```
