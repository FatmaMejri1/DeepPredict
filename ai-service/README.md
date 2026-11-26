# DeepPredict AI service

The development setup targets 64-bit Python 3.12 and the PyTorch 2.15 CPU wheel. `.venv312` is kept separate from `.venv` so the launcher always uses the supported interpreter.

## Create or repair the environment

From this directory in PowerShell:

```powershell
py -3.12 -m venv .venv312
```

Install the service dependencies into that environment:

```powershell
& .\.venv312\Scripts\python.exe -m pip install --upgrade pip
& .\.venv312\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple -r requirements-service.txt
& .\.venv312\Scripts\python.exe -c "import sys, torch; assert sys.version_info[:2] == (3, 12); assert torch.__version__ == '2.15.0+cpu'; print(torch.__version__, torch.rand(1))"
```

The final command verifies Python 3.12, the CPU-specific PyTorch build and a tensor operation.

## Run the AI service tests

Install the separately pinned test dependencies and run the existing suite:

```powershell
& .\.venv312\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple -r requirements-test.txt
& .\.venv312\Scripts\python.exe -m pytest tests
```

`requirements-test.txt` includes the runtime requirements and adds pytest, the pinned HTTPX 2 transport required by the pinned Starlette TestClient, and coverage tools. The service image installs only `requirements-service.txt`.

## Start and check the service

Run the checked-in launcher, which always uses `.venv312`:

```powershell
.\run_dev.ps1
```

Open [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health). The service should return `{"status":"ok", ...}`. Prediction requests from Django use this service at `http://127.0.0.1:8001` by default.

The Dockerfile uses the same pinned runtime requirements and installs from the PyTorch CPU wheel index plus PyPI. `.dockerignore` excludes local Python environments, caches, test output, data and notebooks while retaining the versioned model artifacts needed by the service.
