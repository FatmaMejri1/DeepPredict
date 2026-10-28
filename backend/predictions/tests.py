from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import TestCase

from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions import services
from predictions.inference_client import InferenceError, NotEnoughHistory
from predictions.models import Prediction


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
        self.drive = Resource.objects.create(name="d", identifier="D1", resource_type=ResourceType.DISK)
        for n in range(20):
            Metric.objects.create(resource=self.drive, timestamp=day(n), values={"smart_5_raw": n})

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
        for level, status in [("LOW", Status.HEALTHY), ("MEDIUM", Status.WARNING), ("HIGH", Status.HIGH_RISK)]:
            Prediction.objects.all().delete()
            predict.return_value = fake_answer(level)
            services.predict_resource(self.drive)
            self.drive.refresh_from_db()
            self.assertEqual(self.drive.status, status)

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
        self.assertEqual(sent[-1]["date"], day(9).strftime("%Y-%m-%d"))
        self.assertEqual(sent[-1]["smart_5_raw"], 9)

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
