# DeepPredict API load tests

`locustfile.py` models read-only, JWT-authenticated browser workflows against the existing Django API. It does not generate predictions, upload telemetry, or mutate users/resources.

## Install Locust

From `backend/`, use the project Python environment (Python 3.12 or newer supported by the backend):

```powershell
python -m pip install -r requirements-locust.txt
python -m locust --version
```

The file pins Locust separately so the load-test tool is not added to the Django runtime dependency set.

## Test-account prerequisites

Create three active users in the local/test database using Django admin or an approved local setup process:

- IT professional account with role `IT_PRO`
- Operator account with role `OPERATOR`
- System administrator account with role `SYSADMIN`

Each account needs a valid, distinct username and password. The Locust profile checks the role returned by both login and `/api/auth/me/`. It does not create accounts or reset passwords. Do not use production accounts or put credentials in source control.

## Configure credentials and host

PowerShell example. Enter each password when prompted; these values remain in the current shell environment and are not written to a project file:

```powershell
$env:LOCUST_IT_PRO_USER = Read-Host "IT_PRO username"
$secure = Read-Host "IT_PRO password" -AsSecureString
$env:LOCUST_IT_PRO_PASS = [System.Net.NetworkCredential]::new("", $secure).Password

$env:LOCUST_OPERATOR_USER = Read-Host "OPERATOR username"
$secure = Read-Host "OPERATOR password" -AsSecureString
$env:LOCUST_OPERATOR_PASS = [System.Net.NetworkCredential]::new("", $secure).Password

$env:LOCUST_SYSADMIN_USER = Read-Host "SYSADMIN username"
$secure = Read-Host "SYSADMIN password" -AsSecureString
$env:LOCUST_SYSADMIN_PASS = [System.Net.NetworkCredential]::new("", $secure).Password
```

Start Django separately, then run Locust from `backend/`, pointing `--host` at that server. Local example:

```powershell
python manage.py runserver 127.0.0.1:8000
```

In another terminal with Locust installed and the six variables configured:

```powershell
python -m locust -f locustfile.py --host http://127.0.0.1:8000
```

Open the Locust web UI at `http://localhost:8089`, or run a small, bounded headless session:

```powershell
$reportPrefix = Join-Path $env:TEMP "deeppredict-locust"
python -m locust -f locustfile.py --host http://127.0.0.1:8000 --headless --users 3 --spawn-rate 0.1 --run-time 2m --csv $reportPrefix
```

Locust’s `--spawn-rate` is deliberately conservative: Django scopes login throttling to 10 requests/minute, and unauthenticated users from the same load-generator IP share the throttle bucket. Keep startup logins below that limit per source IP, especially when running multiple workers. Report files go to the operating system temp directory.

## Workload and expected responses

Profiles are weighted `IT_PRO:OPERATOR:SYSADMIN = 5:3:1`. Each application browse task validates the existing response contracts in sequence: login and current user, dashboard summary, dashboard activity, paginated drive list, randomly selected drive detail, SMART/risk telemetry, and prediction history. Empty drive fleets and empty prediction history are valid. A separate weighted task checks the existing AI health endpoint; `online` and `offline` are both valid service states.

The profile is read-only. It exercises dashboard and drive investigation traffic, not the IT_PRO/SYSADMIN prediction and upload writes. Those operations are intentionally excluded to avoid creating predictions or changing telemetry during a read-load run. The existing E2E suite remains authoritative for role-denial behavior; an unexpected 403 during these authenticated read workflows is recorded as a Locust failure.

Access tokens are refreshed through `/api/auth/refresh/` after a 401, using the current `{ "refresh": "…" }` request and `{ "access": "…" }` response contract. Login, refresh, permission denials, server errors, invalid JSON, and response-shape failures are recorded in Locust statistics. Missing credentials stop startup with an explicit configuration error.

Locust timings are measurements of the configured host, database, AI health dependency and test data. A successful run alone is not a performance benchmark; compare request counts, failures, and latency percentiles under a stated user count and environment.
