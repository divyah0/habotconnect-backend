import logging
from django.db import IntegrityError, transaction
from django.db.models import Q, Prefetch
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Booking_Request, LSA_Profile, Parent, Payment
from .serializers import BookingSerializer, LSASerializer
from .services import create_booking_with_lock

logger = logging.getLogger(__name__)


class BookingCreateAPIView(APIView):
    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        try:
            booking = create_booking_with_lock(
                parent=data["parent"],
                lsa=data["lsa"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                subject=data["subject"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except IntegrityError:
            return Response(
                {"detail": "Booking could not be created due to a database conflict."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            BookingSerializer(booking).data,
            status=status.HTTP_201_CREATED,
        )


class LSASearchAPIView(APIView):
    def get(self, request):
        skill = request.query_params.get("skill", "").strip().lower()
        queryset = LSA_Profile.objects.filter(is_active=True)

        if skill:
            # JSONField contains lookup is supported by Django and MySQL JSON.
            queryset = queryset.filter(skills__contains=[skill])

        # select_related is used when related FK data is needed; here LSA is standalone.
        # The query remains one main database query rather than an N+1 loop.
        queryset = queryset.order_by("id")

        return Response(LSASerializer(queryset, many=True).data)

class PaymentWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        event = request.data

        booking_id = event.get("booking_id")
        payment_status = event.get("status")
        reference = event.get("payment_reference", "").strip()

        if not booking_id:
            return Response(
                {"detail": "booking_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment_status not in ["success", "failure"]:
            return Response(
                {"detail": "status must be either success or failure."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                booking = (
                    Booking_Request.objects
                    .select_for_update()
                    .get(pk=booking_id)
                )

                try:
                    payment = Payment.objects.select_for_update().get(
                        booking=booking
                    )
                except Payment.DoesNotExist:
                    return Response(
                        {"detail": "Payment not found for this booking."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Idempotency:
                # If the payment has already reached a final state,
                # return the current state instead of changing it again.
                if payment.status in [
                    Payment.Status.SUCCESS,
                    Payment.Status.FAILED,
                ]:
                    return Response(
                        {
                            "booking_id": booking.id,
                            "status": booking.status,
                            "payment_status": payment.status,
                        },
                        status=status.HTTP_200_OK,
                    )

                if payment_status == "success":
                    if not reference:
                        return Response(
                            {
                                "detail": (
                                    "payment_reference is required "
                                    "for successful payments."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    payment.status = Payment.Status.SUCCESS
                    payment.external_reference = reference

                    booking.status = Booking_Request.Status.CONFIRMED
                    booking.external_reference = reference

                else:
                    payment.status = Payment.Status.FAILED
                    booking.status = Booking_Request.Status.FAILED

                payment.save(
                    update_fields=[
                        "status",
                        "external_reference",
                        "updated_at",
                    ]
                )

                booking.save(
                    update_fields=[
                        "status",
                        "external_reference",
                        "updated_at",
                    ]
                )

                return Response(
                    {
                        "booking_id": booking.id,
                        "status": booking.status,
                        "payment_status": payment.status,
                    },
                    status=status.HTTP_200_OK,
                )

        except Booking_Request.DoesNotExist:
            return Response(
                {"detail": "Booking not found."},
                status=status.HTTP_404_NOT_FOUND,
            )