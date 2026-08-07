# VEXTRO Use Cases

## Actors

VEXTRO contains the following primary actors:

1. Visitor
2. Consumer
3. SME / Business User
4. Administrator
5. Data Collection Scheduler
6. Machine-Learning Service

---

# 1. Visitor Use Cases

## UC-VIS-01 — View Landing Page

### Actor
Visitor

### Preconditions
None

### Main Flow

1. Visitor opens VEXTRO.
2. System displays the public landing page.
3. System explains Consumer and SME capabilities.
4. Visitor can select Login or Register.

### Result
Visitor understands the purpose of VEXTRO.

---

## UC-VIS-02 — Register Account

### Actor
Visitor

### Preconditions
The email is not already registered.

### Main Flow

1. Visitor opens the registration page.
2. Visitor enters full name, email and password.
3. Visitor selects an available account type where permitted.
4. System validates the input.
5. System hashes the password.
6. System creates the account.
7. System assigns the default role.
8. System confirms successful registration.

### Alternative Flows

- Email already exists.
- Password does not meet requirements.
- Required data is missing.

### Result
A new user account is created.

---

## UC-VIS-03 — Login

### Actor
Visitor

### Preconditions
The user has a registered and active account.

### Main Flow

1. User enters email and password.
2. System validates credentials.
3. System issues authentication tokens.
4. System identifies the user's role.
5. System redirects the user to the correct dashboard.

### Alternative Flows

- Invalid email or password.
- Account is inactive.
- Authentication service is unavailable.

### Result
The authenticated user enters VEXTRO.

---

# 2. Consumer Use Cases

## UC-CONS-01 — Search Products

### Actor
Consumer

### Preconditions
Product data exists in the catalog.

### Main Flow

1. Consumer enters a product title, brand or model.
2. System validates the search query.
3. System searches canonical products and listings.
4. System returns paginated results.
5. Consumer can apply filters and sorting.

### Result
Relevant products are displayed.

---

## UC-CONS-02 — View Product Details

### Actor
Consumer

### Main Flow

1. Consumer selects a product.
2. System loads canonical product information.
3. System loads specifications and platform listings.
4. System displays current prices and availability.
5. System displays rating, review and price-history information.

### Result
Consumer understands the available product and listings.

---

## UC-CONS-03 — Compare Marketplace Listings

### Actor
Consumer

### Main Flow

1. Consumer opens the product comparison view.
2. System displays matching Daraz and PriceOye listings.
3. System compares price, seller, rating, warranty and availability.
4. System highlights the lowest price or best-value listing.
5. Consumer may open the original marketplace link.

### Result
Consumer can make an informed purchasing decision.

---

## UC-CONS-04 — View Price History

### Actor
Consumer

### Main Flow

1. Consumer opens a product's price-history view.
2. System retrieves historical observations.
3. System calculates minimum, maximum, average and current price.
4. System displays the price-history chart.

### Alternative Flow

If insufficient history exists, the system displays an insufficient-data message.

### Result
Consumer understands the product's historical pricing behavior.

---

## UC-CONS-05 — Create Price Alert

### Actor
Consumer

### Preconditions
Consumer is authenticated.

### Main Flow

1. Consumer selects a product.
2. Consumer enters a target price.
3. System validates the target.
4. System creates an active price alert.
5. Future price observations are checked against the target.
6. System creates a notification when the condition is met.

### Result
Consumer receives a price-related notification.

---

## UC-CONS-06 — Manage Watchlist

### Actor
Consumer

### Main Flow

1. Consumer adds a product to the watchlist.
2. System saves the relationship.
3. Consumer can view tracked products.
4. Consumer may remove a product.

### Result
Consumer maintains a personalized product watchlist.

---

## UC-CONS-07 — View Review Intelligence

### Actor
Consumer

### Main Flow

1. Consumer opens product-review insights.
2. System retrieves processed reviews.
3. System displays positive, neutral and negative percentages.
4. System displays major positive and negative aspects.
5. System displays a review summary.

### Result
Consumer understands general customer feedback quickly.

---

## UC-CONS-08 — View Buying Guidance

### Actor
Consumer

### Main Flow

1. Consumer opens AI price insights.
2. System loads price history and forecast.
3. System displays predicted trend.
4. System returns Buy Now, Wait or Insufficient Data.
5. System explains the confidence and limitations.

### Result
Consumer receives explainable buying guidance.

---

## UC-CONS-09 — View Recommendations

### Actor
Consumer

### Main Flow

1. System analyzes product views, searches and watchlist activity.
2. System selects similar or relevant products.
3. Consumer views recommendations.
4. Consumer can open recommended product details.

### Result
Consumer discovers relevant products.

---

# 3. SME Use Cases

## UC-SME-01 — Manage Business Profile

### Actor
SME User

### Main Flow

1. SME user creates or updates the business profile.
2. System validates business information.
3. System stores organization data.
4. Authorized organization users may access the SME dashboard.

### Result
The SME organization is represented within VEXTRO.

