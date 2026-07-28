# VEXTRO Database Table Map

## Purpose

This document maps each planned table to its module, priority and implementation phase.

---

## 1. Authentication and Authorization

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| users | Registered user accounts | P1 | Implemented |
| roles | Consumer, SME and Admin roles | P1 | Implemented |
| user_roles | Many-to-many user-role assignment | P1 | Implemented |
| refresh_tokens | Secure refresh-token sessions | P1 | Pending |

---

## 2. Product Catalog

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| categories | Product category hierarchy | P1 | Pending |
| brands | Standardized product brands | P1 | Pending |
| platforms | Daraz, PriceOye and future marketplaces | P1 | Pending |
| canonical_products | Unique real-world products | P1 | Pending |
| product_variants | RAM, storage, color and variant details | P1 | Pending |
| product_listings | Marketplace-specific listings | P1 | Pending |
| product_images | Canonical and listing images | P1 | Pending |
| sellers | Marketplace seller records | P1 | Pending |

---

## 3. Data Acquisition

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| scrape_runs | Data-collection run status and statistics | P1 | Pending |
| scrape_errors | Detailed collection failures | P1 | Pending |

---

## 4. Price Intelligence

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| price_observations | Historical listing prices | P1 | Pending |
| price_alerts | User-defined target-price alerts | P1 | Pending |
| price_forecasts | AI or statistical price predictions | P2 | Pending |
| market_anomalies | Unusual price or availability events | P2 | Pending |

---

## 5. Review Intelligence

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| raw_reviews | Original collected review data | P1 | Pending |
| sentiment_results | Positive, neutral and negative results | P1 | Pending |
| aspect_sentiments | Aspect-level review insights | P2 | Pending |
| review_summaries | Product-level review summaries | P2 | Pending |
| fake_review_results | Suspicious-review risk results | P3 | Pending |
| seller_trust_scores | Explainable seller trust results | P2 | Pending |

---

## 6. Personalization

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| user_events | Searches, views and clicks | P2 | Pending |
| user_preferences | User-selected interests and limits | P2 | Pending |
| watchlists | Tracked products | P1 | Pending |
| saved_comparisons | Saved comparison groups | P1 | Pending |
| saved_comparison_items | Listings inside a saved comparison | P1 | Pending |
| recommendation_results | Generated product recommendations | P2 | Pending |

---

## 7. SME Business Intelligence

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| organizations | SME business profiles | P2 | Pending |
| organization_users | Users belonging to an SME | P2 | Pending |
| business_products | SME-owned products and inventory | P2 | Pending |
| competitor_watchlists | Competitor listings monitored by SMEs | P2 | Pending |
| sales_imports | CSV sales-import metadata | P3 | Pending |
| sales_records | Imported historical sales | P3 | Pending |
| inventory_snapshots | Historical stock levels | P3 | Pending |
| demand_forecasts | Product-demand predictions | P3 | Pending |
| pricing_scenarios | Dynamic-price simulations | P3 | Pending |

---

## 8. Notifications and Reports

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| notifications | In-app user notifications | P1 | Pending |
| reports | Generated analytical reports | P2 | Pending |

---

## 9. Machine Learning and Operations

| Table | Purpose | Priority | Status |
|---|---|---:|---|
| model_versions | Active model and evaluation information | P1 | Pending |
| audit_logs | Sensitive administrator and SME actions | P2 | Pending |

---

# Table Count Summary

| Area | Planned Tables |
|---|---:|
| Authentication | 4 |
| Catalog | 8 |
| Data acquisition | 2 |
| Price intelligence | 4 |
| Review intelligence | 6 |
| Personalization | 6 |
| SME intelligence | 9 |
| Notifications and reporting | 2 |
| ML and operations | 2 |
| **Total planned** | **43** |

---

# Scope-Control Rule

All 43 tables will not be created immediately.

Tables shall be implemented only when their related feature enters active development.

The next planned tables are:

1. refresh_tokens
2. categories
3. brands
4. platforms
5. canonical_products
6. product_variants
7. product_listings
8. price_observations

---

# Data Ownership Rules

1. `vextro_app` owns the application database.
2. Every table shall use primary keys.
3. Relationships shall use foreign keys.
4. Important uniqueness rules shall use database constraints.
5. Historical records shall not be overwritten unnecessarily.
6. Delete behavior shall be explicitly defined.
7. Important queries shall receive appropriate indexes.
8. Sensitive values shall not be stored in plain text.
9. Every AI output shall reference a model version where applicable.
10. Every marketplace record shall retain platform attribution.
