# API examples for presentation/demo

## Create booking

POST /api/v1/bookings/

```json
{
  "parent_id": 1,
  "lsa_id": 1,
  "start_time": "2026-08-20T10:00:00+05:30",
  "end_time": "2026-08-20T11:00:00+05:30",
  "subject": "Reading support"
}
```

Expected success: HTTP 201.

## Overlap

Send another request for the same LSA with:

```text
start_time = 2026-08-20T10:30:00+05:30
end_time   = 2026-08-20T11:30:00+05:30
```

Expected result: HTTP 400 from serializer validation; concurrent race protection is handled again in the transactional service.

## Search

GET /api/v1/lsas/search/?skill=reading

Expected result: active LSAs containing "reading".

## Webhook

POST /api/v1/payments/webhook/

```json
{
  "booking_id": 1,
  "status": "success",
  "payment_reference": "PAY-123"
}
```

Expected result: booking status becomes CONFIRMED.
