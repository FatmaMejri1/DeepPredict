import json
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.models import ActionType
from audit.services import log_action
from ml_models.models import MLModelVersion, ModelType


class Command(BaseCommand):
    help = "Register and activate models from ai-service/models/config.json into the database."

    def handle(self, *args, **options):
        config_path = settings.AI_ARTIFACTS_DIR / "config.json"
        if not config_path.exists():
            raise CommandError(f"Model config not found at {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        version = cfg["version"]
        trained_at = datetime(2026, 10, 24, tzinfo=timezone.utc)

        with transaction.atomic():
            previously_active_ids = set(
                MLModelVersion.objects.filter(is_active=True).values_list("pk", flat=True)
            )
            MLModelVersion.objects.filter(model_type=ModelType.FAILURE_PREDICTION).update(is_active=False)
            risk_model, _ = MLModelVersion.objects.update_or_create(
                name="Disk failure risk",
                version=version,
                defaults={
                    "model_type": ModelType.FAILURE_PREDICTION,
                    "architecture": "GRU",
                    "training_dataset": cfg.get("training_data", "Backblaze Drive Stats"),
                    "trained_at": trained_at,
                    "thresholds": cfg.get("thresholds", {}).get("risk", {}),
                    "evaluation_metrics": {
                        "protocol": cfg.get("evaluation", {}).get("protocol", ""),
                        "results": cfg.get("evaluation", {}).get("risk", {}),
                    },
                    "config": {"feature_cols": cfg.get("feature_cols", [])},
                    "is_active": True,
                },
            )

            MLModelVersion.objects.filter(model_type=ModelType.ANOMALY_DETECTION).update(is_active=False)
            anomaly_model, _ = MLModelVersion.objects.update_or_create(
                name="Disk anomaly",
                version=version,
                defaults={
                    "model_type": ModelType.ANOMALY_DETECTION,
                    "architecture": "LSTM_AUTOENCODER",
                    "training_dataset": cfg.get("training_data", "Backblaze Drive Stats"),
                    "trained_at": trained_at,
                    "thresholds": {"anomaly": cfg.get("thresholds", {}).get("anomaly")},
                    "evaluation_metrics": {
                        "protocol": cfg.get("evaluation", {}).get("protocol", ""),
                        "results": cfg.get("evaluation", {}).get("anomaly", {}),
                    },
                    "config": {"feature_cols": cfg.get("feature_cols", [])},
                    "is_active": True,
                },
            )

            affected_ids = previously_active_ids | {risk_model.pk, anomaly_model.pk}
            affected_models = MLModelVersion.objects.filter(pk__in=affected_ids)
            for model in affected_models:
                log_action(
                    action=ActionType.CONFIG_CHANGE,
                    user="system",
                    resource_type="MLModelVersion",
                    resource_id=str(model.pk),
                    details={
                        "action": "activate" if model.is_active else "deactivate",
                        "source": "register_models",
                        "model_type": model.model_type,
                        "version": model.version,
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully registered and activated models: {risk_model} and {anomaly_model}"
        ))
