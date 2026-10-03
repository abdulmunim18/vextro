# Notification and Reporting Engine (Module 6.14)

VEXTRO delivers one notification event across three channels — in-app,
email and browser Web Push — and sends scheduled daily or weekly digest
reports. This document covers the architecture, configuration, local
testing and the known limitations.

---

## 1. Architecture

```
  PRICE ALERT EVENT                    COMPETITOR RISK EVENT
  (price_alert_service)                (competitor_alert_service)
          |                                      |
          +------------------+-------------------+
                             |
                             v
                   notification_dispatcher
                      dispatch_event()
                   (inside the caller's
                    business transaction)
                             |
     +-----------------------+-----------------------+
     |                       |                       |
     v                       v                       v
 InApp channel         Email channel          WebPush channel
 notifications row     outbox row             outbox row
 status=delivered      status=pending         status=pending
     |                       |                       |
     +-----------------------+-----------------------+
                             |
                        COMMIT  <-- the business transaction ends here
                             |
                             v
               dispatch_pending_deliveries()
              (after commit, or from the
               scheduled outbox job)
                             |
                 +-----------+-----------+
                 v                       v
            email_service          web_push_service
            (smtplib + TLS)        (pywebpush + VAPID)
```

The price-alert and competitor-risk services contain **no** SMTP or push
code. They build a `NotificationEventRequest` and hand it to the
dispatcher, which owns all channel logic.

### Why a transactional outbox

Notifications are created inside the ingestion transaction, which commits
later. Sending email inside that transaction would mean a rollback could
leave a delivered email describing a notification that does not exist.
Instead `dispatch_event` writes `notification_deliveries` rows with
`status = 'pending'`, and the transports are only contacted *after* the
commit. The same rows double as a retry queue.

### Idempotency

`notification_events.event_key` carries a unique index. A key that already
exists makes `dispatch_event` return `None`, and nothing — not the in-app
notification, not the email, not the push — is produced a second time.

| Event type        | Event key                                                  |
| ----------------- | ---------------------------------------------------------- |
| `price_drop`      | `price_alert:{alert_id}:trigger:{arming_generation}`       |
| `competitor_risk` | `competitor_risk:{watchlist_id}:{own_price}:{competitor_price}` |

`arming_generation` is the alert's `notification_count` before the
increment, so a replayed observation rebuilds the identical key while a
genuine re-arm produces a new one.

### Alert re-arming behaviour (preserved, not changed)

Price alerts are **one-time**. `is_triggered` latches on the first
qualifying observation and the alert then stays silent — including when
the price rebounds above the target and falls again:

```
Target: 100,000
105,000  -> silent
102,000  -> silent
 99,000  -> NOTIFY (in-app + email + push)
 98,500  -> silent
 98,000  -> silent
103,000  -> silent (a one-time alert does not re-arm itself)
 97,000  -> silent
```

The alert re-arms only when its owner reactivates it through
`PATCH /api/v1/price-alerts/{id}` with `is_active: true`, which clears
`is_triggered` and starts a new event-key generation. This was the
existing product behaviour before module 6.14 and has been preserved.

Competitor risk is edge-triggered on `last_risk_level` entering `high`:
`LOW -> HIGH` notifies, `HIGH -> HIGH` does not, `HIGH -> MEDIUM` does
not, and `MEDIUM -> HIGH` notifies again.

---

## 2. Email setup

Delivery uses Python's standard `smtplib` with STARTTLS or implicit SSL,
so any SMTP provider works. There is no third-party email SDK and no
credential is ever hard-coded or logged.

Add to `backend/.env` (see `backend/.env.example`):

```
FRONTEND_BASE_URL=http://localhost:5173

SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=alerts@your-domain.com
SMTP_FROM_NAME=VEXTRO
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=15
```

- Leaving `SMTP_HOST` empty disables email entirely. Events are still
  recorded and the email channel is marked `skipped`, with the reason
  stored on the delivery row.
- `SMTP_USE_SSL=true` uses implicit TLS (port 465) and ignores
  `SMTP_USE_TLS`.
- `FRONTEND_BASE_URL` is the only source of links in emails. Nothing
  builds a URL from untrusted input, and a notification's `action_path`
  must be a same-origin absolute path or the link falls back to the base
  URL.

