# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Rice Vision AI — a research project (docs and comments are mostly in Vietnamese) that estimates the number and 3D size of rice grains in a cup from a single top-down photo. The deployable product lives entirely in `AI_SERVICES/`; the other top-level folders are research/training material:

- `AI_SERVICES/` — production package: Python FastAPI inference server (`src/rice_ai`), Node/Express gateway + React/Vite frontend (`RICE_ESTIMATION_APPLICATION/`), phone-camera capture server (`capture_server/`), Windows launchers (`SYSTEM_LAUNCHER/`), tests.
- `LINEAR_REGRESSION_MODEL/` — training of the 31-feature count regressors. The single active entrypoint is `RICE_SEED_REGRESSION_TRAINER.ipynb`; it has its own `.venv` (Python 3.12.10, kernel `ricai-training`) separate from `AI_SERVICES/.venv`. Exported bundles go to `models/<model_id>/` (config/manifest/metrics/feature_schema/scaler_params JSON + gitignored `.joblib`).
- `FromThanh/` — Bayesian few-shot calibration research (`bayes_fewshot.py`, `baseline_comparison.py`) and the integration plan/spec that was ported into `rice_ai/estimation/bayes_hybrid.py`.
- `PAPER_BENCHMARKS/`, `RESULTS/` — benchmark tables/charts for the paper; `DATASET_BUILDER/`, `DATASETS/` — data (raw images are gitignored).

Do not move/rename/delete the legacy regression notebooks in `LINEAR_REGRESSION_MODEL/` — artifact manifests reference their paths and SHA-256 hashes as provenance.

## Commands

All Python commands run from `AI_SERVICES/` with its venv (Python 3.12, see `.python-version`; `requirements.txt`, Colab uses `requirements-colab.txt`).

```powershell
cd AI_SERVICES
.\.venv\Scripts\Activate.ps1

python app.py                                  # inference server on PORT_AI (default 8000)
uvicorn app:app --host 0.0.0.0 --port 8000      # equivalent (note: README's `app.main:app` is wrong)
python capture_server\start.py 8765            # phone camera capture server (HTTPS/WebSocket)

pytest                                          # full suite
pytest tests/test_pipeline.py -v                # one file
pytest tests/test_bayes_estimators.py -k <name> # one test
python scripts/verify_artifacts.py [--yolo|--cnn|--regression|--model-dir <dir>]
python scripts/fit_bayes_params.py [--csv PATH] [--out PATH] [--reps N]
```

Web app (`AI_SERVICES/RICE_ESTIMATION_APPLICATION/`): `npm run install:all`, then `npm run dev` (runs backend on :3000 via nodemon and frontend on :5173 via concurrently). Frontend alone: `npm --prefix frontend run dev|build|lint`. No JS tests exist.

Windows launchers in `AI_SERVICES/SYSTEM_LAUNCHER/`: `0_SETUP_AI_SERVICE.bat` (creates `.venv`), `1_`/`2_`/`3_` start AI server / web / phone camera, `START_ALL_1_CLICK.bat`, `STOP_ALL_SYSTEM.bat`.

Testing notes:
- `tests/conftest.py` caches `platform.uname` on Windows (avoids a WMI crash at pytest startup) and sets `MPLBACKEND=Agg`, `KERAS_BACKEND=torch`.
- Model weights (`*.pt`, `*.keras`, `*.joblib`) are gitignored. Tests needing real YOLO/CNN weights or fixture images (e.g. `test_real_pipeline.py`) `skipTest` when they're missing — a skip is not a pass.

## Architecture (`AI_SERVICES/src/rice_ai`)

Request flow: frontend → Node gateway `POST /api/predict` (multer, forwards to `AI_SERVER_URL`) → FastAPI `POST /predict` → `RicePipeline.run`. The gateway has no vision logic of its own; the phone capture flow goes through the same `/api/predict`. `AI_SERVER_URL` may point to a Colab GPU runtime exposed via ngrok (`src/notebooks/API_Server.ipynb`); the gateway's `POST /api/set-url` rewrites it in `.env`.

- `app.py` (root of AI_SERVICES) is only a bootstrap: puts `src/` on `sys.path`, builds `Settings()` and `create_app()`, and exposes `MODEL_PATHS` for backward compatibility (tests import it).
- `api/application.py` — `create_app()` factory with dependency injection (settings, pipeline, vision/regression/bayes providers, all overridable in tests). Lifespan pre-loads regression and Bayes models; failure → degraded mode with warnings, not a crash. Inference is serialized by an `asyncio.Semaphore`. `api/routes.py` has `/health`, `/api/status`, `/predict`, `/api/results/{id}/manifest|download`.
- `settings.py` — single config source. Precedence: `os.environ` > `AI_SERVICES/.env` (read with `dotenv_values`, never mutates environ) > defaults. Relative paths resolve from `AI_SERVICES/`, not CWD. Model paths fall back through candidate lists (`artifacts/…`, then `LINEAR_REGRESSION_MODEL/models/extra_trees`, then Colab Drive paths). `MAX_CONCURRENT_INFERENCES` must be exactly 1. See `.env.example` for all knobs.
- `contracts.py` — `PredictionInput`, `PipelineResult`, etc., and `PipelineError(status, error_code, message)`, which routes map to HTTP errors (`422 DETECTION_FAILED / INVALID_INPUT`, `503 MODEL_UNAVAILABLE`, `500 INFERENCE_FAILED`).
- `pipeline/runner.py` — the orchestrator; stages in order: decode → `container.analyze_container` (rim detection via `vision/container_detector.py`, `surface_method="adaptive"`; gives `pixels_per_mm`, bulk volume, and a surface-isolated image that keeps full-image coordinates) → `grains.process_grains` (SAHI 640×640 slices + YOLO-seg, crop cleaning, optional DenseNet121 CNN classifier, ellipsoid 3D measurement, IQR size filter, uniformity) → geometry / weight / Bayes / regression estimates → `estimation/fusion.select_final_estimate` → `InferenceArtifactWriter` persists per-request results under `RESULTS_ROOT`.
- `estimator_mode` (`auto|bayes|regression|geometry|weight`): explicit modes raise if their estimator is unavailable; `auto` falls back Bayes hybrid → regression (ExtraTrees) → hybrid → geometry → weight, appending `*_SKIPPED` warnings.
- `estimation/feature_schema.py` is the single source of truth for the 31 regression features (version `31v1`, order, units, ranges). Feature assembly is in `pipeline/features.py`; never redefine the feature list elsewhere, and keep it in sync with the bundle's `feature_schema.json`. The `Estimated_Total_Seeds_Hybrid` feature uses the packing fraction the model was trained with (`hybrid_packing_fraction` from the bundle, default 1.0), which is distinct from `PACKING_FRACTION_GEOMETRY` (0.55) used by the geometry estimate.
- `models/` — lazy loaders/providers: `vision_models.py` (YOLO + Keras CNN, device from `YOLO_DEVICE`), `regression_loader.py` (bundle dir with model/scaler joblib + JSON metadata, plus legacy adapters), `bayes_loader.py` (params JSON at `models/weights/bayes_params_v1.json` or `BAYES_PARAMS_PATH`).

A running server or Colab runtime does not pick up source changes — restart it (and re-run the Colab setup cells) after editing `rice_ai`.
