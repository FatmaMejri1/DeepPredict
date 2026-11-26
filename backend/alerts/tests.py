from datetime import datetime, timedelta, timezone as dt_timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import mock

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient

from accounts.models import Role, User
from alerts.models import Alert, AlertSeverity, AlertStatus, AlertType
from infrastructure.models import Resource, ResourceType, Status
from ml_models.models import MLModelVersion, ModelType
from monitoring.models import Metric
from predictions import services
from predictions.inference_client import InferenceError, NotEnoughHistory
from predictions.models import Prediction


def day(n):
    return datetime(2026, 6, 1, tzinfo=dt_timezone.utc) + timedelta(days=n)


def prediction_answer(level="HIGH", anomalous=True, end=19):
    return {
        "risk_score": 0.9,
        "risk_level": level,
        "horizon_days": 7,
        "anomaly_score": 0.3,
        "is_anomalous": anomalous,
        "window_start": day(end - 13).isoformat(),
        "window_end": day(end).isoformat(),
        "model_version": "risk-v1",
    }


class AlertPredictionServiceTests(TestCase):
    def setUp(self):
        MLModelVersion.objects.create(
            name="risk", model_type=ModelType.FAILURE_PREDICTION, architecture="GRU",
            version="risk-v1", training_dataset="test", trained_at=day(0), is_active=True,
        )
        MLModelVersion.objects.create(
            name="anomaly", model_type=ModelType.ANOMALY_DETECTION, architecture="LSTM_AUTOENCODER",
            version="anomaly-v1", training_dataset="test", trained_at=day(0), is_active=True,
        )
        self.drive = Resource.objects.create(
            name="Test drive", identifier="ALERT-DRIVE", resource_type=ResourceType.DISK,
        )
        for n in range(20):
            Metric.objects.create(resource=self.drive, timestamp=day(n), values={"smart_5_raw": n})

    @mock.patch("predictions.services.inference_client.predict")
    def test_high_risk_and_anomaly_create_separate_alerts_with_fixed_anomaly_severity(self, predict):
        predict.return_value = prediction_answer("CRITICAL", True)

        services.predict_resource(self.drive)

        risk = Alert.objects.get(alert_type=AlertType.FAILURE_RISK)
        anomaly = Alert.objects.get(alert_type=AlertType.ANOMALY)
        self.assertEqual(risk.severity, AlertSeverity.CRITICAL)
        self.assertEqual(anomaly.severity, AlertSeverity.HIGH)
        self.assertEqual(anomaly.latest_prediction.model_version.model_type, ModelType.ANOMALY_DETECTION)
        self.assertEqual(risk.latest_prediction.model_version.model_type, ModelType.FAILURE_PREDICTION)

    @mock.patch("predictions.services.inference_client.predict")
    def test_medium_risk_and_normal_anomaly_do_not_open_alerts(self, predict):
        predict.return_value = prediction_answer("MEDIUM", False)

        services.predict_resource(self.drive)

        self.assertFalse(Alert.objects.exists())
        self.drive.refresh_from_db()
        self.assertEqual(self.drive.status, Status.WARNING)

    @mock.patch("predictions.services.inference_client.predict")
    def test_active_alert_deduplicates_occurrences_and_resolves_after_two_clear_predictions(self, predict):
        predict.side_effect = [
            prediction_answer("HIGH", True, 19),
            prediction_answer("CRITICAL", True, 20),
            prediction_answer("LOW", False, 21),
            prediction_answer("HIGH", True, 22),
            prediction_answer("LOW", False, 23),
            prediction_answer("MEDIUM", False, 24),
            prediction_answer("CRITICAL", True, 25),
        ]
        for index in range(7):
            if index:
                Metric.objects.create(
                    resource=self.drive, timestamp=day(19 + index), values={"smart_5_raw": 19 + index}
                )
            services.predict_resource(self.drive)

        risk_alerts = Alert.objects.filter(alert_type=AlertType.FAILURE_RISK).order_by("created_at")
        self.assertEqual(risk_alerts.count(), 2)
        first, reopened = risk_alerts
        self.assertEqual(first.status, AlertStatus.RESOLVED)
        self.assertEqual(first.consecutive_clear_count, 2)
        self.assertEqual(first.occurrence_count, 3)
        self.assertEqual(first.resolution_source, "AUTO")
        self.assertEqual(reopened.status, AlertStatus.OPEN)
        self.assertEqual(reopened.occurrence_count, 1)
        self.assertEqual(reopened.consecutive_clear_count, 0)

        anomaly_alerts = Alert.objects.filter(alert_type=AlertType.ANOMALY).order_by("created_at")
        self.assertEqual(anomaly_alerts.count(), 2)
        self.assertEqual(anomaly_alerts.first().status, AlertStatus.RESOLVED)
        self.assertEqual(anomaly_alerts.last().status, AlertStatus.OPEN)

    def test_prediction_updates_an_existing_active_episode(self):
        alert = Alert.objects.create(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            severity=AlertSeverity.HIGH,
            first_seen_at=day(0),
            last_seen_at=day(0),
        )
        risk_prediction = Prediction.objects.create(
            resource=self.drive,
            model_version=MLModelVersion.objects.get(model_type=ModelType.FAILURE_PREDICTION),
            score=0.8,
            risk_level="CRITICAL",
            horizon_days=7,
            window_start=day(6),
            window_end=day(19),
        )
        anomaly_prediction = Prediction.objects.create(
            resource=self.drive,
            model_version=MLModelVersion.objects.get(model_type=ModelType.ANOMALY_DETECTION),
            score=0.1,
            is_anomalous=False,
            window_start=day(6),
            window_end=day(19),
        )

        from alerts.services import process_prediction_alerts
        process_prediction_alerts(self.drive, risk_prediction, anomaly_prediction)

        alert.refresh_from_db()
        self.assertEqual(Alert.objects.filter(resource=self.drive, alert_type=AlertType.FAILURE_RISK).count(), 1)
        self.assertEqual(alert.status, AlertStatus.OPEN)
        self.assertEqual(alert.occurrence_count, 2)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.latest_prediction_id, risk_prediction.pk)

    def test_prediction_after_manual_resolution_creates_a_new_episode(self):
        actor = User.objects.create_user(
            username="alert-resolver",
            email="alert-resolver@example.test",
            role=Role.IT_PRO,
        )
        previous = Alert.objects.create(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            severity=AlertSeverity.HIGH,
            first_seen_at=day(0),
            last_seen_at=day(0),
            occurrence_count=4,
        )
        client = APIClient()
        client.force_authenticate(actor)
        response = client.post(f"/api/alerts/{previous.pk}/resolve/")
        self.assertEqual(response.status_code, 200)

        risk_prediction = Prediction.objects.create(
            resource=self.drive,
            model_version=MLModelVersion.objects.get(model_type=ModelType.FAILURE_PREDICTION),
            score=0.8,
            risk_level="HIGH",
            horizon_days=7,
            window_start=day(6),
            window_end=day(19),
        )
        anomaly_prediction = Prediction.objects.create(
            resource=self.drive,
            model_version=MLModelVersion.objects.get(model_type=ModelType.ANOMALY_DETECTION),
            score=0.1,
            is_anomalous=False,
            window_start=day(6),
            window_end=day(19),
        )
        from alerts.services import process_prediction_alerts
        process_prediction_alerts(self.drive, risk_prediction, anomaly_prediction)

        previous.refresh_from_db()
        reopened = Alert.objects.get(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            status=AlertStatus.OPEN,
        )
        self.assertEqual(previous.status, AlertStatus.RESOLVED)
        self.assertEqual(previous.occurrence_count, 4)
        self.assertEqual(previous.resolution_source, "USER")
        self.assertNotEqual(previous.pk, reopened.pk)
        self.assertEqual(reopened.occurrence_count, 1)
        self.assertEqual(reopened.latest_prediction_id, risk_prediction.pk)

    @mock.patch("predictions.services.inference_client.predict")
    def test_prediction_audit_failure_rolls_back_predictions_and_alerts(self, predict):
        predict.return_value = prediction_answer("HIGH", True)
        with mock.patch("predictions.services.log_action", side_effect=IntegrityError("audit unavailable")):
            with self.assertRaises(IntegrityError):
                services.predict_resource(self.drive)

        self.assertEqual(Prediction.objects.filter(resource=self.drive).count(), 0)
        self.assertFalse(Alert.objects.filter(resource=self.drive).exists())
        self.drive.refresh_from_db()
        self.assertEqual(self.drive.status, Status.HEALTHY)

    @mock.patch("predictions.services.inference_client.predict")
    def test_alert_persistence_failure_rolls_back_prediction_transaction(self, predict):
        predict.return_value = prediction_answer("HIGH", True)
        with mock.patch("alerts.services.Alert.objects.create", side_effect=IntegrityError("alert store unavailable")):
            with self.assertRaises(IntegrityError):
                services.predict_resource(self.drive)

        self.assertEqual(Prediction.objects.filter(resource=self.drive).count(), 0)
        self.assertFalse(Alert.objects.filter(resource=self.drive).exists())
        self.drive.refresh_from_db()
        self.assertEqual(self.drive.status, Status.HEALTHY)

    @mock.patch("predictions.services.inference_client.predict", side_effect=InferenceError("unavailable"))
    def test_failed_inference_does_not_create_alert(self, _predict):
        with self.assertRaises(InferenceError):
            services.predict_resource(self.drive)
        self.assertFalse(Alert.objects.exists())

    @mock.patch("predictions.services.inference_client.predict", side_effect=NotEnoughHistory("short"))
    def test_missing_or_insufficient_prediction_does_not_count_as_clear(self, _predict):
        alert = Alert.objects.create(
            resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
            first_seen_at=day(0), last_seen_at=day(0),
        )
        with self.assertRaises(NotEnoughHistory):
            services.predict_resource(self.drive)
        alert.refresh_from_db()
        self.assertEqual(alert.consecutive_clear_count, 0)
        self.assertEqual(alert.status, AlertStatus.OPEN)

    def test_up_to_date_skip_does_not_count_as_clear(self):
        risk_model = MLModelVersion.objects.get(model_type=ModelType.FAILURE_PREDICTION)
        Prediction.objects.create(
            resource=self.drive,
            model_version=risk_model,
            score=0.8,
            risk_level="HIGH",
            horizon_days=7,
            window_start=day(6),
            window_end=day(19),
        )
        alert = Alert.objects.create(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            severity=AlertSeverity.HIGH,
            first_seen_at=day(0),
            last_seen_at=day(0),
            consecutive_clear_count=1,
        )

        self.assertIsNone(services.predict_resource(self.drive))

        alert.refresh_from_db()
        self.assertEqual(alert.consecutive_clear_count, 1)
        self.assertEqual(alert.status, AlertStatus.OPEN)

    def test_partial_unique_constraint_allows_only_one_active_episode_per_type(self):
        Alert.objects.create(
            resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
            first_seen_at=day(0), last_seen_at=day(0),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Alert.objects.create(
                    resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.CRITICAL,
                    first_seen_at=day(1), last_seen_at=day(1),
                )

    def test_resource_deletion_is_protected_while_alert_history_exists(self):
        Alert.objects.create(
            resource=self.drive, alert_type=AlertType.ANOMALY, severity=AlertSeverity.HIGH,
            first_seen_at=day(0), last_seen_at=day(0), status=AlertStatus.RESOLVED,
            resolved_at=day(1), resolution_source="AUTO", consecutive_clear_count=2,
        )
        with self.assertRaises(ProtectedError):
            self.drive.delete()

    def test_lifecycle_model_validation_rejects_inconsistent_fields(self):
        invalid_alerts = [
            Alert(
                resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
                first_seen_at=day(0), last_seen_at=day(0), status=AlertStatus.OPEN,
                acknowledged_at=day(1),
            ),
            Alert(
                resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
                first_seen_at=day(0), last_seen_at=day(0), status=AlertStatus.OPEN,
                consecutive_clear_count=2,
            ),
            Alert(
                resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
                first_seen_at=day(0), last_seen_at=day(0), status=AlertStatus.OPEN,
                consecutive_clear_count=-1,
            ),
            Alert(
                resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
                first_seen_at=day(0), last_seen_at=day(0), status=AlertStatus.ACKNOWLEDGED,
            ),
            Alert(
                resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
                first_seen_at=day(0), last_seen_at=day(0), status=AlertStatus.RESOLVED,
                resolution_source="AUTO",
            ),
            Alert(
                resource=self.drive, alert_type=AlertType.FAILURE_RISK, severity=AlertSeverity.HIGH,
                first_seen_at=day(0), last_seen_at=day(0), status=AlertStatus.RESOLVED,
                resolved_at=day(1), resolution_source="AUTO",
                consecutive_clear_count=1,
                resolved_by_id="00000000-0000-0000-0000-000000000001",
            ),
        ]

        for alert in invalid_alerts:
            with self.subTest(status=alert.status, resolved_at=alert.resolved_at):
                with self.assertRaises(ValidationError):
                    alert.save()

    def test_database_constraint_rejects_invalid_lifecycle_bulk_update(self):
        alert = Alert.objects.create(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            severity=AlertSeverity.HIGH,
            first_seen_at=day(0),
            last_seen_at=day(0),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Alert.objects.filter(pk=alert.pk).update(status=AlertStatus.ACKNOWLEDGED)

    def test_model_validation_rejects_negative_clear_count(self):
        alert = Alert(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            severity=AlertSeverity.HIGH,
            first_seen_at=day(0),
            last_seen_at=day(0),
            consecutive_clear_count=-1,
        )

        with self.assertRaises(ValidationError):
            alert.save()

    def test_database_constraint_rejects_negative_clear_count(self):
        alert = Alert.objects.create(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            severity=AlertSeverity.HIGH,
            first_seen_at=day(0),
            last_seen_at=day(0),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Alert.objects.filter(pk=alert.pk).update(consecutive_clear_count=-1)

    def test_valid_acknowledged_history_survives_actor_deletion(self):
        actor = User.objects.create_user(
            username="alert-actor", email="alert-actor@example.test", password="test-password"
        )
        alert = Alert(
            resource=self.drive,
            alert_type=AlertType.ANOMALY,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.RESOLVED,
            first_seen_at=day(0),
            last_seen_at=day(0),
            acknowledged_at=day(1),
            acknowledged_by=actor,
            resolved_at=day(2),
            resolved_by=actor,
            resolution_source="USER",
        )

        alert.save()
        actor.delete()
        alert.refresh_from_db()

        self.assertEqual(alert.status, AlertStatus.RESOLVED)
        self.assertIsNone(alert.acknowledged_by_id)
        self.assertIsNone(alert.resolved_by_id)
        self.assertEqual(alert.resolution_source, "USER")

    @mock.patch("predictions.services.inference_client.predict")
    def test_freshness_is_rechecked_after_lock_before_alert_occurrence_changes(self, predict):
        from types import SimpleNamespace

        predict.return_value = prediction_answer("HIGH", True)
        alert = Alert.objects.create(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            severity=AlertSeverity.HIGH,
            first_seen_at=day(0),
            last_seen_at=day(0),
        )
        stale_check = SimpleNamespace(exists=lambda: False)
        now_up_to_date_check = SimpleNamespace(exists=lambda: True)

        with mock.patch(
            "predictions.services.Prediction.objects.filter",
            side_effect=[stale_check, now_up_to_date_check],
        ) as freshness_filter:
            result = services.predict_resource(self.drive)

        self.assertIsNone(result)
        self.assertEqual(freshness_filter.call_count, 2)
        predict.assert_called_once()
        self.assertEqual(Prediction.objects.filter(resource=self.drive).count(), 0)
        alert.refresh_from_db()
        self.assertEqual(alert.occurrence_count, 1)
        self.assertEqual(alert.consecutive_clear_count, 0)


class AlertLifecycleConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        base = dict(architecture="x", version="race-v1", training_dataset="test", trained_at=day(0), is_active=True)
        self.risk_model = MLModelVersion.objects.create(
            name="race-risk", model_type=ModelType.FAILURE_PREDICTION, **base
        )
        self.anomaly_model = MLModelVersion.objects.create(
            name="race-anomaly", model_type=ModelType.ANOMALY_DETECTION, **base
        )
        self.drive = Resource.objects.create(
            name="Concurrent drive", identifier="ALERT-CONCURRENT", resource_type=ResourceType.DISK
        )
        self.actor = User.objects.create_user(
            username="concurrent-resolver",
            email="concurrent-resolver@example.test",
            role=Role.IT_PRO,
        )
        self.alert = Alert.objects.create(
            resource=self.drive,
            alert_type=AlertType.FAILURE_RISK,
            severity=AlertSeverity.HIGH,
            first_seen_at=day(0),
            last_seen_at=day(0),
        )
        self.risk_prediction = Prediction.objects.create(
            resource=self.drive,
            model_version=self.risk_model,
            score=0.8,
            risk_level="HIGH",
            horizon_days=7,
            window_start=day(6),
            window_end=day(19),
        )
        self.anomaly_prediction = Prediction.objects.create(
            resource=self.drive,
            model_version=self.anomaly_model,
            score=0.1,
            is_anomalous=False,
            window_start=day(6),
            window_end=day(19),
        )

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_prediction_and_manual_resolution_preserve_episode_history(self):
        from alerts.services import process_prediction_alerts

        barrier = Barrier(2)

        def apply_prediction():
            close_old_connections()
            try:
                resource = Resource.objects.get(pk=self.drive.pk)
                risk = Prediction.objects.get(pk=self.risk_prediction.pk)
                anomaly = Prediction.objects.get(pk=self.anomaly_prediction.pk)
                barrier.wait(timeout=10)
                process_prediction_alerts(resource, risk, anomaly)
            finally:
                close_old_connections()

        def resolve_alert():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.actor)
                barrier.wait(timeout=10)
                return client.post(f"/api/alerts/{self.alert.pk}/resolve/").status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            prediction_future = executor.submit(apply_prediction)
            resolution_future = executor.submit(resolve_alert)
            prediction_future.result(timeout=20)
            self.assertEqual(resolution_future.result(timeout=20), 200)

        episodes = list(Alert.objects.filter(
            resource=self.drive, alert_type=AlertType.FAILURE_RISK
        ).order_by("created_at", "id"))
        self.assertGreaterEqual(len(episodes), 1)
        self.assertEqual(episodes[0].status, AlertStatus.RESOLVED)
        self.assertEqual(episodes[0].resolution_source, "USER")
        if len(episodes) == 1:
            self.assertEqual(episodes[0].occurrence_count, 2)
        else:
            self.assertEqual(len(episodes), 2)
            self.assertEqual(episodes[0].occurrence_count, 1)
            self.assertEqual(episodes[1].status, AlertStatus.OPEN)
            self.assertEqual(episodes[1].occurrence_count, 1)