### Templates

Templates live in `backend/app/services/email_templates.py` and render
both an HTML body and a plain-text fallback from the event's stored
payload.

| Template                        | Subject                                               | Contents |
| ------------------------------- | ----------------------------------------------------- | -------- |
| `render_price_drop_email`       | `Price Alert: {product} reached your target`          | product, current price, target price, amount below target, marketplace, timestamp, CTA |
| `render_competitor_risk_email`  | `Competitor Alert: {product} pricing position at risk`| product, own price, competitor price, gap %, risk level, marketplace, timestamp, CTA |
| `render_digest_email`           | `VEXTRO Daily/Weekly Digest - {period}`               | period sections, CTA |

### Failure behaviour

Email is a strictly secondary channel. On failure VEXTRO:

- keeps the price observation, the price alert state and the in-app
  notification exactly as they are;
- logs `email.delivery.failed` with the reason and no credentials;
- records the reason on the `notification_deliveries` row;
- retries on the next outbox run, up to
  `NOTIFICATION_DELIVERY_MAX_ATTEMPTS` (default 3).

A permanent rejection (refused recipient, refused sender, rejected
authentication) is marked `skipped` immediately rather than retried.

### Local testing without a real provider

Run a throwaway SMTP server that prints messages instead of sending them:

```bash
pip install aiosmtpd          # development only, not a runtime dependency
python -m aiosmtpd -n -l 127.0.0.1:1025
```

Then set:

```
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=alerts@vextro.local
SMTP_USE_TLS=false
```

MailHog or Mailpit work the same way and additionally give you a web
inbox. The automated tests mock the transport instead; a mocked send is
**not** evidence that a real provider accepts the message, so verify once
against a real inbox before release.

---

## 3. Browser Web Push setup

Standards-based Web Push: a Service Worker, the Push API, the
Notifications API and VAPID authentication. No Firebase.

### Generate VAPID keys

```bash
cd backend
python -m scripts.generate_vapid_keys
```

The script prints a fresh key pair to the terminal and writes nothing to
disk. Copy the values into `backend/.env`:

```
VAPID_PUBLIC_KEY=<printed public key>
VAPID_PRIVATE_KEY=<printed private key>
VAPID_SUBJECT=mailto:you@your-domain.com
```

**Never commit `VAPID_PRIVATE_KEY`.** `.env` is already gitignored. The
public key is safe to expose — the browser needs it to subscribe.

The frontend reads the public key from
`GET /api/v1/notifications/preferences`, so no frontend configuration is
required. You may optionally also set `VITE_VAPID_PUBLIC_KEY` in
`frontend/.env` as a fallback.

### Service worker

`frontend/public/service-worker.js` is served from the origin root so its
scope covers the whole app. It handles only `push` and
`notificationclick`; it caches nothing and intercepts no requests.

On click it opens or focuses the path the backend sent. Only same-origin
absolute paths are accepted — a payload path that is not `/...`, or that
starts with `//`, falls back to `/dashboard`. Both the service worker and
the email templates enforce this, so a crafted `action_path` cannot
become an open redirect.

### Permission flow

The browser prompt is never raised on page load. It appears only when the
user clicks **Enable browser notifications** in Dashboard → Notification
Settings, which then:

1. checks `serviceWorker`, `PushManager` and `Notification` support;
2. calls `Notification.requestPermission()`;
3. registers the service worker and waits for it to become ready;
4. obtains a `PushSubscription`;
5. posts it to `POST /api/v1/notifications/push/subscribe`;
6. turns the push preferences on.

The UI reports `granted`, `denied`, `default` (not yet asked), browser
unsupported, and server-not-configured as distinct states.

### Expired subscriptions

A push endpoint that answers `404 Not Found` or `410 Gone` is permanently
dead. VEXTRO sets `is_active = false` and `deactivated_at` on that
`push_subscriptions` row and logs `push.subscription.invalidated`, so
later jobs skip it. Any other failure (`503`, timeout, network error) is
treated as temporary: the subscription is left active and the delivery is
retried within the bounded budget.

### Verifying push without a browser

