# VEXTRO Functional Requirements

## Document Information

- Project: VEXTRO
- System: AI-Powered Multi-Platform E-Commerce Market Intelligence and Decision Support System
- Version: 1.0
- Status: Initial Development Baseline

---

## 1. User Roles

VEXTRO shall support the following roles:

1. Consumer
2. / Business Us SMEer
3. Administrator

---

## 2. Authentication and Authorization

### FR-AUTH-01

The system shall allow a new user to register an account.

### FR-AUTH-02

The system shall allow registered users to log in using their email and password.

### FR-AUTH-03

The system shall allow authenticated users to log out.

### FR-AUTH-04

The system shall provide role-based access for Consumer, SME and Administrator users.

### FR-AUTH-05

The system shall prevent unauthorized users from accessing protected pages and APIs.

### FR-AUTH-06

The system shall allow users to view and update their profiles.

---

## 3. Product Data Acquisition

### FR-DATA-01

The system shall collect publicly accessible product data from supported e-commerce platforms.

### FR-DATA-02

The initial supported platforms shall include Daraz and PriceOye.

### FR-DATA-03

The system shall collect product title, price, platform, seller, availability, rating, review count and product URL where available.

### FR-DATA-04

The system shall record the date and time of every data collection run.

### FR-DATA-05

The system shall log failed data-collection attempts.

### FR-DATA-06

The administrator shall be able to view data-acquisition runs and errors.

---

## 4. Product Processing and Normalization

### FR-NORM-01

The system shall clean product titles before matching and comparison.

### FR-NORM-02

The system shall normalize product brand, model, RAM, storage and other supported specifications.

### FR-NORM-03

The system shall identify duplicate listings.

### FR-NORM-04

The system shall group matching platform listings under one canonical product.

### FR-NORM-05

The system shall assign a matching confidence score to possible product matches.

### FR-NORM-06

The administrator shall be able to approve or reject uncertain product matches.

---

## 5. Product Search and Discovery

### FR-SEARCH-01

The user shall be able to search products by title, brand or model.

### FR-SEARCH-02

The system shall allow filtering by category, price range, platform, rating and availability.

### FR-SEARCH-03

The system shall display paginated search results.

### FR-SEARCH-04

The system shall allow users to sort results by relevance, lowest price, highest rating and recent update.

### FR-SEARCH-05

The system shall display available platform prices on product cards.

---

## 6. Product Comparison

### FR-COMP-01

The user shall be able to view listings of the same product from multiple platforms.

### FR-COMP-02

The comparison shall display price, seller, availability, rating, warranty and platform.

### FR-COMP-03

The system shall identify the lowest available price.

### FR-COMP-04

The system shall allow users to select listings for detailed comparison.

### FR-COMP-05

The system shall provide a direct link to the original marketplace listing.

---

## 7. Price History and Alerts

### FR-PRICE-01

The system shall store each observed product price as a historical record.

### FR-PRICE-02

The user shall be able to view price history for supported products.

### FR-PRICE-03

The system shall show minimum, maximum, average and current price.

### FR-PRICE-04

The user shall be able to create a target-price alert.

### FR-PRICE-05

The user shall be able to activate, deactivate and delete alerts.

### FR-PRICE-06

The system shall generate a notification when the observed price reaches the user's target.

---

## 8. Review and Sentiment Intelligence

### FR-REV-01

The system shall store supported publicly available product reviews.

### FR-REV-02

The system shall classify reviews as positive, neutral or negative.

### FR-REV-03

The system shall display overall sentiment distribution.

### FR-REV-04

The system shall identify sentiment related to supported aspects such as quality, delivery, durability, battery and performance.

### FR-REV-05

The system shall generate a summarized overview of customer feedback.

---

## 9. Price Forecasting

### FR-FORECAST-01

The system shall use historical price data to generate a future price forecast.

### FR-FORECAST-02

The system shall display historical and predicted prices on a chart.

### FR-FORECAST-03

The system shall provide a Buy Now, Wait or Insufficient Data recommendation.

### FR-FORECAST-04

The system shall display the model confidence or forecast limitations.

### FR-FORECAST-05

