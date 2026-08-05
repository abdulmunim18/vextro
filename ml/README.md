# VEXTRO Machine Learning Workspace

This workspace contains the independent AI and machine-learning modules used by the FastAPI backend.

## Module Ownership

### AI/ML Member

- 6.4 AI Price Intelligence and Forecasting
- 6.5 NLP Sentiment and Review Analytics
- 6.6 AI-Powered Personalization Engine
- 6.9 Smart Inventory and Demand Forecasting

### Data Engineering Member

- 6.10 Fake Review and Trust Verification

## Structure

- `price_forecasting` — ARIMA and optional LSTM forecasting
- `sentiment` — Sentiment, aspect analysis and summaries
- `personalization` — Content-based recommendation logic
- `demand_forecasting` — Sales and inventory forecasting
- `trust_verification` — Fake-review risk and seller trust
- `shared` — Common preprocessing, schemas and utilities
- `datasets` — Local sample datasets; do not commit sensitive or very large files
- `artifacts` — Generated model artifacts; large files should not be committed
- `tests` — Model, preprocessing and inference tests

## Required Output for Every Module

- Training or baseline script
- Inference function or API-ready service
- Sample input and output
- Evaluation metrics
- Tests
- Error handling
- Model limitations
- Short usage instructions
