from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LSA_Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("skills", models.JSONField(default=list)),
                ("hourly_rate", models.DecimalField(decimal_places=2, max_digits=10)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"indexes": [models.Index(fields=["is_active"], name="bookings_lsa_is_acti_9d3a1e_idx")]},
        ),
        migrations.CreateModel(
            name="Parent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("phone", models.CharField(blank=True, max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name="Booking_Request",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField()),
                ("subject", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("PENDING","Pending"),("PAYMENT_PENDING","Payment Pending"),("CONFIRMED","Confirmed"),("FAILED","Failed"),("CANCELLED","Cancelled")], default="PENDING", max_length=30)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("external_reference", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("lsa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="bookings.lsa_profile")),
                ("parent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings", to="bookings.parent")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["lsa", "start_time", "end_time"], name="bookings_boo_lsa_id_4b9d5f_idx"),
                    models.Index(fields=["status"], name="bookings_boo_status_6e4db6_idx"),
                ],
            },
        ),
    ]
