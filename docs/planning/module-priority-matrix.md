# VEXTRO Module Priority Matrix

## Document Information

- Project: VEXTRO
- Version: 1.0
- Status: Development Baseline
- Purpose: Define implementation priority and prevent scope creep

---

## Priority Definitions

### P0 — Foundation

Technical foundation required before application features can operate.

### P1 — Must Have

The FYP cannot be considered complete without these modules working properly.

### P2 — Should Have

Important modules that strengthen the academic and practical value of VEXTRO.

### P3 — Prototype

Limited but demonstrable implementation is acceptable.

### P4 — Future Scope

Documented but not required for the primary final demonstration.

---

# P0 — Technical Foundation

| Module | Required Output | Current Status |
|---|---|---|
| GitHub repository | Version-controlled source code | Completed |
| Team collaboration | Collaborators and pull-request workflow | Completed |
| Branch protection | Main branch protection and reviews | Completed |
| FastAPI backend | Running backend and Swagger documentation | Completed |
| React frontend | Running frontend application | Completed |
| Frontend-backend connection | React calling FastAPI successfully | Completed |
| PostgreSQL database | Dedicated VEXTRO database | Completed |
| SQLAlchemy connection | Backend connected to PostgreSQL | Completed |
| Alembic migrations | Controlled schema migrations | Completed |
| Environment configuration | Secrets stored outside Git | Completed |
| Requirements documentation | Functional and non-functional requirements | In Progress |
| System architecture | Approved system design | Pending |
| ERD | Approved database relationships | Pending |
| API contract | Initial backend/frontend contract | Pending |

---

# P1 — Must-Have Core Modules

## 1. Authentication and Authorization

Required capabilities:

- User registration
- Login
- Logout
- Password hashing
- Access tokens
- Refresh tokens
- Consumer, SME and Admin roles
- Protected APIs
- Role-based permissions

Success condition:

A Consumer, SME and Admin user can log in and access only the resources permitted for their role.

---

## 2. Canonical Product Catalog

Required capabilities:

- Categories
- Brands
- Canonical products
- Product variants
- Platform listings
- Product specifications
- Product images

Success condition:

One real-world product can contain multiple marketplace listings without duplicating the canonical product.

---

## 3. Multi-Platform Data Acquisition

Required capabilities:

- Daraz product collector
- PriceOye product collector
- Product-data validation
- Collection timestamp
- Scraper-run logs
- Failure logging
- Saved HTML or dataset fallback

Success condition:

The system can collect or import supported product data from both platforms without crashing the main application.

---

## 4. Data Normalization and Product Matching

Required capabilities:

- Title cleaning
- Brand normalization
- Model extraction
- RAM and storage normalization
- Duplicate detection
- Product matching score
- Manual review for uncertain matches

Success condition:

Listings representing the same product and variant are grouped accurately.

---

## 5. Product Search and Filtering

Required capabilities:

- Search by product title
- Search by brand
- Search by model
- Category filter
- Price filter
- Platform filter
- Rating filter
- Availability filter
- Pagination and sorting

Success condition:

A user can find products quickly using practical search and filter options.

---

## 6. Cross-Platform Product Comparison

Required capabilities:

- Daraz and PriceOye prices
- Seller details
- Availability
- Rating
- Warranty
- Product specifications
- Lowest-price identification
- Marketplace URL

Success condition:

The user can understand which available listing provides the best value.

---

## 7. Historical Price Tracking

Required capabilities:

- Price observation storage
- Observation timestamp
- Minimum price
- Maximum price
- Average price
- Current price
- Price-history chart

Success condition:

The system can show how a product's price changed over time.

---

## 8. Price Alerts and Notifications

Required capabilities:

- Create target-price alert
- Activate/deactivate alert
- Delete alert
- Compare target with latest price
- In-app notification
- Read/unread notification status

Success condition:

The user receives a notification when the product price reaches the configured target.

---

## 9. Consumer Dashboard

Required capabilities:

- Tracked products
- Active alerts
- Recent price drops
- Saved comparisons
- Recommended products
- Buying guidance where data is sufficient

Success condition:

The Consumer dashboard provides a clear overview of shopping activity and market opportunities.

---

## 10. Review Sentiment Analysis

Required capabilities:

- Review storage
- Text preprocessing
- Positive classification
- Neutral classification
- Negative classification
- Sentiment percentages
- Evaluation metrics

Success condition:

The product page displays understandable review sentiment with documented model performance.

---

## 11. Administrator Dashboard

Required capabilities:

- User statistics
- Product statistics
- Listing statistics
- Scraper runs
- Scraper errors
- Pending product matches
- Model versions
- System health

Success condition:

The administrator can monitor and manage the core application.

---

# P2 — Should-Have Modules

## 1. Price Forecasting

- Baseline forecasting model
- ARIMA forecasting
- Historical vs predicted chart
- MAE, RMSE or MAPE
- Buy Now, Wait or Insufficient Data result

## 2. Content-Based Recommendations

- Product similarity
- Price-range similarity
- Specification similarity
- User watchlist signals
- Cold-start recommendations

## 3. Review Summarization

- Common positive feedback
- Common negative feedback
- Major product aspects
- Short readable summary

## 4. Seller Trust Score

- Seller rating
- Review count
- Negative-review ratio
- Listing consistency
- Explainable trust result

## 5. SME Competitor Monitoring

- SME business profile
- Business products
- Competitor watchlist
- Competitor pricing gap
- Pricing alerts
- Basic analytical report

## 6. CSV and Report Export

- CSV data export
- Product comparison report
- Competitor report
- Price-history report

---

# P3 — Prototype Modules

## 1. LSTM Price Forecasting

A limited comparison against the baseline or ARIMA model.

## 2. Fake Review Detection

A suspicious-review classifier with clear limitations.

## 3. Conversational Shopping Assistant

Database-grounded questions for search, comparison, prices and reviews.

## 4. Collaborative Recommendations

Prototype using limited interaction or synthetic academic data.

## 5. Demand Forecasting

Basic sales-demand prediction from imported SME sales data.

## 6. Inventory Recommendations

Low-stock and reorder-point suggestions.

## 7. Dynamic Pricing Advisor

Pricing-gap and margin-impact scenario simulation.

---

# P4 — Future Scope

- Additional marketplaces
- Additional countries and currencies
- Real-time streaming price updates
- Native mobile application
- Automated marketplace purchasing
- Enterprise ERP integrations
- Advanced market-share estimation
- Large-scale distributed scraping
- Commercial subscription and billing system

---

# Implementation Rule

Development shall follow this order:

1. P0 foundation
2. P1 core modules
3. P2 supporting modules
4. P3 prototypes
5. P4 future scope

A lower-priority feature shall not delay a higher-priority module.

---

# Final FYP Demonstration Priority

The final demonstration must successfully show:

1. User login
2. Product search
3. Product details
4. Daraz and PriceOye comparison
5. Price history
6. Review sentiment
7. Price alert
8. Consumer dashboard
9. SME competitor dashboard
10. Administrator monitoring