`tests/test_notification_web_push.py::test_real_vapid_encryption_accepts_the_payload`
runs the real `pywebpush` and `http_ece` stack — VAPID signing and
aes128gcm encryption — and intercepts only the outbound HTTP request. It
guards the encryption contract (the payload must be `bytes`, not `str`)
without needing a live push endpoint.

### Browser and host requirements

- A Service Worker needs a **secure context**: `https://`, or
  `http://localhost` / `http://127.0.0.1`. Push will not work over plain
  HTTP on a LAN address or a custom hostname.
- The Vite dev server on `http://localhost:5173` qualifies, so push works
  in local development without certificates.
- Chrome, Edge, Firefox and Opera support Web Push on desktop and
  Android. Safari supports it on macOS 13+ and, on iOS 16.4+, only for a
  site the user has added to the Home Screen. iOS Safari in a normal tab
  cannot receive Web Push.

---

## 4. Notification preferences

Stored in `notification_preferences`, one row per user, created with
sensible defaults on first read.

| Setting                  | Default | Notes |
| ------------------------ | ------- | ----- |
| Price alerts, in app     | on      | Always on, cannot be disabled |
| Price alerts, email      | on      | |
| Price alerts, push       | on      | Needs an active browser subscription |
| Competitor alerts, in app| on      | Always on, cannot be disabled |
| Competitor alerts, email | on      | |
| Competitor alerts, push  | on      | Needs an active browser subscription |
| Digest reports           | `off`   | `off`, `daily` or `weekly` |

In-app notifications stay available for every user, matching FR-NOTIF-01.
A user who disables email or push never receives that channel again for
that alert category; the delivery row records `skipped` with the reason.

The settings UI shows only the categories the signed-in role receives:
consumers see price alerts, SME owners see competitor alerts, and
administrators see both.

---

## 5. Scheduled digest reports

### What a digest contains

Consumers:
- price alerts triggered during the period, with observed and target price;
- the alerts still watching (shown alongside triggered alerts).

SME owners:
- competitor-risk events raised during the period, with own price,
  competitor price and gap percentage;
- optionally the existing competitor-intelligence PDF as an attachment
  (`DIGEST_ATTACH_SME_REPORT=true`), generated by the module 6.13
  `build_competitor_pdf` service — no reporting logic is duplicated.

Only data VEXTRO already records is used. No metric is invented.

### Periods and timezone

Boundaries are computed in `DIGEST_TIMEZONE` (default `Asia/Karachi`) and
converted to UTC for querying, so a daily digest covers the user-facing
calendar day rather than a UTC day.

- **Daily** reports the previous complete local day. A job at 08:00 on
  3 October sends the digest for 2 October.
- **Weekly** reports the previous complete seven-day block, where the week
  starts on `DIGEST_WEEKLY_DAY` (`0` = Monday).

A digest never reports a partial period. There is **no per-user
timezone** in the schema, so one system timezone applies to everybody;
this is a deliberate simplification and is listed as a limitation below.

### Empty digests

If the period produced no events, nothing is sent. The run is recorded as
`skipped_empty` and `digest.skipped_empty` is logged. VEXTRO never emails
a user to say nothing changed.

### Duplicate prevention

`digest_runs` has a unique index on `(user_id, frequency, period_key)`.
The run row is claimed *before* the email is built, so a scheduler that
fires twice for the same period loses the insert race and returns
`duplicate` without sending.

### Configuration

```
DIGEST_TIMEZONE=Asia/Karachi
DIGEST_DAILY_HOUR=8
DIGEST_WEEKLY_DAY=0
DIGEST_WEEKLY_HOUR=9
DIGEST_ATTACH_SME_REPORT=true
DIGEST_SCHEDULER_ENABLED=false
NOTIFICATION_OUTBOX_INTERVAL_SECONDS=300
```

### Running the jobs

Two supported options.

**In-process scheduler** — APScheduler inside the API, the same tool the
scraper already uses (`vextro_scraper/scheduler.py`). Set
`DIGEST_SCHEDULER_ENABLED=true` in **exactly one** API process. It
registers three jobs: the daily digest, the weekly digest and the outbox
retry sweep.

**External cron** — leave `DIGEST_SCHEDULER_ENABLED=false` and drive the
jobs yourself:

```bash
cd backend
python -m scripts.run_notification_jobs daily-digest
python -m scripts.run_notification_jobs weekly-digest
python -m scripts.run_notification_jobs outbox
```

