# VEXTRO Scraper Workspace

This workspace is owned primarily by the Data Acquisition and Engineering member.

## Assigned Modules

- 6.1 Multi-Platform Data Acquisition
- 6.2 Data Processing and Normalization
- 6.3 Data Warehouse Operations
- Data preparation support for 6.10 Trust Verification

## Structure

- `app/sources/daraz` — Daraz collector and parser
- `app/sources/priceoye` — PriceOye collector and parser
- `app/normalizers` — Price, title and specification normalization
- `app/matching` — Canonical product and variant matching
- `app/services` — Acquisition workflow and backend ingestion
- `fixtures` — Saved HTML or JSON test fixtures
- `tests` — Parser and normalization tests

## Development Rules

- Do not scrape from the frontend.
- Use respectful request delays, timeouts and retries.
- Store saved fixtures for reliable tests.
- Return standardized records for backend ingestion.
- Do not directly modify backend database models without a pull request.
- Include tests, sample input/output and a README update with every feature.
