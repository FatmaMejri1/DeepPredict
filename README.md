# DeepPredict — Predictive Monitoring & AI Fault Detection for IT Infrastructures

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1.1-092E20.svg)](https://www.djangoproject.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Angular](https://img.shields.io/badge/Angular-22.3.0-DD0031.svg)](https://angular.dev/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.15.0+cpu-EE4C2C.svg)](https://pytorch.org/)
[![Test Suite](https://img.shields.io/badge/Tests-125%2B%20Passing%20(100%25)-brightgreen.svg)]()
[![Code Quality](https://img.shields.io/badge/Standards-ISO%2FIEC%2025010-orange.svg)]()

**DeepPredict** is an enterprise-grade predictive maintenance and monitoring platform for IT infrastructure. Designed specifically for mission-critical storage fleets (such as Seagate Enterprise `ST12000NM0008` 12TB drives), it shifts infrastructure operations from reactive incident response to proactive failure prevention.

By analyzing multi-dimensional **S.M.A.R.T.** (Self-Monitoring, Analysis and Reporting Technology) telemetry through a dual-model Deep Learning pipeline, DeepPredict forecasts hard drive failure probabilities over a **7-day horizon** and pinpoints anomalous behavioral degradation before data loss occurs.

---

## Architecture Overview

```
                                +---------------------------------------------+
                                |             Angular 22 SPA                  |
                                | (Dashboard, Fleet, Alerts, Analytics, Auth) |
                                +---------------------+-----------------------+
                                                      |
                                                      | HTTP / REST (JWT)
                                                      v
                                +---------------------------------------------+
                                |            Django 6.1 Backend API           |
                                |  - REST Framework & JWT Authentication      |
                                |  - RBAC: SYSADMIN, IT_PRO, OPERATOR         |
                                |  - Drive Fleet & Telemetry Ingestion        |
                                |  - Alert Generation & Audit Trails          |
                                +---------------------+-----------------------+
                                                      |
                                       +--------------+--------------+
                                       |                             |
                                       v                             v
                        +----------------------------+  +----------------------------+
                        |  SQLite / PostgreSQL DB    |  |   FastAPI AI Microservice   |
                        | (Drives, Metrics, Alerts,  |  | (Port 8001 - PyTorch CPU)  |
                        |  Audit Logs, Model Record) |  | - RiskNet (GRU)            |
                        +----------------------------+  | - LSTMAE (AutoEncoder)     |
                                                        +----------------------------+
```

### Components

1. **AI Microservice (`ai-service/`)**: Isolated high-performance service running on **Python 3.12**, **FastAPI**, and **PyTorch (CPU)**. Handles telemetry validation, column mapping normalization, gap imputation, and dual-model neural network inference.
2. **Backend API (`backend/`)**: Core application service built with **Django 6.1.1** and **Django REST Framework (DRF)**. Provides JWT authentication, strict role-based access control (RBAC), immutable audit logging, fleet telemetry ingestion, automated alert lifecycle management, and OpenAPI 3.0 schema generation.
3. **Frontend SPA (`frontend/`)**: Modern reactive web client built with **Angular 22**, **TypeScript**, **RxJS**, and **Chart.js**. Features interactive telemetry degradation charts, fleet health filters, real-time alert notifications with unread counters, and role-tailored workspaces.

---

## Machine Learning Pipeline

### Dual-Model Architecture

| Model | Architecture | Purpose | Horizon / Metric | Thresholds |
| :--- | :--- | :--- | :--- | :--- |
| **RiskNet** | **GRU (Gated Recurrent Unit)**<br>(Input: 23, Hidden: 32, Dropout: 0.2) | Supervised failure risk probability | 7 days ($P(\text{fail} \le 7\text{d})$) | • **Low**: $< 0.4108$<br>• **Medium**: $\ge 0.4108$<br>• **High**: $\ge 0.7807$<br>• **Critical**: $\ge 0.8836$ |
| **LSTMAE** | **LSTM Sequence AutoEncoder**<br>(Input: 23, Hidden: 32, Latent: 8) | Unsupervised anomaly detection | Mean Squared Reconstruction Error | • **Anomaly Cutoff**: $\ge 1.6137$ |

### Telemetry & Feature Processing
- **Dataset:** Trained and calibrated on real-world industrial storage telemetry (**Backblaze Drive Stats 2026 Q1+Q2**).
- **Features:** 22 raw S.M.A.R.T. indicators (reallocated sectors, pending sectors, temperature, seek errors, ECC recoveries, power cycles, etc.) plus a 23rd binary indicator (`gap_filled`).
- **Sliding Window:** Requires a **14-calendar-day sequence**.
- **Data Quality:** Forward-fills missing telemetry gaps up to **3 consecutive days**; windows with gaps $> 3$ days are rejected. Values are transformed into log-space ($\log(1+x)$) and Z-score standardized within $[-10.0, +10.0]$.

---

## Repository Structure

```text
DeepPredict/
├── ai-service/             # FastAPI + PyTorch inference microservice
│   ├── dp_ml/              # Preprocessing, validation, inference & model architectures
│   ├── models/             # PyTorch weights (risk_gru.pt, anomaly_lstmae.pt, config.json)
│   ├── service/            # FastAPI application (app.py) & health endpoints
│   ├── tests/              # 58 Pytest unit tests (100% statement & branch coverage)
│   └── Dockerfile          # Container specification for AI microservice
├── backend/                # Django 6.1 REST API & application orchestration
│   ├── accounts/           # User authentication, JWT tokens, RBAC permissions
│   ├── alerts/             # Proactive alert domain, resolution & lifecycle workflows
│   ├── audit/              # Immutable audit trails and security signal tracking
│   ├── config/             # Django settings, security middleware & URL routing
│   ├── dashboard/          # Fleet aggregation queries, timeline analytics, E2E tests
│   ├── infrastructure/     # Storage resource models, hardware metadata & status
│   ├── ml_models/          # Model registry, version tracking & metadata
│   ├── monitoring/         # Telemetry ingestion and SMART time-series metrics
│   ├── predictions/        # Inference client orchestrator and risk scoring services
│   └── locustfile.py       # Performance & load testing suite
├── frontend/               # Angular 22 Single-Page Application
│   ├── src/app/core/       # Guards, HTTP interceptors, services, and models
│   ├── src/app/features/   # Feature modules (overview, drives, alerts, ml-models, users)
│   └── src/app/layout/     # App shell, responsive sidebar & notification bell header
├── docs/                   # System documentation & business rules (BR-01 to BR-05)
└── evidence/               # QA reports, coverage XML, Locust benchmarks, Bandit SAST
```

---

## Role-Based Access Control (RBAC) & Business Rules

DeepPredict enforces formal business rules documented in [`docs/business-rules.md`](docs/business-rules.md):

* **SYSADMIN**: Full administrative governance, user account management, model registry configuration, and system settings.
* **IT_PRO**: Infrastructure management, telemetry file uploads, manual prediction triggers, and alert acknowledgement/resolution.
* **OPERATOR**: Read-only monitoring of dashboards, drive inventory, and alert notifications.
* **Drive Status Mapping**:
  - `LOW` risk $\rightarrow$ Drive marked **`HEALTHY`**
  - `MEDIUM` risk $\rightarrow$ Drive marked **`WARNING`**
  - `HIGH` / `CRITICAL` risk $\rightarrow$ Drive marked **`HIGH_RISK`**

---

## Getting Started

### Prerequisites
- **Python 3.12** (required for `ai-service` PyTorch compatibility)
- **Python 3.14** or **3.12** (for `backend`)
- **Node.js 22+ / 24+** & **npm 11+** (for `frontend`)

---

### 1. Launch the AI Inference Service

Open PowerShell in `ai-service/`:

```powershell
cd ai-service

# Create and activate Python 3.12 virtual environment
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1

# Install PyTorch CPU and service dependencies
pip install --upgrade pip
pip install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple -r requirements-service.txt

# Start the AI microservice on port 8001
.\run_dev.ps1
```
> Verify health check: [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health) $\rightarrow$ `{"status":"ok", "model_version":"gru-ae-v1"}`

---

### 2. Launch the Django Backend API

In a second terminal:

```powershell
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Apply database migrations and seed default models
python manage.py migrate
python manage.py register_models

# Start Django development server on port 8000
python manage.py runserver 127.0.0.1:8000
```
> Explore API Documentation (Swagger): [http://127.0.0.1:8000/api/schema/swagger-ui/](http://127.0.0.1:8000/api/schema/swagger-ui/)

---

### 3. Launch the Angular Frontend

In a third terminal:

```powershell
cd frontend

# Install dependencies
npm ci

# Start Angular development server (with reverse proxy to Django API)
npm start
```
> Open your browser at [http://localhost:4200](http://localhost:4200).

---

## Testing & Quality Assurance

The project follows an **ISO/IEC 25010** software quality standard with 125+ automated tests:

### Unit & Integration Tests
```powershell
# Run AI Service test suite (58 tests, 100% statement & branch coverage)
cd ai-service
.\.venv312\Scripts\python.exe -m pytest tests --cov=dp_ml --cov=service

# Run Backend test suite (67 tests, 100% pass)
cd backend
pytest
```

### End-to-End (E2E) Browser Testing (Playwright)
```powershell
cd backend
pip install -r requirements-e2e.txt
python -m playwright install chromium
python manage.py test dashboard
```

### Performance & Load Testing (Locust)
```powershell
cd backend
pip install -r requirements-locust.txt
python -m locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 10 -r 1 --run-time 1m
```

### Security & Static Code Analysis (SAST & SCA)
```powershell
# SAST security vulnerability scan
bandit -r backend/ ai-service/dp_ml/ ai-service/service/

# Dependency vulnerability audit
pip-audit
```

---

## License & Intellectual Property

DeepPredict is developed for predictive IT monitoring and infrastructure health governance. All rights reserved.