Every command is safe to run more often than its schedule. To disable
digests entirely, leave the scheduler off and schedule no cron entry;
individual users can also set their frequency to `off`.

---

## 6. Database

New tables, all created by
`migrations/versions/a1c4e7b20f31_create_notification_delivery_tables.py`:

| Table                       | Purpose |
| --------------------------- | ------- |
| `notification_preferences`  | One row per user: per-category email/push toggles and digest frequency. Unique on `user_id`. |
| `push_subscriptions`        | Browser Web Push subscriptions. Unique on `endpoint_hash`; indexed on `(user_id, is_active)`. |
| `notification_events`       | One row per logical event. Unique on `event_key` — the idempotency guarantee. Holds the rendering payload. |
| `notification_deliveries`   | Per-channel outcome and retry state. Unique on `(event_id, channel)`. |
| `digest_runs`               | One row per user per digest period. Unique on `(user_id, frequency, period_key)`. |

Every table cascades from `users.id`, so deleting a user removes their
preferences, subscriptions, events, deliveries and digest history. No
existing table or migration was modified.

---

## 7. API

All routes require a valid bearer token and are scoped to that token's
user. Nothing accepts a user id from the request body.

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `GET` | `/api/v1/notifications` | List the caller's notifications (existing) |
| `GET` | `/api/v1/notifications/unread-count` | Unread count (existing) |
| `PATCH` | `/api/v1/notifications/{id}/read` | Mark one read (existing) |
| `PATCH` | `/api/v1/notifications/read-all` | Mark all read (existing) |
| `GET` | `/api/v1/notifications/preferences` | **New.** Read preferences, server capability flags and the public VAPID key |
| `PATCH` | `/api/v1/notifications/preferences` | **New.** Update the caller's own preferences |
| `POST` | `/api/v1/notifications/push/subscribe` | **New.** Register a browser subscription |
| `DELETE` | `/api/v1/notifications/push/unsubscribe` | **New.** Disable a browser subscription the caller owns |

### Security properties

- Notification reads were previously restricted to consumers and
  administrators. SME owners receive `competitor_risk` notifications, so
  they could not read their own inbox; the four existing routes now accept
  any authenticated role. Every query is still filtered by the token's
  `user_id`, so no cross-user data is exposed.
- A notification belonging to another user returns `404`, not `403`, so
  the endpoint does not confirm that the id exists.
- `push/unsubscribe` with somebody else's endpoint returns
  `deactivated: false` and changes nothing.
- A subscription endpoint must be an absolute `https://` URL. The server
  later contacts this URL, so an arbitrary scheme is rejected with `422`.
- Preference updates use `extra="forbid"`, so an unexpected field such as
  `user_id` is rejected with `422`.
- The preferences response exposes only the **public** VAPID key and
  boolean capability flags. The private key, SMTP password and full
  subscription secrets are never returned and never logged.

---

## 8. Delivery tracking and logging

`notification_deliveries` records `channel`
(`in_app` / `email` / `web_push`), `status`
(`pending` / `delivered` / `failed` / `skipped`), `attempts`,
`attempted_at`, `delivered_at` and `failure_reason`.

Structured log events, none of which contain a password, private key or
token:

```
notification.event.created          notification.event.duplicate_skipped
email.delivery.attempted            email.delivery.successful
email.delivery.failed               email.delivery.skipped
push.delivery.successful            push.delivery.failed
push.subscription.registered        push.subscription.invalidated
push.subscription.deactivated       notification.preferences.updated
digest.cycle.started                digest.cycle.finished
digest.delivered                    digest.skipped_empty
digest.skipped_duplicate            digest.delivery.failed
scheduler.started                   scheduler.stopped
```

---

## 9. Manual end-to-end test

### Prerequisites

```bash
cd backend
python -m alembic upgrade head
python -m scripts.generate_vapid_keys   # copy into .env
# start a local SMTP sink
python -m aiosmtpd -n -l 127.0.0.1:1025
# run the API
uvicorn app.main:app --reload
# run the frontend
cd ../frontend && npm run dev
```

### Consumer price alert

1. Open `http://localhost:5173` and log in as a consumer.
2. Go to **Dashboard → Notification Settings**. Confirm price-alert email
   is on.