---

## UC-SME-02 — Add Business Products

### Actor
SME User

### Main Flow

1. SME user adds a product or SKU.
2. SME user links it with a canonical product where applicable.
3. System stores current price, cost and inventory information.
4. Product appears in the SME dashboard.

### Result
The SME can monitor its own products.

---

## UC-SME-03 — Monitor Competitors

### Actor
SME User

### Main Flow

1. SME user selects a business product.
2. SME user adds competitor listings to the watchlist.
3. System monitors observed competitor prices.
4. System displays market average and pricing gap.
5. System highlights significant competitor changes.

### Result
The SME understands its competitive pricing position.

---

## UC-SME-04 — Import Sales Data

### Actor
SME User

### Preconditions
The CSV follows the supported template.

### Main Flow

1. SME user uploads a CSV file.
2. System validates the file and columns.
3. System rejects invalid rows with explanations.
4. Valid sales records are imported.
5. System displays an import summary.

### Result
Historical sales become available for analytics.

---

## UC-SME-05 — View Demand Forecast

### Actor
SME User

### Main Flow

1. SME user selects a product.
2. System retrieves historical sales and supported signals.
3. Forecasting service generates expected demand.
4. System displays the forecast and evaluation information.

### Result
SME user receives future demand guidance.

---

## UC-SME-06 — View Reorder Recommendation

### Actor
SME User

### Main Flow

1. System reads current inventory.
2. System reads forecast demand and sales velocity.
3. System calculates a recommended reorder point.
4. System highlights products with inventory risk.

### Result
SME user receives stock-management guidance.

---

## UC-SME-07 — Use Pricing Advisor

### Actor
SME User

### Main Flow

1. SME user selects a product.
2. System compares the current price with competitor prices.
3. SME user enters a proposed price.
4. System estimates revenue and margin impact.
5. System displays pricing risk and recommendation.

### Result
SME user can evaluate a pricing scenario.

---

## UC-SME-08 — Export Business Report

### Actor
SME User

### Main Flow

1. SME user selects the report type.
2. SME user selects filters and date range.
3. System generates the report.
4. System provides a supported download format.

### Result
SME user receives an analytical report.

---

# 4. Administrator Use Cases

## UC-ADMIN-01 — Manage Users

### Actor
Administrator

### Main Flow

1. Administrator views registered users.
2. Administrator filters users by role or status.
3. Administrator can activate or deactivate an account.
4. Administrator can inspect user roles.

### Result
User access remains controlled.

---

## UC-ADMIN-02 — Manage Products and Listings

### Actor
Administrator

### Main Flow

1. Administrator views canonical products and listings.
2. Administrator edits incorrect normalized data.
3. Administrator deactivates invalid listings.
4. Administrator resolves duplicate-product issues.

### Result
Catalog quality is maintained.

---

## UC-ADMIN-03 — Resolve Product Matches

### Actor
Administrator

### Main Flow

1. System displays uncertain matching candidates.
2. Administrator compares titles and specifications.
3. Administrator approves or rejects the proposed match.
4. System records the decision.

### Result
Uncertain listings are correctly classified.

---

## UC-ADMIN-04 — Monitor Data Collection

### Actor
Administrator

### Main Flow

1. Administrator views collection runs.
2. System displays success, failure and item counts.
3. Administrator views detailed errors.
4. Administrator may trigger an allowed manual run.

### Result
Data acquisition remains observable.

---

## UC-ADMIN-05 — Monitor Models

### Actor
Administrator

### Main Flow

1. Administrator views deployed model versions.
2. System displays training date and evaluation metrics.
3. Administrator identifies the active model.
4. Administrator can review model-related failures.

### Result
AI functionality remains traceable.

---

## UC-ADMIN-06 — View System Health

### Actor
Administrator

### Main Flow

1. Administrator opens the system dashboard.
2. System displays backend and database status.
3. System displays recent application errors.
4. System displays operational statistics.

### Result
Administrator understands the current system condition.

---

# 5. Automated System Use Cases

## UC-AUTO-01 — Scheduled Data Acquisition

### Actor
Data Collection Scheduler

### Main Flow

1. Scheduler starts a collection run.
2. System records the run.
3. Supported collectors fetch permitted data.
4. System validates and normalizes the data.
5. System stores listing and price observations.
6. System records success and failure statistics.

### Result
VEXTRO receives updated marketplace information.

---

## UC-AUTO-02 — Evaluate Price Alerts

### Actor
Data Collection Scheduler

### Main Flow

1. New price observations are stored.
2. System loads active alerts for affected products.
3. System compares latest price with target price.
4. System creates notifications for satisfied conditions.

### Result
Eligible users receive alert notifications.

---

## UC-AUTO-03 — Generate AI Results

### Actor
Machine-Learning Service

### Main Flow

1. Service retrieves suitable input data.
2. Service processes or predicts results.
3. Service stores model version and output.
4. API exposes the result to authorized users.

### Result
AI insight becomes available in VEXTRO.