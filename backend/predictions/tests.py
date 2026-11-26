from datetime import datetime, timedelta, timezone as dt_timezone
from io import BytesIO
from urllib.error import HTTPError
from unittest import mock

from django.test import TestCase
from django.db import IntegrityError

from accounts.models import Role, User
from audit.models import ActionType, AuditLog
from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions import services
from predictions.inference_client import (
    DriveModelCompatibilityError,
    InferenceError,
    NotEnoughHistory,
    predict as call_ai_service,
)
from predictions.models import Prediction

SUPPORTED_DRIVE_MODEL = "ST12000NM0008"


def day(n):
    return datetime(2026, 6, 1, tzinfo=dt_timezone.utc) + timedelta(days=n)


def fake_answer(level="HIGH", end=19, version="v1"):
    return {"risk_score": 0.9, "risk_level": level, "horizon_days": 7, "anomaly_score": 0.3,
            "is_anomalous": True, "window_start": day(end - 13).strftime("%Y-%m-%dT00:00:00"),
            "window_end": day(end).strftime("%Y-%m-%dT00:00:00"), "model_version": version}


class PredictionServiceTests(TestCase):
    def setUp(self):
        base = dict(architecture="x", version="v1", training_dataset="t", trained_at=day(0), is_active=True)
        MLModelVersion.objects.create(name="risk", model_type=ModelType.FAILURE_PREDICTION, **base)
        MLModelVersion.objects.create(name="ano", model_type=ModelType.ANOMALY_DETECTION, **base)
        self.drive = Resource.objects.create(
            name="d",
            identifier="D1",
            resource_type=ResourceType.DISK,
            attributes={"drive_model": SUPPORTED_DRIVE_MODEL},
        )
        for n in range(20):
            Metric.objects.create(resource=self.drive, timestamp=day(n), values={"smart_5_raw": n})

    def add_metric_metadata(self, key, value):
        for metric in Metric.objects.filter(resource=self.drive):
            metric.values[key] = value
            metric.save(update_fields=["values"])

    @mock.patch("predictions.services.inference_client.predict")
    def test_saves_two_predictions_and_updates_status(self, predict):
        predict.return_value = fake_answer("CRITICAL")
        risk, anomaly = services.predict_resource(self.drive)
        self.assertEqual(Prediction.objects.count(), 2)
        self.assertEqual(risk.risk_level, "CRITICAL")
        self.assertTrue(anomaly.is_anomalous)
        self.drive.refresh_from_db()
        self.assertEqual(self.drive.status, Status.HIGH_RISK)                  # CRITICAL -> HIGH_RISK

    @mock.patch("predictions.services.inference_client.predict")
    def test_level_to_status_mapping(self, predict):
        for level, status in [
            ("LOW", Status.HEALTHY),
            ("MEDIUM", Status.WARNING),
            ("HIGH", Status.HIGH_RISK),
            ("CRITICAL", Status.HIGH_RISK),
        ]:
            Prediction.objects.all().delete()
            predict.return_value = fake_answer(level)
            services.predict_resource(self.drive)
            self.drive.refresh_from_db()
            self.assertEqual(self.drive.status, status)

    @mock.patch("predictions.services.inference_client.predict")
    def test_anomaly_result_does_not_change_drive_status(self, predict):
        for is_anomalous in (True, False):
            Prediction.objects.all().delete()
            self.drive.status = Status.HIGH_RISK
            self.drive.save(update_fields=["status"])
            answer = fake_answer("MEDIUM")
            answer["is_anomalous"] = is_anomalous
            predict.return_value = answer

            services.predict_resource(self.drive)

            self.drive.refresh_from_db()
            self.assertEqual(self.drive.status, Status.WARNING)

    @mock.patch("predictions.services.inference_client.predict")
    def test_up_to_date_drive_is_skipped(self, predict):
        predict.return_value = fake_answer()
        services.predict_resource(self.drive)
        self.assertIsNone(services.predict_resource(self.drive))
        self.assertEqual(predict.call_count, 1)                                 # the AI was not called again
        self.assertEqual(Prediction.objects.count(), 2)

    @mock.patch("predictions.services.inference_client.predict")
    def test_as_of_only_sends_readings_up_to_that_day(self, predict):
        predict.return_value = fake_answer(end=9)
        services.predict_resource(self.drive, as_of=day(9).date())
        sent = predict.call_args[0][0]
        self.assertEqual(len(sent), 10)
        self.assertEqual(sent[0]["date"], day(0).strftime("%Y-%m-%d"))
        self.assertEqual(sent[-1]["date"], day(9).strftime("%Y-%m-%d"))
        self.assertEqual(sent[-1]["smart_5_raw"], 9)
        self.assertTrue(all(row["model"] == SUPPORTED_DRIVE_MODEL for row in sent))

    @mock.patch("predictions.services.inference_client.predict")
    def test_forwards_drive_model_and_full_history_without_truncation(self, predict):
        predict.return_value = fake_answer()

        services.predict_resource(self.drive)

        sent = predict.call_args[0][0]
        self.assertEqual(len(sent), 20)
        self.assertEqual(sent[0]["date"], day(0).strftime("%Y-%m-%d"))
        self.assertEqual(sent[-1]["date"], day(19).strftime("%Y-%m-%d"))
        self.assertEqual(sent[-1]["smart_5_raw"], 19)
        self.assertTrue(all(row["model"] == SUPPORTED_DRIVE_MODEL for row in sent))

    @mock.patch("predictions.services.inference_client.predict")
    def test_metric_model_cannot_override_resource_model(self, predict):
        self.add_metric_metadata("model", "UNSUPPORTED-METRIC-MODEL")
        predict.return_value = fake_answer()

        services.predict_resource(self.drive)

        sent = predict.call_args[0][0]
        self.assertTrue(all(row["model"] == SUPPORTED_DRIVE_MODEL for row in sent))
        self.assertTrue(all("drive_model" not in row for row in sent))
        self.assertEqual(sent[-1]["smart_5_raw"], 19)

    @mock.patch("predictions.services.inference_client.predict")
    def test_metric_drive_model_cannot_substitute_for_resource_model(self, predict):
        self.add_metric_metadata("drive_model", SUPPORTED_DRIVE_MODEL)
        self.drive.attributes = {"drive_model": "UNSUPPORTED-RESOURCE-MODEL"}
        self.drive.save(update_fields=["attributes"])
        predict.return_value = fake_answer()

        services.predict_resource(self.drive)

        sent = predict.call_args[0][0]
        self.assertTrue(all(row["model"] == "UNSUPPORTED-RESOURCE-MODEL" for row in sent))
        self.assertTrue(all("drive_model" not in row for row in sent))

    @mock.patch("predictions.services.inference_client.predict")
    def test_supported_metric_model_cannot_make_unsupported_resource_compatible(self, predict):
        self.add_metric_metadata("model", SUPPORTED_DRIVE_MODEL)
        self.drive.attributes = {"drive_model": "UNSUPPORTED-RESOURCE-MODEL"}
        self.drive.save(update_fields=["attributes"])

        def reject_unsupported_resource(readings):
            self.assertTrue(all(row["model"] == "UNSUPPORTED-RESOURCE-MODEL" for row in readings))
            raise InferenceError("unsupported drive model")

        predict.side_effect = reject_unsupported_resource

        with self.assertRaises(InferenceError):
            services.predict_resource(self.drive)

        self.assertEqual(Prediction.objects.filter(resource=self.drive).count(), 0)

    @mock.patch("predictions.services.inference_client.predict")
    def test_missing_drive_model_is_not_replaced_with_a_supported_model(self, predict):
        self.add_metric_metadata("model", SUPPORTED_DRIVE_MODEL)
        self.add_metric_metadata("drive_model", SUPPORTED_DRIVE_MODEL)
        self.drive.attributes = {}
        self.drive.save(update_fields=["attributes"])

        with self.assertRaises(DriveModelCompatibilityError):
            services.predict_resource(self.drive)

        predict.assert_not_called()
        self.assertEqual(Prediction.objects.filter(resource=self.drive).count(), 0)

    def test_ai_compatibility_422_is_reported_as_a_validation_error(self):
        body = (
            b'{"detail":{"message":"Dataset validation failed or drive model '
            b'compatibility could not be verified. Prediction was not performed."}}'
        )
        error = HTTPError("http://ai-service/predict", 422, "Unprocessable Entity", {}, BytesIO(body))

        with mock.patch("predictions.inference_client.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(DriveModelCompatibilityError):
                call_ai_service([{"date": day(19).strftime("%Y-%m-%d"), "model": "UNSUPPORTED"}])

    @mock.patch("predictions.services.inference_client.predict")
    def test_not_enough_history_saves_nothing(self, predict):
        predict.side_effect = NotEnoughHistory("not enough valid history")
        with self.assertRaises(NotEnoughHistory):
            services.predict_resource(self.drive)
        self.assertEqual(Prediction.objects.count(), 0)

    @mock.patch("predictions.services.inference_client.predict")
    def test_wrong_model_version_is_rejected(self, predict):
        predict.return_value = fake_answer(version="other")
        with self.assertRaises(InferenceError):
            services.predict_resource(self.drive)
        self.assertEqual(Prediction.objects.count(), 0)

    def test_no_active_model(self):
        MLModelVersion.objects.update(is_active=False)
        with self.assertRaises(InferenceError):
            services.predict_resource(self.drive)

    def test_drive_without_readings(self):
        empty = Resource.objects.create(name="e", identifier="E1", resource_type=ResourceType.DISK)
        self.assertIsNone(services.predict_resource(empty))

    @mock.patch("predictions.services.log_action", side_effect=IntegrityError("audit unavailable"))
    @mock.patch("predictions.services.inference_client.predict")
    def test_prediction_and_status_roll_back_when_audit_fails(self, predict, _log_action):
        predict.return_value = fake_answer("HIGH")
        with self.assertRaises(IntegrityError):
            services.predict_resource(self.drive)
        self.drive.refresh_from_db()
        self.assertEqual(self.drive.status, Status.HEALTHY)
        self.assertEqual(Prediction.objects.filter(resource=self.drive).count(), 0)

    @mock.patch("predictions.services.inference_client.predict")
    def test_prediction_audit_records_api_actor(self, predict):
        predict.return_value = fake_answer("MEDIUM")
        actor = User.objects.create_user(
            username="prediction_actor", email="prediction_actor@example.com",
            password="safe-test-password", role=Role.IT_PRO,
        )
        services.predict_resource(self.drive, actor=actor, source="api")
        event = AuditLog.objects.get(action=ActionType.PREDICT_RUN, resource_id=str(self.drive.pk))
        self.assertEqual(event.user, actor)
        self.assertEqual(event.details["source"], "api")

    @mock.patch("predictions.services.inference_client.predict")
    def test_prediction_audit_records_system_source_without_user(self, predict):
        predict.return_value = fake_answer("LOW")
        services.predict_resource(self.drive, actor="system", source="run_predictions")
        event = AuditLog.objects.get(action=ActionType.PREDICT_RUN, resource_id=str(self.drive.pk))
        self.assertIsNone(event.user)
        self.assertEqual(event.username, "system")
        self.assertEqual(event.details["source"], "run_predictions")
