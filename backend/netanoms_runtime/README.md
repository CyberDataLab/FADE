# Netanoms-runtime: A Real-Time Anomaly Detection Runtime for Network Traffic and System Calls

# Description

**netanoms-runtime** is a Python runtime library designed to deploy **real-time anomaly detection pipelines** over:

- Raw **network packets** (via *tshark*),
- Aggregated **network flows**, and
- **System calls** (via *bpftrace*),

using **pre-trained Machine Learning or Deep Learning models**.  
It integrates seamlessly with scikit-learn, TensorFlow, and other ML frameworks, and can be embedded into larger applications such as web servers (e.g., Django) or standalone Python services.

The runtime manages:

- Live data capture (local or remote through SSH),
- Feature extraction and transformation,
- Model inference using your trained pipelines,
- Optional SHAP/LIME explainability,
- Alerting, event reporting, and session lifecycle management.

This repository includes:

- The `netanoms_runtime` **Python module**,
- Utilities for model execution, explainability, and anomaly event notification,
- Modular handlers for packets, flows, and syscalls.

---

# Features

### 🔌 **Model-Agnostic Runtime**
Works with any ML/DL model (scikit-learn, TensorFlow, PyTorch, etc.) via standardized pipeline definitions.

### ⚙️ **Real-Time Packet / Flow / Syscall Processing**
Captures and processes live data from local hosts or remote servers through SSH.

### 📦 **Pipeline-Based Architecture**
Each anomaly-detection pipeline may contain:
- A trained ML model,
- Preprocessing steps (scalers, encoders, PCA, etc.),
- Optional training data for explainability.

### 🧠 **Built-In Explainability (SHAP / LIME)**
Generates SHAP/LIME artifacts to help operators understand why anomalies occur.

### 📡 **Extensible Capture Modes**
Support for:
- `packet` mode: raw packets (`tshark -T ek`),
- `flow` mode: packet aggregation into flows,
- `syscalls` mode: system call tracing via bpftrace.

### 🔔 **Callback and Alert System**
Real-time emission of:
- Status updates,
- Errors,
- Anomaly events and descriptions.

---

# Installation & Setup

## Requirements

- Python 3.10+
- `tshark` (for packet/flow capture)
- `bpftrace` (for syscall monitoring)
- (Optional) SSH access to remote capture environments

Check your Python version:

```bash
python --version

# Installation & Setup

## Prerequisites

Before installing **netanoms-runtime**, make sure your environment meets the following requirements:

+ Python 3.12 or higher
+ pip (Python package installer)
+ (Recommended) A virtual environment like venv or conda
+ `tshark` (for packet/flow capture)
+ `bpftrace` (for syscall monitoring)
+ (Optional) SSH access to remote capture environments

You can check your Python version with:
```bash
python --version
```

You can set up a virtual environment with:

```bash
python -m venv .venv
source .venv/bin/activate
```

## Installation Steps

To install the library, clone the repository and ensure dependencies are installed:

```bash
git clone <repo_url>
cd <repo_directory>
pip install -r requirements.txt
```

## Usage
The example file provided in the [examples folder](examples/) provides a step-by-step guide on using netanoms-runtime. 

Once you finish the offline training phase (data processing + feature engineering + model training), you can put your anomaly detection system into production using  key steps:

### 1. Import all the necessary components

In your Python script or notebook, begin by importing the necessary components from the netanoms_runtime library. 

```python
from netanoms_runtime.utils import build_pipelines_from_components
from netanoms_runtime.ssh_config import SSHConfig
from netanoms_runtime.capture_config import CaptureConfig
from netanoms_runtime.explainability_config import ExplainabilityConfig
from netanoms_runtime.detection import run_live_production
```

### 2. Build Pipelines From Trained Components

Use build_pipelines_from_components to create the runtime pipeline from your trained scaler, encoder, PCA, imputer, or other preprocessing steps, your trained model and, optionally, data to train the explainability model.

```python
trained_model = my_trained_model
scaler = my_fitted_scaler
pca = my_fitted_pca
X_train = training_features_array

pipelines = build_pipelines_from_components(
    model=trained_model,
    preprocessors=[scaler, pca],
    model_id="net-traffic-pipeline-v1",
    X_train=X_train,
)
```

This returns a list with a single PipelineDef, ready to be used by the runtime.

📌 Pipeline Structure (PipelineDef)

For clarity, this is the structure of each pipeline created with build_pipelines_from_components: 

```python
@dataclass
class PipelineDef:
    id: str
    model: Any
    steps: List[Tuple[str, Any]]
    X_train: Optional[Any] = None
