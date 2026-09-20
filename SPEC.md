# AI-Powered Predictive Maintenance System for CNC Machines and 3D Printers
## System Architecture & Technical Specification

---

## 1. Project Overview & Scope
This project delivers a real-time, AI-driven Predictive Maintenance (PdM) platform designed specifically for CNC Milling Machines and Industrial 3D Printers. The system ingests streaming sensor telemetry, detects operational anomalies, estimates Health Index (HI) and Remaining Useful Life (RUL), and classifies failure risks before critical equipment breakdowns occur.

### Key Capabilities
- **Multi-Machine Telemetry Simulation**: Realistic generation of high-frequency sensor readings (temperature, vibration, current draw, spindle/motor RPM, operating hours, workload, tool wear).
- **Multi-Scenario Simulation Modes**: Baseline operational scenarios covering `normal`, `degrading`, and `near_failure` states.
- **Predictive Analytics & Anomaly Detection**: Machine learning models (XGBoost, Scikit-learn) trained to identify early degradation patterns and estimate machine health.
- **RESTful API Backend**: High-performance FastAPI server delivering telemetry ingestion, health scoring endpoints, model inference, and alert triggers.
- **Interactive Operator Dashboard**: Streamlit web interface featuring real-time telemetry visualizations (Plotly), machine status cards, SHAP explainability insights, and alert histories.

---

## 2. Directory Structure & Module Responsibilities

```
predictive-maintenance-ai/
├── app/                  # Streamlit dashboard interface & UI visual components
├── simulator/            # Telemetry simulation engines for CNC and 3D Printers
├── ml/                   # Model training, feature engineering, evaluation, SHAP explainability & inference
├── backend/              # FastAPI REST endpoints, request schemas & service layers
│   ├── main.py           # FastAPI app instance and versioned route registration
│   ├── schemas.py        # Pydantic v2 validation request & response schemas
│   └── services/         # Business logic for telemetry, predictions, and maintenance
├── database/             # SQLAlchemy ORM models & SQLite connection management
│   ├── connection.py     # SQLite engine, sessionmaker, and init_db helpers
│   └── models.py         # ORM entities (Machine, TelemetryReading, PredictionRecord, MaintenanceEvent)
├── data/
│   ├── raw/              # Simulated / raw ingested sensor telemetry logs
│   ├── processed/        # Cleaned, transformed & feature-engineered datasets
│   └── predictive_maintenance.db  # Local SQLite database instance (git-ignored)
├── models/               # Serialized model binaries (.joblib, .json), scalers & explainers
├── tests/                # Automated pytest suite & environment verification scripts
├── artifacts/            # Generated charts, metrics reports, training logs & scratch outputs
├── config/               # Centralized configuration, shared schema & validation rules
├── .gitignore            # Version control exclusion rules
├── requirements.txt      # Pinned dependency manifest for existing environment
├── environment.yml       # Conda environment definition for reproducibility
└── SPEC.md               # Complete project specification and architecture document
```

### Module Responsibilities
- **`app/`**: User-facing web application. Displays real-time machine telemetry, health index gauges, failure risk predictions, and SHAP model explainability charts.
- **`simulator/`**: Pure Python telemetry generation engine. Simulates realistic physical dynamics (thermal dissipation, vibration spikes, tool degradation, electrical current fluctuations) for CNC machines and 3D printers.
- **`ml/`**: Machine Learning pipeline. Handles data preprocessing, sliding-window feature engineering, model training (XGBoost/RandomForest), evaluation metrics, model persistence, and SHAP explainability (`ml/explainability.py`).
- **`backend/`**: FastAPI REST service. Ingests live telemetry streams, interacts with database models, invokes ML inference services, and exposes API endpoints for the dashboard.
- **`database/`**: Persistence layer using SQLAlchemy ORM. Manages historical sensor readings, machine metadata, model predictions, and maintenance records.
- **`config/`**: Shared domain schemas (`config/schema.py`), validation limits, and system settings. Ensures consistent data contracts across simulator, backend, ML, and dashboard.
- **`tests/`**: Suite of unit, integration, and environmental sanity tests (`check_environment.py`, `test_simulator.py`, `test_data_preparation.py`, `test_model_training.py`, `test_explainability.py`, `test_database.py`, `test_api.py`).

---

## 3. Shared Telemetry Data Schema

All telemetry readings across the system adhere to a strict shared contract defined in `config/schema.py`.

### Core Schema (First 8 Fields)
These 8 fields form the mandatory baseline core schema present in all standard telemetry payloads:

| Field Name | Type | Description | Unit / Format | Example |
| :--- | :--- | :--- | :--- | :--- |
| `machine_id` | `str` | Unique machine identifier | String ID | `"CNC-001"`, `"PRINTER-3D-02"` |
| `timestamp` | `datetime` | Reading timestamp | UTC ISO 8601 | `2026-10-02T18:45:00Z` |
| `machine_type` | `str` | Type of machine equipment | Enum: `"CNC"`, `"3D_Printer"` | `"CNC"` |
| `temp` | `float` | Operating temperature | Degrees Celsius (°C) | `65.4` |
| `vibration` | `float` | Vibration intensity | mm/s RMS | `2.85` |
| `current` | `float` | Electrical current draw | Amperes (A) | `14.2` |
| `rpm` | `int` | Spindle / motor speed | Rotations Per Minute | `12000` |
| `hours` | `float` | Cumulative operating hours | Hours (h) | `1450.5` |

### Extension Schema (Remaining 4 Fields)
These 4 fields extend the core schema to support simulation controls, advanced feature engineering, and ground-truth validation:

