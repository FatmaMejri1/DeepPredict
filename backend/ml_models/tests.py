import json
from io import StringIO
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from audit.models import ActionType, AuditLog
from .models import MLModelVersion


class RegisterModelsAuditTests(TestCase):
    def _run_register_command(self, artifact_dir):
        config_path = Path(artifact_dir) / "config.json"
        config_path.write_text(json.dumps({
            "version": "audit-test-v1",
            "training_data": "Backblaze Drive Stats",
            "thresholds": {"risk": {"high": 0.6}, "anomaly": 0.05},
            "evaluation": {"protocol": "test", "risk": {}, "anomaly": {}},
            "feature_cols": ["smart_5_raw"],
        }), encoding="utf-8")
        with patch.object(settings, "AI_ARTIFACTS_DIR", Path(artifact_dir)):
            call_command("register_models", stdout=StringIO())

    def test_registration_records_system_configuration_events(self):
        with tempfile.TemporaryDirectory(dir=settings.BASE_DIR) as artifact_dir:
            self._run_register_command(artifact_dir)

        events = AuditLog.objects.filter(action=ActionType.CONFIG_CHANGE)
        self.assertEqual(events.count(), 2)
        self.assertEqual(set(events.values_list("username", flat=True)), {"system"})
        self.assertEqual(set(events.values_list("details__source", flat=True)), {"register_models"})

    def test_registration_rolls_back_when_audit_write_fails(self):
        with tempfile.TemporaryDirectory(dir=settings.BASE_DIR) as artifact_dir:
            config_path = Path(artifact_dir) / "config.json"
            config_path.write_text(json.dumps({
                "version": "audit-fail-v1", "training_data": "test",
                "thresholds": {"risk": {}, "anomaly": 0.05},
                "evaluation": {"protocol": "test", "risk": {}, "anomaly": {}},
                "feature_cols": [],
            }), encoding="utf-8")
            with patch.object(settings, "AI_ARTIFACTS_DIR", Path(artifact_dir)), patch(
                "ml_models.management.commands.register_models.log_action",
                side_effect=IntegrityError("audit unavailable"),
            ):
                with self.assertRaises(IntegrityError):
                    call_command("register_models", stdout=StringIO())
        self.assertEqual(MLModelVersion.objects.count(), 0)

# Create your tests here.
