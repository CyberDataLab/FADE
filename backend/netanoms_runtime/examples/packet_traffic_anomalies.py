from netanoms_runtime.utils import build_pipelines_from_components, extract_features_by_packet_from_pcap
from netanoms_runtime.ssh_config import SSHConfig
from netanoms_runtime.capture_config import CaptureConfig
from netanoms_runtime.explainability_config import ExplainabilityConfig
from netanoms_runtime.detection import run_live_production

from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

import time

with open("capture.pcap", "rb") as f:
    df = extract_features_by_packet_from_pcap(f)

excluded_numeric = ['src_port', 'dst_port']

numeric_cols = [col for col in df.select_dtypes(include=['number']).columns if col not in excluded_numeric]

X_train = df[numeric_cols]

scaler = StandardScaler()

X_scaled = scaler.fit_transform(X_train)

model = IsolationForest(
    n_estimators=100,
    max_samples='auto',
    contamination='auto',
    max_features=1.0,
    random_state=42,
)

model.fit(X_scaled)

pipelines = build_pipelines_from_components(
    model=model,
    preprocessors=[scaler],
    model_id="packet_traffic_anomalies_model",
    X_train=X_scaled,
)

ssh = SSHConfig(
    username="your_host_username",
    host="your_ip",
    tshark_path="/usr/bin/tshark",
    bpftrace_path="/usr/bin/bpftrace",
    interface="eth0",
    sudo=True,
)

capture = CaptureConfig(
    mode='packet',
    ek=True,
    run_env="host",
)

explainability = ExplainabilityConfig(
    kind="shap",
    module="shap",
    explainer_class="KernelExplainer",
)

def on_status(message: str):
    print(f"[STATUS] {message}")


def on_error(error):
    print(f"[ERROR] {error}")


def on_anomaly(event: dict):
    print(f"[ANOMALY] {event}")

handle = run_live_production(
    ssh=ssh,
    capture=capture,
    pipelines=pipelines,
    explainability=explainability,
    scenario_uuid="packet_traffic_anomaly_detection",
    execution=1,
    on_anomaly=on_anomaly,
    on_status=on_status,
    on_error=on_error,
)

time.sleep(10)

handle.stop()

handle.join()