| Field Name | Type | Description | Range / Values | Example |
| :--- | :--- | :--- | :--- | :--- |
| `workload` | `float` | Operational workload percentage | `0.0` to `100.0` (%) | `85.0` |
| `tool_wear` | `float` | Tool/nozzle wear index | `0.0` (new) to `1.0` (worn) | `0.42` |
| `health_index` | `float` | Ground-truth machine health score | `0.0` (failed) to `100.0` (perfect) | `88.5` |
| `scenario` | `str` | Simulator operational scenario state | Enum: `"normal"`, `"degrading"`, `"near_failure"` | `"degrading"` |

### Allowed Scenarios
The simulator emits telemetry under three explicit scenario states:
1. `normal`: Equipment operating within baseline parameter ranges. Low vibration, stable temperature, minimal wear.
2. `degrading`: Incipient wear detected. Gradual elevation in temperature, rising vibration RMS, increased current draw.
3. `near_failure`: Severe mechanical/thermal degradation. High vibration spikes, thermal threshold exceedance, unstable current, critical failure risk.

---

## 4. Strict Data-Leakage & Governance Rules

To guarantee realistic, production-grade machine learning performance, strict data governance rules are enforced across all training and evaluation pipelines:

1. **Target & Ground-Truth Isolation**:
   - `health_index` and `scenario` are simulator ground-truth indicators ONLY.
   - `health_index` and `scenario` MUST NEVER be used as feature inputs when training or evaluating predictive models.
2. **Feature vs. Ground-Truth Boundaries**:
   - Sensor telemetry inputs (`temp`, `vibration`, `current`, `rpm`, `hours`, `workload`, `tool_wear`) are valid candidate predictive features for simulator telemetry.
3. **Preprocessing & Scaling Boundaries**:
   - Feature scaling parameters (`StandardScaler`) are fit strictly on training splits within Scikit-learn pipelines.
4. **Data Contract Compatibility Isolation**:
   - Equipment telemetry ingestion (`POST /api/v1/telemetry`) accepts simulator schema fields.
   - Machine failure prediction (`POST /api/v1/predictions`) accepts exact AI4I benchmark model features (`type`, `air_temperature_c`, `process_temperature_c`, `rotational_speed_rpm`, `torque_nm`, `tool_wear_min`).
   - Simulator telemetry is NOT passed directly into the AI4I prediction model.

---

## 5. Configurable Validation Limits vs. Operational Safety

Telemetry parameters are validated against documented, configurable operational ranges defined in `config/schema.py`:

| Parameter | Min Value | Max Value | Default Unit | Note |
| :--- | :--- | :--- | :--- | :--- |
| `temp` | `-20.0` | `200.0` | °C | Thermal operational range |
| `vibration` | `0.0` | `100.0` | mm/s RMS | Vibration operational range |
| `current` | `0.0` | `200.0` | Amperes | Electrical load range |
| `rpm` | `0` | `50000` | RPM | Spindle / motor speed range |
| `hours` | `0.0` | `100000.0` | Hours | Operating lifetime limit |
| `workload` | `0.0` | `100.0` | % | Load percentage range |
| `tool_wear` | `0.0` | `100.0` | Index / % | Tool wear range |
| `health_index` | `0.0` | `100.0` | % | Health percentage range |

---

## 6. Phase 6 Backend API & Database Specification

### Database Schema (SQLite via SQLAlchemy ORM)
- **Database Storage Path**: `data/predictive_maintenance.db` (git-ignored)
- **ORM Tables**:
  - `machines`: Equipment registry (`id`, `machine_id`, `machine_type`, `created_at`).
  - `telemetry_readings`: Sensor readings (`id`, `machine_id`, `timestamp`, `temp`, `vibration`, `current`, `rpm`, `hours`, `workload`, `tool_wear`, `health_index`, `scenario`, `created_at`). Unique index on `(machine_id, timestamp)`.
  - `prediction_records`: ML prediction history (`id`, `machine_id`, `created_at`, `failure_probability`, `classification_threshold`, `predicted_class`, `predicted_label`, `model_name`, `input_features_json`, `model_metadata_version`).
  - `maintenance_events`: Maintenance logs (`id`, `machine_id`, `event_type`, `description`, `event_timestamp`, `status`, `created_at`).

### Versioned API Endpoints (`/api/v1`)
- **System**:
  - `GET /health`: Database health check.
  - `GET /ready`: Model loading & database readiness check.
- **Machines**:
  - `POST /api/v1/machines`: Register machine.
  - `GET /api/v1/machines`: List machines.
  - `GET /api/v1/machines/{machine_id}`: Retrieve machine by ID.
- **Telemetry**:
  - `POST /api/v1/telemetry`: Single reading ingestion.
  - `POST /api/v1/telemetry/batch`: Atomic batch ingestion.
  - `GET /api/v1/telemetry`: Query readings with filters & pagination.
  - `GET /api/v1/telemetry/{reading_id}`: Retrieve reading by ID.
- **Failure Prediction**:
  - `POST /api/v1/predictions`: Execute failure prediction (XGBoost production model, threshold `0.33`).
  - `GET /api/v1/predictions`: List prediction history.
  - `GET /api/v1/predictions/{prediction_id}`: Retrieve prediction record by ID.
  - `POST /api/v1/predictions/explain`: Local SHAP explanation endpoint.
- **Maintenance**:
  - `POST /api/v1/maintenance`: Schedule/log maintenance event.
  - `GET /api/v1/maintenance`: Query maintenance events.
  - `GET /api/v1/maintenance/{event_id}`: Retrieve event by ID.

---

## 7. Execution Commands

#### Start Backend Service:
```bash
& "D:\ML_study\envs\study\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

#### Run Full Test Suite:
```bash
& "D:\ML_study\envs\study\python.exe" -m pytest -q
```

---
*Document Version: 1.1.0 | Phase 6 Backend API & Database Specification*
