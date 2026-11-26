from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("alerts", "0001_initial")]

    operations = [
        migrations.RemoveConstraint(
            model_name="alert",
            name="alert_clear_count_at_most_two",
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.CheckConstraint(
                condition=(
                    Q(status__in=("OPEN", "ACKNOWLEDGED"), consecutive_clear_count__lte=1)
                    | Q(status="RESOLVED", consecutive_clear_count__lte=2)
                ),
                name="alert_clear_count_at_most_two",
            ),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.CheckConstraint(
                condition=(
                    Q(
                        status="OPEN",
                        acknowledged_at__isnull=True,
                        acknowledged_by__isnull=True,
                        resolved_at__isnull=True,
                        resolved_by__isnull=True,
                        resolution_source="",
                    )
                    | Q(
                        status="ACKNOWLEDGED",
                        acknowledged_at__isnull=False,
                        resolved_at__isnull=True,
                        resolved_by__isnull=True,
                        resolution_source="",
                    )
                    | Q(
                        status="RESOLVED",
                        resolved_at__isnull=False,
                        resolution_source="AUTO",
                        consecutive_clear_count=2,
                    )
                    | Q(
                        status="RESOLVED",
                        resolved_at__isnull=False,
                        resolution_source="USER",
                    )
                ),
                name="alert_lifecycle_fields_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.CheckConstraint(
                condition=Q(acknowledged_by__isnull=True) | Q(acknowledged_at__isnull=False),
                name="alert_ack_actor_requires_time",
            ),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.CheckConstraint(
                condition=Q(resolved_by__isnull=True) | Q(resolution_source="USER"),
                name="alert_resolver_requires_user_source",
            ),
        ),
    ]