The administrator shall be able to view the active forecasting-model version.

---

## 10. Personalization and Recommendations

### FR-REC-01

The system shall track supported user interactions such as product views, searches and watchlist activity.

### FR-REC-02

The system shall recommend similar products based on product characteristics.

### FR-REC-03

The system shall provide initial recommendations for new users using selected interests and popular products.

### FR-REC-04

The user shall be able to add and remove products from a watchlist.

---

## 11. Consumer Dashboard

### FR-CONS-01

The consumer dashboard shall display tracked products.

### FR-CONS-02

The consumer dashboard shall display active alerts and recent price drops.

### FR-CONS-03

The dashboard shall display saved comparisons and recommended products.

### FR-CONS-04

The dashboard shall display AI-generated buying guidance where sufficient data is available.

---

## 12. SME Business Intelligence

### FR-SME-01

The system shall allow an SME user to create or manage a business profile.

### FR-SME-02

The SME user shall be able to add business products and SKUs.

### FR-SME-03

The system shall allow SME users to monitor competitor listings.

### FR-SME-04

The system shall calculate competitor pricing gaps.

### FR-SME-05

The system shall display products that are priced above or below the observed market average.

### FR-SME-06

The SME user shall be able to import historical sales data using a supported CSV format.

### FR-SME-07

The system shall generate a basic product-demand forecast.

### FR-SME-08

The system shall provide reorder-point or low-stock recommendations.

### FR-SME-09

The system shall provide a pricing simulation showing the expected effect of a price change on revenue and margin.

### FR-SME-10

The SME user shall be able to export supported reports.

---

## 13. Fake Review and Seller Trust

### FR-TRUST-01

The system shall calculate a suspicious-review risk score using available review signals.

### FR-TRUST-02

The system shall label results as low risk, potentially suspicious or insufficient evidence.

### FR-TRUST-03

The system shall calculate an explainable seller trust score.

### FR-TRUST-04

The system shall display factors contributing to the trust score.

---

## 14. Conversational Assistant

### FR-CHAT-01

The system shall allow users to submit natural-language product questions.

### FR-CHAT-02

The assistant shall answer questions using data stored within VEXTRO.

### FR-CHAT-03

The assistant shall support product search, comparison, price-history and review-insight questions.

### FR-CHAT-04

The assistant shall maintain limited conversation context for follow-up questions.

### FR-CHAT-05

The assistant shall state when sufficient supporting data is unavailable.

---

## 15. Notifications and Reports

### FR-NOTIF-01

The system shall provide in-application notifications.

### FR-NOTIF-02

The user shall be able to mark notifications as read.

### FR-NOTIF-03

The system shall support price-alert, competitor, inventory and system notifications.

### FR-REPORT-01

The system shall allow authorized users to generate supported analytical reports.

### FR-REPORT-02

The system shall support CSV export.

### FR-REPORT-03

The system may support PDF and Excel export during the advanced implementation phase.

---

## 16. Administrator Functions

### FR-ADMIN-01

The administrator shall be able to view system statistics.

### FR-ADMIN-02

The administrator shall be able to view and manage users.

### FR-ADMIN-03

The administrator shall be able to manage canonical products and listings.

### FR-ADMIN-04

The administrator shall be able to review uncertain product matches.

### FR-ADMIN-05

The administrator shall be able to view scraper runs and scraper errors.

### FR-ADMIN-06

The administrator shall be able to view model versions and evaluation results.

### FR-ADMIN-07

The administrator shall be able to deactivate invalid listings.

---

## 17. Scope Priority

### Must-Have

- Authentication and roles
- Product catalog
- Daraz and PriceOye data
- Normalization and matching
- Search and filtering
- Product comparison
- Price history
- Price alerts
- Consumer dashboard
- Admin dashboard
- Sentiment analysis

### Should-Have

- Price forecasting
- Product recommendations
- SME competitor monitoring
- Reports
- Seller trust score
- Review summarization

### Prototype / Advanced

- LSTM forecasting
- Collaborative filtering
- Fake-review detection
- Conversational AI
- Demand forecasting
- Inventory optimization
- Dynamic pricing simulations
