from django.db import models


class Parent(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name


class LSA_Profile(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    skills = models.JSONField(default=list)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name


class Booking_Request(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAYMENT_PENDING = "PAYMENT_PENDING", "Payment Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name="bookings")
    lsa = models.ForeignKey(LSA_Profile, on_delete=models.PROTECT, related_name="bookings")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    external_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["lsa", "start_time", "end_time"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Booking #{self.pk} - {self.lsa.name}"

class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    booking = models.OneToOneField(
        Booking_Request,
        on_delete=models.CASCADE,
        related_name="payment",
    )
    provider = models.CharField(max_length=50, default="MOCK")
    external_reference = models.CharField(
        max_length=120,
        unique=True,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["external_reference"]),
        ]

    def __str__(self):
        return f"Payment #{self.pk} - Booking #{self.booking_id}"