"""Read-only JWT-authenticated application workflows for DeepPredict."""

import os
import random

import gevent
from locust import HttpUser, between, task
from locust.exception import LocustError, StopUser


def _object_with_keys(value, keys):
    return isinstance(value, dict) and all(key in value for key in keys)


def _summary_contract(data):
    keys = ("total", "healthy", "warning", "high_risk", "anomalous", "not_scored", "data_until", "top_critical")
    if not _object_with_keys(data, keys):
        return "summary response is missing required fields"
    if not all(isinstance(data[key], int) for key in keys[:6]):
        return "summary KPI values must be integers"
    if not isinstance(data["top_critical"], list):
        return "summary top_critical must be a list"
    return None


def _activity_contract(data):
    if not _object_with_keys(data, ("results",)) or not isinstance(data["results"], list):
        return "activity response must contain a results list"
    required = ("id", "drive_identifier", "drive_name", "kind", "outcome", "score", "created_at")
    if any(not _object_with_keys(row, required) for row in data["results"]):
        return "activity result is missing required fields"
    return None


def _drive_list_contract(data):
    if not _object_with_keys(data, ("count", "next", "previous", "results")):
        return "drive list response is missing pagination fields"
    if not isinstance(data["count"], int) or not isinstance(data["results"], list):
        return "drive list count/results have unexpected types"
    if any(not _object_with_keys(row, ("id", "identifier")) for row in data["results"]):
        return "drive list item is missing its id or identifier"
    return None


def _drive_detail_contract(data):
    if not _object_with_keys(data, ("id", "name", "identifier", "status", "attributes", "created_at", "updated_at")):
        return "drive detail response is missing required fields"
    return None


def _telemetry_contract(data):
    if not _object_with_keys(data, ("smart", "risk", "thresholds")):
        return "telemetry response is missing smart, risk or thresholds"
    smart = data["smart"]
    risk = data["risk"]
    if not _object_with_keys(smart, ("labels", "series")) or not isinstance(smart["labels"], list) or not isinstance(smart["series"], list):
        return "SMART telemetry chart has an unexpected shape"
    if not _object_with_keys(risk, ("labels", "scores")) or not isinstance(risk["labels"], list) or not isinstance(risk["scores"], list):
        return "risk telemetry chart has an unexpected shape"
    return None


def _prediction_history_contract(data):
    if not isinstance(data, list):
        return "prediction history response must be a list"
    required = ("id", "prediction_type", "score", "window_start", "window_end", "created_at", "model")
    for row in data:
        if not _object_with_keys(row, required) or not _object_with_keys(row["model"], ("name", "version", "model_type", "architecture")):
            return "prediction history item is missing prediction or model fields"
    return None


def _health_contract(data):
    if not _object_with_keys(data, ("status", "model_version", "checked_at")):
        return "health response is missing status, model_version or checked_at"
    if data["status"] not in ("online", "offline"):
        return "health status must be online or offline"
    return None