3. Click **Enable browser notifications** and accept the browser prompt.
   The status should read *Active on 1 device(s)*.
4. Create a price alert on Samsung Galaxy A55 with target `PKR 100,000`.
5. Ingest an observation above the target:

   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/internal/acquisition/listings \
     -H "X-Ingestion-Key: $INGESTION_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{ ... "current_price": 105000 ... }'
   ```

   Expected: `alerts_triggered: 0`, no notification, no email, no push.
6. Ingest the same listing at `97500` with a later `scraped_at`.
7. Verify: the bell shows a new notification, the unread counter
   increments, the SMTP sink printed the price-alert email, and a browser
   notification appeared.
8. Re-post the identical payload (same `scraped_at`). Expected:
   `status: "duplicate"`, no second notification, email or push.
9. Click the browser notification. It must focus the tab and open
   `/products/{id}`.
10. Ingest `96000`. Expected: nothing new — the alert is one-time.

### SME competitor risk

1. Log in as an SME owner and open **SME Workspace**.
2. Add a business product with a selling price and watch a competitor
   listing.
3. In **Notification Settings**, confirm competitor email and push are on.
4. Ingest the competitor listing at a price far below yours. Expected: an
   in-app competitor alert, a competitor email and a browser push.
5. Ingest a slightly different low price. Expected: nothing — risk is
   still high.
6. Ingest a price just below yours (medium risk), then a very low price
   again. Expected: a second alert.

### Digest

1. Set **Digest reports** to *Daily*.
2. Make sure at least one alert triggered yesterday in the configured
   timezone.
3. Run `python -m scripts.run_notification_jobs daily-digest`.
4. Verify the digest arrives in the SMTP sink and that running the
   command again sends nothing.
5. Set the frequency to *Off*, re-run, and verify nothing is sent.

### Existing reporting

Export the SME competitor report as PDF and as Excel from the SME
workspace and confirm both still download and open.

---

## 10. Limitations

- **SMTP provider dependency.** Email delivery depends entirely on the
  configured SMTP server. The automated tests mock the transport, so they
  prove the orchestration, not that a production provider accepts the
  mail. The real `smtplib` path has been verified against a local
  `aiosmtpd` sink (correct headers, multipart body with text fallback and
  an absolute CTA URL), but a real provider's authentication, SPF/DKIM
  and deliverability still need one manual check before release.
- **Bounded retries, no queue.** The project has no Celery or RQ, and none
  was introduced. Retries are bounded by
  `NOTIFICATION_DELIVERY_MAX_ATTEMPTS` and driven by the outbox job. A
  delivery that exhausts its attempts stays `failed` and is not retried
  again automatically; it remains visible in `notification_deliveries`.
- **Synchronous post-commit dispatch.** When an ingestion run triggers
  alerts, the outbox is flushed in the same request. A slow SMTP server
  therefore slows that one ingestion response. Set
  `DIGEST_SCHEDULER_ENABLED=true` (or run the `outbox` cron job) and the
  retry sweep absorbs anything that fails fast.
- **Single scheduler process.** Only one process may run with
  `DIGEST_SCHEDULER_ENABLED=true`. With several enabled workers the unique
  constraints prevent duplicate emails, but the duplicated work is wasted.
- **Digest crash window.** A digest run row is claimed before the email is
  built. If the process dies between claiming and sending, that period is
  recorded as processed and is not retried. The events themselves are not
  lost and appear in the in-app inbox.
- **No per-user timezone.** Digest timing uses one system timezone
  (`DIGEST_TIMEZONE`). Users in other timezones receive their digest at
  the system time.
- **Browser support.** Web Push requires a secure context and is
  unavailable in iOS Safari tabs (Home Screen installs on iOS 16.4+ only).
- **Push verified short of a live endpoint.** VAPID signing and aes128gcm
  encryption run for real in the test suite, and the failure
  classification for 404/410/429/503 is covered. Delivery to an actual
  FCM or Mozilla endpoint has not been exercised automatically and needs
  one manual browser check, documented in section 9.
- **Email address verification.** Email is sent to the account address,
  which is required and unique at registration. VEXTRO has no email
  confirmation flow yet, so `users.is_verified` is not used as a gate.
