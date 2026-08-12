import logging
import requests
from django.db import transaction
from .models import Booking_Request, Payment
logger = logging.getLogger(__name__)


def create_mock_payment(booking):
    """
    Mock payment integration.
    In production this would call a real payment gateway.
    """
    url = "https://example.invalid/mock-payment"
    payload = {
        "booking_id": booking.id,
        "amount": str(booking.amount),
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()

        data = response.json()
        reference = data.get("reference")

        if not reference:
            raise ValueError("Payment reference missing from response.")

        payment = Payment.objects.create(
            booking=booking,
            provider="MOCK",
            external_reference=reference,
            amount=booking.amount,
            status=Payment.Status.PENDING,
        )

        logger.info(
            "Payment created for booking %s with reference %s",
            booking.id,
            reference,
        )

        return payment

    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            "Mock payment request failed for booking %s: %s",
            booking.id,
            exc,
        )
        raise


@transaction.atomic
def create_booking_with_lock(*, parent, lsa, start_time, end_time, subject):
    """
    Re-checks overlap while holding a row lock on the LSA.
    This reduces the race window between concurrent booking requests.
    """
    from .models import LSA_Profile

    locked_lsa = LSA_Profile.objects.select_for_update().get(pk=lsa.pk)

    overlap = Booking_Request.objects.filter(
        lsa=locked_lsa,
        start_time__lt=end_time,
        end_time__gt=start_time,
        status__in=[
            Booking_Request.Status.PENDING,
            Booking_Request.Status.PAYMENT_PENDING,
            Booking_Request.Status.CONFIRMED,
        ],
    ).exists()

    if overlap:
        raise ValueError("The selected LSA is already booked for the requested time.")

    booking = Booking_Request.objects.create(
    parent=parent,
    lsa=locked_lsa,
    start_time=start_time,
    end_time=end_time,
    subject=subject,
    amount=locked_lsa.hourly_rate,
    status=Booking_Request.Status.PAYMENT_PENDING,
)

    create_mock_payment(booking)

    return booking