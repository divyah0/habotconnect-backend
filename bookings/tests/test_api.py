import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APIClient
from bookings.models import Booking_Request, LSA_Profile, Parent, Payment
from unittest.mock import patch
pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def parent():
    return Parent.objects.create(
        name="Test Parent", email="parent@example.com", phone="9999999999"
    )


@pytest.fixture
def lsa():
    return LSA_Profile.objects.create(
        name="Test LSA",
        email="lsa@example.com",
        skills=["reading", "math"],
        hourly_rate=Decimal("500.00"),
        is_active=True,
    )


def future_window():
    start = timezone.now() + timedelta(days=1)
    return start, start + timedelta(hours=1)

@patch("bookings.services.requests.post")
def test_create_booking_success(mock_post, client, parent, lsa):
    mock_post.return_value.status_code = 200
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {
        "reference": "MOCK-PAY-001"
    }

    start, end = future_window()

    response = client.post("/api/v1/bookings/", {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "subject": "Reading session",
    }, format="json")

    assert response.status_code == 201
    assert response.data["status"] == "PAYMENT_PENDING"
    assert Booking_Request.objects.count() == 1

    payment = Payment.objects.get(
        booking_id=response.data["id"]
    )

    assert payment.provider == "MOCK"
    assert payment.external_reference == "MOCK-PAY-001"
    assert payment.amount == Decimal("500.00")
    assert payment.status == Payment.Status.PENDING

    mock_post.assert_called_once()

def test_booking_rejects_invalid_time(client, parent, lsa):
    start = timezone.now() + timedelta(days=1)
    response = client.post("/api/v1/bookings/", {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "start_time": start.isoformat(),
        "end_time": start.isoformat(),
        "subject": "Invalid",
    }, format="json")

    assert response.status_code == 400


def test_booking_rejects_overlap(client, parent, lsa):
    start, end = future_window()
    Booking_Request.objects.create(
        parent=parent, lsa=lsa, start_time=start, end_time=end,
        subject="Existing", amount=500, status=Booking_Request.Status.CONFIRMED
    )

    response = client.post("/api/v1/bookings/", {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "start_time": (start + timedelta(minutes=15)).isoformat(),
        "end_time": (end + timedelta(minutes=15)).isoformat(),
        "subject": "Overlap",
    }, format="json")

    assert response.status_code == 400


def test_lsa_search_filters_by_skill(client, lsa):
    response = client.get("/api/v1/lsas/search/?skill=reading")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == lsa.id


def test_lsa_search_excludes_inactive(client):
    LSA_Profile.objects.create(
        name="Inactive", email="inactive@example.com",
        skills=["reading"], hourly_rate=300, is_active=False
    )
    response = client.get("/api/v1/lsas/search/?skill=reading")
    assert response.status_code == 200
    assert response.data == []

def test_payment_webhook_confirms_booking(client, parent, lsa):
    start, end = future_window()

    booking = Booking_Request.objects.create(
        parent=parent,
        lsa=lsa,
        start_time=start,
        end_time=end,
        subject="Math",
        amount=500,
        status=Booking_Request.Status.PAYMENT_PENDING,
    )

    payment = Payment.objects.create(
        booking=booking,
        provider="MOCK",
        external_reference="TEMP-PAY-123",
        amount=500,
        status=Payment.Status.PENDING,
    )

    response = client.post(
        "/api/v1/payments/webhook/",
        {
            "booking_id": booking.id,
            "status": "success",
            "payment_reference": "PAY-123",
        },
        format="json",
    )

    booking.refresh_from_db()
    payment.refresh_from_db()

    assert response.status_code == 200
    assert booking.status == Booking_Request.Status.CONFIRMED
    assert booking.external_reference == "PAY-123"

    assert payment.status == Payment.Status.SUCCESS
    assert payment.external_reference == "PAY-123"