class AuthenticatedAPIUser(HttpUser):
    """Base profile; credentials are required from the environment, never defaults."""

    abstract = True
    wait_time = between(2.5, 5.5)
    expected_role = ""
    username_env = ""
    password_env = ""

    def on_start(self):
        username = os.environ.get(self.username_env, "").strip()
        password = os.environ.get(self.password_env, "")
        if not username or not password:
            raise LocustError(
                f"Missing Locust credentials for {self.expected_role}. Set both "
                f"{self.username_env} and {self.password_env}; no defaults are used."
            )

        with self.client.post(
            "/api/auth/login/",
            json={"username": username, "password": password},
            name="POST /api/auth/login/",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(self._http_failure("login", response))
                raise StopUser()
            try:
                payload = response.json()
            except ValueError:
                response.failure("login returned invalid JSON")
                raise StopUser()

            user = payload.get("user") if isinstance(payload, dict) else None
            if not _object_with_keys(payload, ("access", "refresh", "user")):
                response.failure("login response must contain access, refresh and user")
                raise StopUser()
            if not isinstance(payload["access"], str) or not payload["access"]:
                response.failure("login response has no usable access token")
                raise StopUser()
            if not isinstance(payload["refresh"], str) or not payload["refresh"]:
                response.failure("login response has no usable refresh token")
                raise StopUser()
            if not _object_with_keys(user, ("id", "username", "role")) or user["role"] != self.expected_role:
                response.failure(f"login user role must be {self.expected_role}")
                raise StopUser()
            response.success()

        self.refresh_token = payload["refresh"]
        self.client.headers.update({"Authorization": f"Bearer {payload['access']}"})

        current_user = self._request_json(
            "GET", "/api/auth/me/", "GET /api/auth/me/",
            lambda data: None if _object_with_keys(data, ("id", "username", "role")) and data["role"] == self.expected_role else "current-user response has missing fields or unexpected role",
        )
        if current_user is None:
            raise StopUser()

    @staticmethod
    def _http_failure(action, response):
        if response.status_code == 403:
            return f"Unexpected permission denial (403) during authorized {action} workflow"
        if response.status_code >= 500:
            return f"Server error {response.status_code} during {action} workflow"
        return f"Unexpected HTTP {response.status_code} during {action} workflow"

    def _refresh_access_token(self):
        with self.client.post(
            "/api/auth/refresh/",
            json={"refresh": self.refresh_token},
            name="POST /api/auth/refresh/",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(self._http_failure("JWT refresh", response))
                return False
            try:
                payload = response.json()
            except ValueError:
                response.failure("JWT refresh returned invalid JSON")
                return False
            access = payload.get("access") if isinstance(payload, dict) else None
            if not isinstance(access, str) or not access:
                response.failure("JWT refresh response must contain a usable access token")
                return False
            response.success()
            # The configured SimpleJWT rotation is disabled; refresh remains unchanged.
            self.client.headers.update({"Authorization": f"Bearer {access}"})
            return True

    def _request_json(self, method, path, name, validator, allow_refresh=True):
        retry_after_refresh = False
        with self.client.request(method, path, name=name, catch_response=True) as response:
            if response.status_code == 401 and allow_refresh:
                if self._refresh_access_token():
                    response.success()  # expected expiry recovered through the refresh API
                    retry_after_refresh = True
                else:
                    response.failure("Unauthorized request; JWT refresh did not recover the session")
                    return None
            elif response.status_code != 200:
                response.failure(self._http_failure(name, response))
                return None
            else:
                try:
                    payload = response.json()
                except ValueError:
                    response.failure("successful response was not valid JSON")
                    return None
                contract_error = validator(payload)
                if contract_error:
                    response.failure(f"Invalid response contract: {contract_error}")
                    return None
                response.success()
                return payload

        if retry_after_refresh:
            return self._request_json(method, path, name, validator, allow_refresh=False)
        return None

    @staticmethod
    def _think_between_pages():
        gevent.sleep(random.uniform(0.5, 1.25))

    @task(8)
    def browse_overview_and_inspect_drive(self):
        """Overview -> recent activity -> drive inventory -> selected-drive detail."""
        summary = self._request_json(
            "GET", "/api/dashboard/summary/", "GET /api/dashboard/summary/", _summary_contract
        )
        if summary is None:
            return

        self._think_between_pages()
        activity = self._request_json(
            "GET", "/api/dashboard/activity/", "GET /api/dashboard/activity/", _activity_contract
        )
        if activity is None:
            return

        self._think_between_pages()
        drives = self._request_json(
            "GET", "/api/drives/?page=1", "GET /api/drives/", _drive_list_contract
        )
        if drives is None or not drives["results"]:
            return  # An empty fleet is a valid application state.

        drive = random.choice(drives["results"])
        drive_id = drive["id"]
        self._think_between_pages()
        detail = self._request_json(
            "GET", f"/api/drives/{drive_id}/", "GET /api/drives/{id}/",
            lambda data: (
                _drive_detail_contract(data)
                or ("drive detail id does not match the selected inventory row" if data["id"] != drive_id else None)
            ) if isinstance(data, dict) else "drive detail response must be an object",
        )
        if detail is None:
            return

        self._think_between_pages()
        telemetry = self._request_json(
            "GET", f"/api/drives/{drive_id}/telemetry/?days=90",
            "GET /api/drives/{id}/telemetry/", _telemetry_contract,
        )
        if telemetry is None:
            return

        self._think_between_pages()
        self._request_json(
            "GET", f"/api/drives/{drive_id}/predictions/",
            "GET /api/drives/{id}/predictions/", _prediction_history_contract,
        )

    @task(2)
    def check_ai_service_status(self):
        # The Angular header refreshes this status approximately every 30 seconds.
        self._request_json(
            "GET", "/api/dashboard/health/", "GET /api/dashboard/health/", _health_contract
        )


class ITProUser(AuthenticatedAPIUser):
    weight = 5
    expected_role = "IT_PRO"
    username_env = "LOCUST_IT_PRO_USER"
    password_env = "LOCUST_IT_PRO_PASS"


class OperatorUser(AuthenticatedAPIUser):
    weight = 3
    expected_role = "OPERATOR"
    username_env = "LOCUST_OPERATOR_USER"
    password_env = "LOCUST_OPERATOR_PASS"


class SysAdminUser(AuthenticatedAPIUser):
    weight = 1
    expected_role = "SYSADMIN"
    username_env = "LOCUST_SYSADMIN_USER"
    password_env = "LOCUST_SYSADMIN_PASS"