```

- **id** → used to track and name pipelines during runtime
- **model** → your trained classifier/regressor/anomaly detector
- **steps** → preprocessing components applied in order
- **X_train** → (optional) required for SHAP or LIME explainability

### 3. Configure SSHConfig, CaptureConfig, and (Optional) Explainability

**SSH configuration**

```python
ssh = SSHConfig(
    username="your_host_username",
    host="your_ip",
    tshark_path="/usr/bin/tshark",
    bpftrace_path="/usr/bin/bpftrace",
    interface="eth0",
    sudo=True,
)
```

**Capture configuration**

```python
capture = CaptureConfig(
    mode='packet',
    ek=True,
    run_env="host",
)
```
Switching **modes** is as simple as changing the mode field (and providing a **bpftrace_script** in **syscalls** mode).

**(Optional) Explainability configuration**

If you want to enable SHAP or LIME explanations at runtime, configure **ExplainabilityConfig**:

```python
explainability = ExplainabilityConfig(
    kind="shap",
    module="shap",
    explainer_class="KernelExplainer",
)
```

To disable explainability, either omit this parameter or use **kind="none"**.

### 4. Create and run live production

The final step is to **start the live runtime**. You do this by calling **run_live_production** and providing a set of callbacks that will receive all the information produced by the library.

After this call:

- The library starts the capture process (tshark or bpftrace).
- A background thread reads the stream of events.
- Each event is processed through your pipeline(s).
- Anomalies, status messages, and errors are sent back through the callbacks you define.

You do not have to poll the library; everything is pushed via callbacks.

### 4.1 Define the callbacks

```python
def on_status(message: str):
    """
    Called for high-level runtime messages:
    - start/stop notifications
    - current mode (packet/flow/syscalls)
    - internal status updates
    """
    print(f"[STATUS] {message}")


def on_error(error):
    """
    Called whenever an error occurs in the capture process,
    the processing pipeline, or the explainability module.
    """
    print(f"[ERROR] {error}")


def on_anomaly(event: dict):
    """
    Called for every anomaly-related event.

    The 'event' dictionary is JSON-serializable and may include, among others:
    - timestamps and IDs
    - pipeline identifier
    - anomaly scores / predictions
    - basic contextual information (e.g. IPs, ports, process info)
    - (optionally) SHAP/LIME artifacts or metadata
    """
    print(f"[ANOMALY] {event}")

```

### 4.2 Start the live runtime

```python
handle = run_live_production(
    ssh=ssh,
    capture=capture,
    pipelines=pipelines,
    explainability=explainability,
    scenario_uuid="demo-session-001",
    execution=1,
    on_anomaly=on_anomaly,
    on_status=on_status,
    on_error=on_error,
)
```

At this point:

- **run_live_production** spawns the capture process.
- A monitoring thread is created.
- The function returns immediately with a ProductionHandle.
- The process continues in the background and your callbacks start receiving data as events occur.

You just keep your application running (e.g., a service loop, a web server, or a long-running script) and let the callbacks do the work.

### 4.3 Stop the runtime

When you want to stop the anomaly detection session (for example, during shutdown of your service), use the ProductionHandle:

```python
# Signal the library to stop capturing and processing
handle.stop()

# Wait for the background thread to finish cleanly
handle.join()
```

This will:

- Signal the internal loop to exit,
- Terminate the capture process,
- Close pipes and resources,
- Ensure no more callbacks are invoked.

# Folder structure
The repository is organized as follows:

```
.
├── examples
│   ├── example_packet
│   │   └── packet_traffic_anomalies        # Usage example with packet mode
│   ├── example_flow
│   │   └── flow_traffic_anomalies          # Usage example with flow mode
│   └── example_syscalls
│       └── syscalls_traffic_anomalies      # Usage example with syscalls mode
├── callbacks.py                            # Callback and event dispatching helpers
├── capture_config.py                       # Capture configuration definitions
├── detection.py                            # Main runtime entry point (run_live_production)
├── explainability_config.py                # SHAP/LIME configuration
├── handler_flow_traffic_anomalies.py       # Flow-level anomaly handler
├── handler_packet_traffic_anomalies.py     # Packet-level anomaly handler
├── handler_syscalls_anomalies.py           # Syscall-level anomaly handler
├── LICENSE                                 # License file
├── pipeline_def.py                         # PipelineDef and build_pipelines_from_components
├── production_handle.py                    # Control interface for running sessions
├── README.md                               # Documentation (this file)
├── ssh_config.py                           # SSH and binary path configuration
├── state.py                                # Shared counters and thread controls
└── utils.py                                # Utility functions (command building, IP tools, etc.)
```

# License
This project is licensed under the [MIT License](LICENSE).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Contact & Support
For questions or support, contact the author:
- Eduardo López Bernal (eduardo.lopez5@um.es)