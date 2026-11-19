
import os

from locust import HttpUser, task, between
from locust.exception import StopUser


IT_PRO_USER = os.environ.get("LOCUST_IT_PRO_USER", "it_pro_user")
IT_PRO_PASS = os.environ.get("LOCUST_IT_PRO_PASS", "")

OPERATOR_USER = os.environ.get("LOCUST_OPERATOR_USER", "operator_user")
OPERATOR_PASS = os.environ.get("LOCUST_OPERATOR_PASS", "")


class AuthenticatedUser(HttpUser):
    abstract = True
    wait_time = between(0.3, 1.0)

    username: str = ""
    password: str = None

    def on_start(self):
        if not self.username or not self.password:
            raise StopUser()

        # 1. Load login page and retrieve CSRF cookie.
        response = self.client.get(
            "/login/",
            name="GET /login/ (authentication setup)",
        )

        if response.status_code != 200:
            raise StopUser()

        csrf_token = self.client.cookies.get("csrftoken")

        if not csrf_token:
            raise StopUser()

        # 2. Submit login form without following redirects.
        response = self.client.post(
            "/login/",
            data={
                "username": self.username,
                "password": self.password,
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={"Referer": f"{self.host}/login/"},
            allow_redirects=False,
            name="POST /login/",
        )

        if response.status_code != 302:
            raise StopUser()

        if "/login/" in response.headers.get("Location", ""):
            raise StopUser()

        # 3. Confirm that the session is authenticated.
        response = self.client.get(
            "/",
            name="GET / (authentication verification)",
        )

        if response.status_code != 200:
            raise StopUser()

        if "Sign in to your workspace" in response.text:
            raise StopUser()


class ITPROBenchmarkUser(AuthenticatedUser):
    weight = 3
    username = IT_PRO_USER
    password = IT_PRO_PASS

    @task(4)
    def view_dashboard(self):
        self.client.get("/", name="GET / (IT_PRO dashboard)")

    @task(3)
    def list_drives(self):
        self.client.get("/drives/", name="GET /drives/ (IT_PRO)")

    @task(2)
    def drives_page_2(self):
        self.client.get(
            "/drives/?page=2",
            name="GET /drives/?page=2",
        )

    @task(1)
    def api_docs(self):
        self.client.get("/api/docs/", name="GET /api/docs/")


class OperatorBenchmarkUser(AuthenticatedUser):
    weight = 1
    username = OPERATOR_USER
    password = OPERATOR_PASS

    @task(4)
    def view_dashboard(self):
        self.client.get("/", name="GET / (OPERATOR dashboard)")

    @task(3)
    def list_drives(self):
        self.client.get(
            "/drives/",
            name="GET /drives/ (OPERATOR)",
        )

    @task(1)
    def try_forbidden_admin(self):
        with self.client.get(
            "/admin/",
            name="GET /admin/ (OPERATOR access restriction)",
            catch_response=True,
            allow_redirects=False,
        ) as response:

            location = response.headers.get("Location", "")

            if (
                response.status_code == 302
                and "/admin/login/" in location
            ):
                response.success()
            else:
                response.failure(
                    f"Expected redirect to admin login, "
                    f"received HTTP {response.status_code}, "
                    f"Location={location}"
                )