def test_payment_webhook_failure(client, parent, lsa):
    start, end = future_window()

    booking = Booking_Request.objects.create(
        parent=parent,
        lsa=lsa,
        start_time=start,
        end_time=end,
        subject="Math",
        amount=500,
        status=Booking_Request.Status.PAYMENT_PENDING,
    )

    payment = Payment.objects.create(
        booking=booking,
        provider="MOCK",
        external_reference="TEMP-FAIL-001",
        amount=500,
        status=Payment.Status.PENDING,
    )

    response = client.post(
        "/api/v1/payments/webhook/",
        {
            "booking_id": booking.id,
            "status": "failure",
            "payment_reference": "",
        },
        format="json",
    )

    booking.refresh_from_db()
    payment.refresh_from_db()

    assert response.status_code == 200
    assert booking.status == Booking_Request.Status.FAILED
    assert payment.status == Payment.Status.FAILED

def test_payment_webhook_is_idempotent(client, parent, lsa):
    start, end = future_window()

    booking = Booking_Request.objects.create(
        parent=parent,
        lsa=lsa,
        start_time=start,
        end_time=end,
        subject="Math",
        amount=500,
        status=Booking_Request.Status.PAYMENT_PENDING,
    )

    payment = Payment.objects.create(
        booking=booking,
        provider="MOCK",
        external_reference="TEMP-IDEM-001",
        amount=500,
        status=Payment.Status.PENDING,
    )

    payload = {
        "booking_id": booking.id,
        "status": "success",
        "payment_reference": "PAY-IDEM-001",
    }

    first_response = client.post(
        "/api/v1/payments/webhook/",
        payload,
        format="json",
    )

    second_response = client.post(
        "/api/v1/payments/webhook/",
        payload,
        format="json",
    )

    booking.refresh_from_db()
    payment.refresh_from_db()

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert booking.status == Booking_Request.Status.CONFIRMED
    assert payment.status == Payment.Status.SUCCESS
    assert payment.external_reference == "PAY-IDEM-001"

def test_payment_webhook_requires_booking_id(client):
    response = client.post(
        "/api/v1/payments/webhook/",
        {
            "status": "success",
            "payment_reference": "PAY-001",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["detail"] == "booking_id is required."

def test_payment_webhook_rejects_invalid_status(client):
    response = client.post(
        "/api/v1/payments/webhook/",
        {
            "booking_id": 999999,
            "status": "pending",
            "payment_reference": "PAY-002",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "status must be either success or failure." in response.data["detail"]

def test_payment_webhook_requires_reference_for_success(
    client, parent, lsa
):
    start, end = future_window()

    booking = Booking_Request.objects.create(
        parent=parent,
        lsa=lsa,
        start_time=start,
        end_time=end,
        subject="Math",
        amount=500,
        status=Booking_Request.Status.PAYMENT_PENDING,
    )

    Payment.objects.create(
        booking=booking,
        provider="MOCK",
        external_reference="TEMP-REF-001",
        amount=500,
        status=Payment.Status.PENDING,
    )

    response = client.post(
        "/api/v1/payments/webhook/",
        {
            "booking_id": booking.id,
            "status": "success",
            "payment_reference": "",
        },
        format="json",
    )

    assert response.status_code == 400

def test_payment_webhook_unknown_booking(client):
    response = client.post(
        "/api/v1/payments/webhook/",
        {
            "booking_id": 999999,
            "status": "success",
            "payment_reference": "PAY-404",
        },
        format="json",
    )

    assert response.status_code == 404
    assert response.data["detail"] == "Booking not found."

def test_payment_webhook_missing_payment(client, parent, lsa):
    start, end = future_window()

    booking = Booking_Request.objects.create(
        parent=parent,
        lsa=lsa,
        start_time=start,
        end_time=end,
        subject="Math",
        amount=500,
        status=Booking_Request.Status.PAYMENT_PENDING,
    )

    response = client.post(
        "/api/v1/payments/webhook/",
        {
            "booking_id": booking.id,
            "status": "success",
            "payment_reference": "PAY-NO-PAYMENT",
        },
        format="json",
    )

    assert response.status_code == 404
    assert response.data["detail"] == "Payment not found for this booking."