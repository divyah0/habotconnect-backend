# HabotConnect – Python Backend Developer Hiring Project

## Overview

This project implements the core backend prototype requested in the HabotConnect hiring exercise:

- Relational booking data model
- Booking creation API
- LSA skill search API
- Double-booking validation
- Mock third-party payment integration boundary
- Payment webhook
- Automated tests
- GitHub Actions CI
- API and architecture documentation

## Architecture

The project follows Django's **MVT architecture**. Django handles routing and persistence, Django REST Framework handles serialization/HTTP APIs, and a small service layer contains booking business logic that benefits from transaction handling.

```text
Client
  |
  v
Django URL Router
  |
  +--> Booking API ----> Serializer ----> Service/Transaction ----> ORM ----> DB
  |
  +--> LSA Search ------> Serializer -----------------------------> ORM ----> DB
  |
  +--> Payment Webhook -------------------------------------------> ORM ----> DB
```

## Data Model

Core entities:

- `Parent`
- `LSA_Profile`
- `Booking_Request`

Relationships:

- One Parent can have many Booking Requests.
- One LSA Profile can have many Booking Requests.
- A Booking Request belongs to exactly one Parent and one LSA.

`skills` is stored as a JSON array in `LSA_Profile` to keep the assessment implementation to the requested three core entities while still allowing skill-based filtering.

## API Endpoints

### 1. Create booking

`POST /api/v1/bookings/`

Request:

```json
{
  "parent_id": 1,
  "lsa_id": 1,
  "start_time": "2026-08-20T10:00:00+05:30",
  "end_time": "2026-08-20T11:00:00+05:30",
  "subject": "Reading support"
}
```

The API validates:

- Parent and active LSA exist
- End time is after start time
- Start time is not in the past
- The requested LSA has no overlapping active booking

### 2. Search LSAs

`GET /api/v1/lsas/search/?skill=reading`

Returns active LSAs whose skills contain the requested skill.

The endpoint serializes the queryset directly rather than fetching each record inside a Python loop, avoiding the classic N+1 pattern.

### 3. Payment webhook

`POST /api/v1/payments/webhook/`

Success example:

```json
{
  "booking_id": 1,
  "status": "success",
  "payment_reference": "PAY-123"
}
```

A successful event moves the booking to `CONFIRMED`; a failed event moves it to `FAILED`.

## Double-booking protection

The booking service:

1. Opens an atomic database transaction.
2. Locks the selected LSA row with `select_for_update()`.
3. Re-checks for an overlapping active booking.
4. Creates the booking only when the time range is still free.

Overlap rule:

```text
existing.start < requested.end
AND
existing.end > requested.start
```

This is important because checking only in the serializer is vulnerable to two requests arriving at nearly the same time.

## Mock external integration

`bookings/services.py` contains a mock payment call using `requests.post()` with:

- timeout
- `raise_for_status()`
- `RequestException` handling
- logging

The URL is intentionally a placeholder because the assessment asks for a mock external service rather than a real payment provider.

## Testing

Run:

```bash
pytest -q
```

The test suite covers:

1. Successful booking
2. Invalid time range
3. Overlapping booking
4. LSA skill search
5. Inactive LSA exclusion
6. Payment webhook confirmation

## Local setup

### 1. Create virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install packages

```bash
pip install -r requirements.txt
```

### 3. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Run tests

```bash
pytest -q
```

### 5. Start server

```bash
python manage.py runserver
```

## MySQL

For the final submission, MySQL can be used by setting the environment variables in `.env.example`.

You may also install the MySQL Python driver if your local environment requires it:

```bash
pip install mysqlclient
```

Then create the database and configure:

```text
DB_ENGINE=django.db.backends.mysql
DB_NAME=habot_booking
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

## Git workflow

Suggested workflow:

```bash
git checkout -b feature/booking-api
git add .
git commit -m "Implement booking API"
git push origin feature/booking-api
```

Open a pull request after the tests pass.

## CI/CD

GitHub Actions runs on every push and pull request:

1. Checks out the repository
2. Installs Python
3. Installs dependencies
4. Applies migrations
5. Runs pytest

Workflow:

`.github/workflows/tests.yml`

## Production considerations

For a production implementation, I would additionally add:

- authenticated API access
- webhook signature verification
- idempotency keys for payment events
- PostgreSQL exclusion constraints where appropriate
- structured logging
- rate limiting
- API versioning
- secrets stored outside source control
- monitoring and alerting
