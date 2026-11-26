# DeepPredict Angular frontend

The Angular application lives in this directory. Django provides its API; it no longer renders the application pages.

## Run the frontend

Install frontend dependencies once:

```powershell
npm ci
```

Start Django on `http://localhost:8000` in one terminal, then start Angular:

```powershell
npm start
```

Open `http://localhost:4200`. Angular sends `/api` requests through its development proxy to Django.

## Run the unified E2E suite

Install the backend requirements and Playwright's Chromium browser once:

```powershell
cd ..\backend
pip install -r requirements-e2e.txt
python -m playwright install chromium
```

Install the frontend dependencies with `npm ci` from this directory, then run the complete dashboard test suite from `backend/`:

```powershell
python manage.py test dashboard
```

The suite starts Angular automatically, proxies it to Django's isolated test server, and covers the IT professional, operator, and system administrator journeys. Screenshots and the JSON run report are written under `backend/evidence/e2e/`.
