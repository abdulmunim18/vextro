# VEXTRO Initial API Contract

## Document Information

- **Project:** VEXTRO
- **Version:** 1.0
- **Status:** Initial Backend–Frontend Contract
- **Base URL:** `/api/v1`
- **Response Format:** JSON
- **Authentication:** Bearer access token

---

## 1. General Conventions

### Authentication Header

```http
Authorization: Bearer <access_token>
```

### Content Type

```http
Content-Type: application/json
```

### Date and Time Format

All timestamps use ISO 8601 UTC format.

```text
2026-07-29T10:30:00Z
```

### Pagination Parameters

```text
page=1
page_size=20
```

### Standard Paginated Response

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total_items": 0,
  "total_pages": 0
}
```

### Standard Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The submitted data is invalid.",
    "details": []
  }
}
```

### Main HTTP Status Codes

| Code | Meaning |
|---:|---|
| 200 | Request completed successfully |
| 201 | Resource created successfully |
| 204 | Request completed with no response body |
| 400 | Invalid request |
| 401 | Authentication required or invalid |
| 403 | User does not have permission |
| 404 | Resource not found |
| 409 | Duplicate or conflicting resource |
| 422 | Validation failed |
| 500 | Internal server error |
| 503 | Dependent service unavailable |

---

# 2. Health Endpoints

## GET `/health`

**Access:** Public  
**Purpose:** Check application health.

### Response — 200

```json
{
  "status": "healthy",
  "project": "VEXTRO API",
  "version": "0.1.0"
}
```

---

## GET `/database/health`

**Access:** Development/Admin  
**Purpose:** Check PostgreSQL connectivity.

### Response — 200

```json
{
  "status": "healthy",
  "database_name": "vextro_db",
  "connected_user": "vextro_app",
  "postgres_version": "PostgreSQL"
}
```

---

# 3. Authentication Endpoints

## POST `/api/v1/auth/register`

**Access:** Public  
**Purpose:** Register a Consumer or SME account.

### Request

```json
{
  "full_name": "Example User",
  "email": "user@example.com",
  "password": "StrongPassword123!",
  "account_type": "consumer"
}
```

Allowed `account_type` values:

```text
consumer
sme
```

### Response — 201

```json
{
  "id": 1,
  "full_name": "Example User",
  "email": "user@example.com",
  "roles": ["consumer"],
  "is_active": true,
  "is_verified": false,
  "created_at": "2026-07-29T10:30:00Z"
}
```

### Possible Errors

- `EMAIL_ALREADY_REGISTERED`
- `WEAK_PASSWORD`
- `INVALID_ACCOUNT_TYPE`

---

## POST `/api/v1/auth/login`

**Access:** Public  
**Purpose:** Authenticate a user.

### Request

```json
{
  "email": "user@example.com",
  "password": "StrongPassword123!"
}
```

### Response — 200

```json
{
  "access_token": "<jwt_access_token>",
  "refresh_token": "<refresh_token>",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": 1,
    "full_name": "Example User",
    "email": "user@example.com",
    "roles": ["consumer"]
  }
}
```

### Possible Errors

- `INVALID_CREDENTIALS`
- `ACCOUNT_INACTIVE`

---

## POST `/api/v1/auth/refresh`

**Access:** Public with valid refresh token  
**Purpose:** Create a new access token.

### Request

```json
{
  "refresh_token": "<refresh_token>"
}
```

### Response — 200

