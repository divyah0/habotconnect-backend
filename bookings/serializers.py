from django.utils import timezone
from rest_framework import serializers
from .models import Booking_Request, LSA_Profile, Parent


class ParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parent
        fields = ["id", "name", "email", "phone"]


class LSASerializer(serializers.ModelSerializer):
    class Meta:
        model = LSA_Profile
        fields = ["id", "name", "email", "skills", "hourly_rate", "is_active"]


class BookingSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent", queryset=Parent.objects.all(), write_only=True
    )
    lsa_id = serializers.PrimaryKeyRelatedField(
        source="lsa", queryset=LSA_Profile.objects.filter(is_active=True), write_only=True
    )
    parent = ParentSerializer(read_only=True)
    lsa = LSASerializer(read_only=True)

    class Meta:
        model = Booking_Request
        fields = [
            "id", "parent_id", "lsa_id", "parent", "lsa",
            "start_time", "end_time", "subject", "status",
            "amount", "external_reference", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "external_reference", "amount", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs["start_time"]
        end = attrs["end_time"]
        if start >= end:
            raise serializers.ValidationError("end_time must be after start_time.")
        if start < timezone.now():
            raise serializers.ValidationError("start_time cannot be in the past.")

        lsa = attrs["lsa"]
        if not lsa.is_active:
            raise serializers.ValidationError("Selected LSA is inactive.")

        # Fast pre-check; the service layer repeats this under a transaction/lock.
        overlap = Booking_Request.objects.filter(
            lsa=lsa,
            start_time__lt=end,
            end_time__gt=start,
            status__in=[
                Booking_Request.Status.PENDING,
                Booking_Request.Status.PAYMENT_PENDING,
                Booking_Request.Status.CONFIRMED,
            ],
        ).exists()
        if overlap:
            raise serializers.ValidationError(
                "The selected LSA is already booked for the requested time."
            )

        return attrs

    def create(self, validated_data):
        validated_data["amount"] = validated_data["lsa"].hourly_rate
        return Booking_Request.objects.create(**validated_data)
