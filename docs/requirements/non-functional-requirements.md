# VEXTRO Non-Functional Requirements

## 1. Performance

### NFR-PERF-01

Normal product-search requests should return within 2 seconds for the demonstration dataset.

### NFR-PERF-02

A product-comparison page should load within 3 seconds under normal development conditions.

### NFR-PERF-03

Long-running data acquisition and machine-learning tasks shall not block normal user API requests.

### NFR-PERF-04

Frequently accessed database fields shall use suitable indexes.

---

## 2. Security

### NFR-SEC-01

Passwords shall never be stored in plain text.

### NFR-SEC-02

Protected APIs shall require authentication.

### NFR-SEC-03

Role-based authorization shall protect Consumer, SME and Administrator resources.

### NFR-SEC-04

Environment variables shall be used for passwords, database credentials and private keys.

### NFR-SEC-05

Secrets and local environment files shall not be committed to GitHub.

### NFR-SEC-06

User input shall be validated before database or model processing.

### NFR-SEC-07

Authentication and high-cost endpoints should apply rate limiting during the hardening phase.

---

## 3. Reliability

### NFR-REL-01

Failure of one scraper shall not crash the complete application.

### NFR-REL-02

Scraper errors shall be recorded for administrator review.

### NFR-REL-03

The project shall include a seeded demonstration dataset.

### NFR-REL-04

The panel demonstration shall not depend entirely on live marketplace access.

### NFR-REL-05

Database migrations shall be reversible where practical.

---

## 4. Availability and Recovery

### NFR-AVAIL-01

The development system shall provide database backup instructions.

### NFR-AVAIL-02

The application shall provide health endpoints for backend and database monitoring.

### NFR-AVAIL-03

The system shall provide a documented local startup process.

---

## 5. Usability

### NFR-USE-01

The interface shall use consistent navigation and design components.

### NFR-USE-02

The user interface shall provide clear loading, success, empty and error states.

### NFR-USE-03

The main consumer and SME workflows shall be understandable without technical knowledge.

### NFR-USE-04

The application shall be responsive on desktop, tablet and mobile screens.

### NFR-USE-05

Charts and AI recommendations shall include readable descriptions.

---

## 6. Maintainability

### NFR-MAIN-01

Frontend, backend, scraper and ML code shall remain separated.

### NFR-MAIN-02

Database schema changes shall be managed through migrations.

### NFR-MAIN-03

Major functionality shall be developed in feature branches.

### NFR-MAIN-04

Changes to the main branch shall use pull requests and review.

### NFR-MAIN-05

Functions, classes and modules shall use clear descriptive names.

### NFR-MAIN-06

Important APIs and modules shall include documentation.

---

## 7. Data Quality

### NFR-DATA-01

Product data shall be validated before being added to the canonical catalog.

### NFR-DATA-02

Duplicate listings shall be detected and controlled.

### NFR-DATA-03

Every historical observation shall contain an observation timestamp.

### NFR-DATA-04

The source platform shall be recorded for collected listings and reviews.

### NFR-DATA-05

Synthetic or manually prepared academic data shall be clearly identified.

---

## 8. AI and Model Quality

### NFR-AI-01

Each implemented ML model shall be evaluated using appropriate metrics.

### NFR-AI-02

Sentiment classification shall report precision, recall and F1-score.

### NFR-AI-03

Price forecasting shall report MAE, RMSE or MAPE.

### NFR-AI-04

Predictions shall not be presented as guaranteed outcomes.

### NFR-AI-05

The application shall show insufficient-data messages when a reliable prediction cannot be generated.

### NFR-AI-06

The active model version and training date shall be recorded.

---

## 9. Compatibility

### NFR-COMP-01

The frontend shall support recent desktop versions of Chrome, Edge and Firefox.

### NFR-COMP-02

The development environment shall support Windows 11.

### NFR-COMP-03

The backend shall expose standards-based REST APIs.

---

## 10. Scalability

### NFR-SCALE-01

The database design shall support additional e-commerce platforms in the future.

### NFR-SCALE-02

The catalog shall support additional product categories without redesigning the complete system.

### NFR-SCALE-03

Background processing shall be separable from interactive web requests.

---

## 11. Ethical and Legal Constraints

### NFR-ETH-01

Only publicly accessible or explicitly permitted data shall be collected.

### NFR-ETH-02

Data acquisition shall use reasonable request rates.

### NFR-ETH-03

The system shall not attempt to bypass protected or private marketplace data.

### NFR-ETH-04

Marketplace source attribution shall be retained where applicable.

---

## 12. Documentation

### NFR-DOC-01

The repository shall contain setup and startup instructions.

### NFR-DOC-02

The final project shall include an ERD and architecture diagram.

### NFR-DOC-03

Each core module shall include functional test cases.

### NFR-DOC-04

Known limitations shall be documented honestly.