```json
{
  "access_token": "<new_access_token>",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

## POST `/api/v1/auth/logout`

**Access:** Authenticated  
**Purpose:** Revoke the current refresh-token session.

### Request

```json
{
  "refresh_token": "<refresh_token>"
}
```

### Response — 204

No response body.

---

## GET `/api/v1/auth/me`

**Access:** Authenticated  
**Purpose:** Return the current user.

### Response — 200

```json
{
  "id": 1,
  "full_name": "Example User",
  "email": "user@example.com",
  "roles": ["consumer"],
  "is_active": true,
  "is_verified": false
}
```

---

# 4. Catalog Endpoints

## GET `/api/v1/categories`

**Access:** Public  
**Purpose:** List active product categories.

### Response — 200

```json
{
  "items": [
    {
      "id": 1,
      "name": "Mobile Phones",
      "slug": "mobile-phones",
      "parent_id": null
    }
  ]
}
```

---

## GET `/api/v1/brands`

**Access:** Public  
**Purpose:** List supported brands.

### Response — 200

```json
{
  "items": [
    {
      "id": 1,
      "name": "Samsung",
      "slug": "samsung"
    }
  ]
}
```

---

## GET `/api/v1/platforms`

**Access:** Public  
**Purpose:** List supported marketplaces.

### Response — 200

```json
{
  "items": [
    {
      "id": 1,
      "name": "Daraz",
      "code": "daraz"
    },
    {
      "id": 2,
      "name": "PriceOye",
      "code": "priceoye"
    }
  ]
}
```

---

## GET `/api/v1/products`

**Access:** Public  
**Purpose:** Search and filter canonical products.

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---:|---|
| `q` | string | No | Search title, brand or model |
| `category_id` | integer | No | Filter by category |
| `brand_id` | integer | No | Filter by brand |
| `platform` | string | No | Filter by marketplace |
| `min_price` | decimal | No | Minimum current listing price |
| `max_price` | decimal | No | Maximum current listing price |
| `min_rating` | decimal | No | Minimum rating |
| `available` | boolean | No | Availability filter |
| `sort` | string | No | `price_asc`, `price_desc`, `rating`, `latest` |
| `page` | integer | No | Default `1` |
| `page_size` | integer | No | Default `20` |

### Response — 200

```json
{
  "items": [
    {
      "id": 100,
      "name": "Samsung Galaxy Example",
      "brand": "Samsung",
      "category": "Mobile Phones",
      "image_url": "https://example.com/image.jpg",
      "lowest_price": 999.99,
      "highest_price": 1099.99,
      "currency": "PKR",
      "platform_count": 2,
      "average_rating": 4.5
    }
  ],
  "page": 1,
  "page_size": 20,
  "total_items": 1,
  "total_pages": 1
}
```

---

## GET `/api/v1/products/{product_id}`

**Access:** Public  
**Purpose:** Get complete canonical product details.

### Response — 200

```json
{
  "id": 100,
  "name": "Samsung Galaxy Example",
  "model": "Example Model",
  "brand": {
    "id": 1,
    "name": "Samsung"
  },
  "category": {
    "id": 1,
    "name": "Mobile Phones"
  },
  "description": "Product description",
  "specifications": {
    "display": "6.5 inch",
    "battery": "5000 mAh"
  },
  "variants": []
}
```

---

## GET `/api/v1/products/{product_id}/listings`

**Access:** Public  
**Purpose:** Return matching marketplace listings.

### Response — 200

```json
{
  "product_id": 100,
  "listings": [
    {
      "id": 501,
      "platform": "Daraz",
      "seller": "Example Seller",
      "title": "Samsung Galaxy Example",
      "current_price": 999.99,
      "currency": "PKR",
      "rating": 4.5,
      "review_count": 250,
      "is_available": true,
      "warranty": "1 Year",
      "product_url": "https://example.com/product"
    }
  ]
}
```

---

## GET `/api/v1/products/{product_id}/compare`

**Access:** Public  
**Purpose:** Compare listings and identify best value.

### Response — 200

```json
{
  "product_id": 100,
  "lowest_price_listing_id": 501,
  "best_value_listing_id": 501,
  "market_average_price": 1049.99,
  "listings": []
}
```

---

# 5. Price Intelligence Endpoints

## GET `/api/v1/products/{product_id}/price-history`

**Access:** Public  
**Purpose:** Return historical price observations.

### Query Parameters

```text
platform
date_from
date_to
```

### Response — 200

```json
{
  "product_id": 100,
  "current_price": 999.99,
  "minimum_price": 949.99,
  "maximum_price": 1099.99,
  "average_price": 1015.50,
  "currency": "PKR",
  "observations": [
    {
      "listing_id": 501,
      "platform": "Daraz",
      "price": 999.99,
      "observed_at": "2026-07-29T10:30:00Z"
    }
  ]
}
```

---

## GET `/api/v1/products/{product_id}/forecast`

**Access:** Public  
**Purpose:** Return available price forecast and buying guidance.

### Response — 200

```json
{
  "product_id": 100,
  "status": "available",
  "guidance": "wait",
  "explanation": "The model predicts a small price decrease.",
  "model_version": "price-arima-v1",
  "metrics": {
    "mae": 25.4,
    "rmse": 31.8
  },
  "forecast": []
}
```

If data is insufficient:

```json
{
  "product_id": 100,
  "status": "insufficient_data",
  "guidance": null,
  "explanation": "More historical observations are required."
}
```

---

## POST `/api/v1/price-alerts`

**Access:** Consumer  
**Purpose:** Create a target-price alert.

### Request

```json
{
  "product_variant_id": 200,
  "target_price": 949.99,
  "currency": "PKR"
}
```

### Response — 201

```json
{
  "id": 1,
  "product_variant_id": 200,
  "target_price": 949.99,
  "currency": "PKR",
  "is_active": true,
  "created_at": "2026-07-29T10:30:00Z"
}
```

---

## GET `/api/v1/price-alerts`

**Access:** Consumer  
**Purpose:** List current user's price alerts.

---

## PATCH `/api/v1/price-alerts/{alert_id}`

**Access:** Alert owner  
**Purpose:** Update target price or active status.

### Request

```json
{
  "target_price": 929.99,
  "is_active": true
}
```

---

## DELETE `/api/v1/price-alerts/{alert_id}`

**Access:** Alert owner  
**Purpose:** Delete a price alert.

### Response — 204

---

# 6. Review Intelligence Endpoints

## GET `/api/v1/products/{product_id}/reviews`

**Access:** Public  
**Purpose:** Return paginated product reviews.

### Query Parameters

```text
sentiment
rating
platform
page
page_size
```

---

## GET `/api/v1/products/{product_id}/review-insights`

**Access:** Public  
**Purpose:** Return sentiment and review summary.

### Response — 200

```json
{
  "product_id": 100,
  "review_count": 500,
  "sentiment_distribution": {
    "positive": 72.0,
    "neutral": 18.0,
    "negative": 10.0
  },
  "positive_summary": "Customers commonly appreciate battery life.",
  "negative_summary": "Some customers report slow charging.",
  "common_aspects": [
    {
      "aspect": "battery",
      "sentiment": "positive",
      "mention_count": 120
    }
  ],
  "model_version": "sentiment-v1"
}
```

---

## GET `/api/v1/sellers/{seller_id}/trust-score`

**Access:** Public  
**Purpose:** Return explainable seller trust information.

### Response — 200

```json
{
  "seller_id": 10,
  "trust_score": 84.5,
  "risk_level": "low",
  "factors": {
    "rating": 4.7,
    "review_count": 1800,
    "verified_status": true
  },
  "model_version": "seller-trust-v1"
}
```

---

# 7. Consumer Endpoints

## GET `/api/v1/consumer/dashboard`

**Access:** Consumer  
**Purpose:** Return consumer dashboard summary.

### Response — 200

```json
{
  "tracked_products": 5,
  "active_alerts": 3,
  "recent_price_drops": [],
  "recommendations": [],
  "unread_notifications": 2
}
```

---

## POST `/api/v1/watchlist`

**Access:** Consumer  
**Purpose:** Add a product variant to the watchlist.

### Request

```json
{
  "product_variant_id": 200
}
```

---

## GET `/api/v1/watchlist`

**Access:** Consumer  
**Purpose:** List tracked products.

---

## DELETE `/api/v1/watchlist/{product_variant_id}`

**Access:** Consumer  
**Purpose:** Remove a product from the watchlist.

### Response — 204

---

## GET `/api/v1/recommendations`

**Access:** Consumer  
**Purpose:** Return personalized or cold-start recommendations.

---

## POST `/api/v1/saved-comparisons`

**Access:** Consumer  
**Purpose:** Save selected marketplace listings.

### Request

```json
{
  "title": "My Mobile Comparison",
  "listing_ids": [501, 502]
}
```

---

## GET `/api/v1/saved-comparisons`

**Access:** Consumer  
**Purpose:** List saved comparisons.

---

# 8. SME Endpoints

## POST `/api/v1/sme/organizations`

**Access:** SME  
**Purpose:** Create an SME business profile.

### Request

```json
{
  "name": "Example Business",
  "industry": "Electronics",
  "registration_number": "Optional"
}
```

---

## GET `/api/v1/sme/dashboard`

**Access:** SME organization member  
**Purpose:** Return SME analytics summary.

### Response — 200

```json
{
  "organization_id": 1,
  "business_product_count": 10,
  "competitor_alert_count": 2,
  "inventory_risk_count": 1,
  "recent_price_changes": []
}
```

---

## POST `/api/v1/sme/business-products`

**Access:** SME organization member  
**Purpose:** Add a product managed by the SME.

### Request

```json
{
  "organization_id": 1,
  "product_variant_id": 200,
  "internal_sku": "SKU-001",
  "cost_price": 750.00,
  "selling_price": 999.99,
  "current_stock": 25,
  "minimum_stock": 5
}
```

---

## GET `/api/v1/sme/business-products`

**Access:** SME organization member  
**Purpose:** List organization products.

---

## POST `/api/v1/sme/competitor-watchlists`

**Access:** SME organization member  
**Purpose:** Monitor a competitor listing.

### Request

```json
{
  "business_product_id": 1,
  "listing_id": 501
}
```

---

## GET `/api/v1/sme/competitor-analysis/{business_product_id}`

**Access:** SME organization member  
**Purpose:** Compare own price with monitored competitors.

### Response — 200

```json
{
  "business_product_id": 1,
  "own_price": 999.99,
  "market_average_price": 1025.00,
  "lowest_competitor_price": 975.00,
  "price_gap": 24.99,
  "competitors": []
}
```

---

## POST `/api/v1/sme/sales-imports`

**Access:** SME organization member  
**Content Type:** `multipart/form-data`  
**Purpose:** Import supported sales CSV.

### Response — 201

```json
{
  "import_id": 1,
  "status": "completed",
  "total_rows": 100,
  "accepted_rows": 95,
  "rejected_rows": 5
}
```

---

## GET `/api/v1/sme/demand-forecast/{business_product_id}`

**Access:** SME organization member  
**Purpose:** Return product demand forecast.

---

## POST `/api/v1/sme/pricing-scenarios`

**Access:** SME organization member  
**Purpose:** Evaluate a proposed price.

### Request

```json
{
  "business_product_id": 1,
  "proposed_price": 979.99
}
```

### Response — 200

```json
{
  "current_price": 999.99,
  "proposed_price": 979.99,
  "estimated_units": 120,
  "estimated_revenue": 117598.80,
  "estimated_margin": 27598.80,
  "risk_level": "medium",
  "assumptions": []
}
```

---

# 9. Notification and Report Endpoints

## GET `/api/v1/notifications`

**Access:** Authenticated  
**Purpose:** List current user's notifications.

### Query Parameters

```text
is_read
notification_type
page
page_size
```

---

## PATCH `/api/v1/notifications/{notification_id}/read`

**Access:** Notification owner  
**Purpose:** Mark a notification as read.

---

## POST `/api/v1/reports`

**Access:** Authenticated  
**Purpose:** Request a supported report.

### Request

```json
{
  "report_type": "price_history",
  "file_format": "csv",
  "filters": {
    "product_id": 100
  }
}
```

### Response — 202

```json
{
  "id": 1,
  "status": "queued",
  "requested_at": "2026-07-29T10:30:00Z"
}
```

---

## GET `/api/v1/reports/{report_id}`

**Access:** Report owner or Admin  
**Purpose:** Check report status and obtain file information.

---

# 10. Administrator Endpoints

## GET `/api/v1/admin/dashboard`

**Access:** Admin  
**Purpose:** Return operational statistics.

---

## GET `/api/v1/admin/users`

**Access:** Admin  
**Purpose:** Search and filter users.

### Query Parameters

```text
q
role
is_active
page
page_size
```

---

## PATCH `/api/v1/admin/users/{user_id}/status`

**Access:** Admin  
**Purpose:** Activate or deactivate a user.

### Request

```json
{
  "is_active": false
}
```

---

## GET `/api/v1/admin/product-matches/pending`

**Access:** Admin  
**Purpose:** List uncertain product matches.

---

## POST `/api/v1/admin/product-matches/{match_id}/decision`

**Access:** Admin  
**Purpose:** Approve or reject a product match.

### Request

```json
{
  "decision": "approved",
  "notes": "Titles and specifications represent the same variant."
}
```

---

## GET `/api/v1/admin/scrape-runs`

**Access:** Admin  
**Purpose:** Monitor collection runs and failures.

---

## POST `/api/v1/admin/scrape-runs`

**Access:** Admin  
**Purpose:** Trigger an allowed manual collection run.

### Request

```json
{
  "platform": "daraz",
  "run_type": "manual"
}
```

---

## GET `/api/v1/admin/model-versions`

**Access:** Admin  
**Purpose:** View available model versions and metrics.

---

## GET `/api/v1/admin/audit-logs`

**Access:** Admin  
**Purpose:** View sensitive system actions.

---

# 11. Role Permission Matrix

| API Area | Public | Consumer | SME | Admin |
|---|:---:|:---:|:---:|:---:|
| Health | Yes | Yes | Yes | Yes |
| Product search | Yes | Yes | Yes | Yes |
| Product comparison | Yes | Yes | Yes | Yes |
| Price history | Yes | Yes | Yes | Yes |
| Review insights | Yes | Yes | Yes | Yes |
| Price alerts | No | Yes | No | Yes |
| Watchlist | No | Yes | No | Yes |
| Recommendations | No | Yes | No | Yes |
| SME dashboard | No | No | Yes | Yes |
| SME products | No | No | Yes | Yes |
| Competitor monitoring | No | No | Yes | Yes |
| User management | No | No | No | Yes |
| Product-match review | No | No | No | Yes |
| Scraper monitoring | No | No | No | Yes |
| Model monitoring | No | No | No | Yes |

---

# 12. Implementation Order

The initial API implementation order is:

1. Authentication
2. Categories, brands and platforms
3. Product search and product details
4. Listings and cross-platform comparison
5. Price history
6. Watchlist and price alerts
7. Review sentiment
8. Consumer dashboard
9. SME organization and competitor monitoring
10. Administrator monitoring
11. Reports and advanced AI endpoints

---

# 13. Contract Change Rule

Any endpoint, request field, response field or permission change must be updated in this document before frontend and backend implementations are considered complete.
