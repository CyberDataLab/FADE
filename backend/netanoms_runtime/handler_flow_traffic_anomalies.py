from typing import List, Optional
import json
import time
from collections import defaultdict
import pandas as pd
import numpy as np
import logging
from netanoms_runtime.pipeline_def import PipelineDef
from netanoms_runtime.explainability_config import ExplainabilityConfig
from netanoms_runtime.utils import (get_next_anomaly_index, save_shap_bar_local, 
                                    save_lime_bar_local, ip_to_int, int_to_ip, 
                                    build_anomaly_description,check_and_send_email_alerts, 
                                    df_from_ra_csv_lines, PROTOCOL_MAP, PROTOCOL_REVERSE_MAP)

from netanoms_runtime.callbacks import save_anomaly_metrics

from .state import thread_controls, ip_anomaly_counter, port_anomaly_counter

logger = logging.getLogger('backend')

"""Handler for real-time flow traffic anomaly detection and explainability."""

def handle_flow_traffic_anomalies(
    proc,
    pipelines: List["PipelineDef"],
    *,
    explainability: Optional["ExplainabilityConfig"] = None,
    execution: int = 1,
    scenario_uuid: Optional[str] = None,
) -> None:    
    """
    Handle real-time prediction on network flows extracted from packet captures.
    This function processes packets grouped into flows, applies preprocessing steps,
    runs anomaly detection models, and triggers explainability modules (SHAP/LIME)
    when anomalies are found.

    Args:
        proc: The subprocess capturing the traffic.
        pipelines: List of tuples (element_id, model, steps, X_train).
        scenario_model: The Django model instance for storing metrics.
        design: The visual scenario configuration (nodes and connections).
        config: The backend config.json loaded object.
        execution: The Execution object linked to this run.
        uuid: The unique identifier for this scenario instance.
        scenario: The Scenario object with scenario metadata.
    """

    image_counter = get_next_anomaly_index(scenario_uuid)

    buf: list[str] = []
    last_flush = time.time()

    # Time interval in seconds to flush the flow data
    interval = 1

    header_skipped = False

    # Keep processing while the thread control flag is True
    while thread_controls.get(scenario_uuid, True):
        # Read a line from the subprocess output
        line = proc.stdout.readline()

        if line == "" or line == b"":
            rc = proc.poll()
            try:
                err = proc.stderr.read() if getattr(proc, "stderr", None) else ""
            except Exception:
                err = ""
            logger.error(
                f"[HANDLE FLOW] EOF: el proceso de captura terminó (returncode={rc}, execution={execution}). "
                f"stderr:\n{err}"
            )
            break

        if isinstance(line, (bytes, bytearray)):
            line = line.decode("utf-8", errors="replace")

        logger.debug(f"[HANDLE FLOW] Read line: {line!r}")

        line = line.strip()
        if not line:
            continue

        if not header_skipped:
            low = line.lower()
            if "srcaddr" in low and "dstaddr" in low and "proto" in low:
                header_skipped = True
                logger.debug(f"[HANDLE FLOW] CSV header detected and skipped: {line}")
                continue
            header_skipped = True

        if "," in line and not line.lower().startswith(("ra ", "argus", "dumpcap")):
            buf.append(line)

        # Check if it's time to flush the flow data
        if time.time() - last_flush >= interval:
            df = df_from_ra_csv_lines(buf)
            buf.clear()
            last_flush = time.time()

            if df.empty:
                continue

            anomaly_context = {
                "source": "argus_ra_csv",
                "interval_s": interval,
            }

            # Process each pipeline: preprocessing + model inference
            for pipe in pipelines:
                model_id = pipe.id
                model_instance = pipe.model
                steps = pipe.steps
                X_train = pipe.X_train

                df_proc = df.copy()
                
                # Apply preprocessing steps
                for step_type, transformer in steps:
                    if step_type in ["StandardScaler", "MinMaxScaler", "Normalizer", "KNNImputer", "PCA"]:
                        expected_cols = transformer.feature_names_in_
                        logger.info(f"[HANDLE FLOW] Transformer {step_type} expects columns: {expected_cols}")
                        
                        df_proc_transformable = df_proc.reindex(columns=expected_cols, fill_value=0)

                        df_proc_transformed = transformer.transform(df_proc_transformable)

                        df_proc_transformed = pd.DataFrame(df_proc_transformed, columns=expected_cols, index=df_proc.index)

                        df_proc[expected_cols] = df_proc_transformed

                    elif step_type == "OneHotEncoding":
                        df_proc = pd.get_dummies(df_proc)

                # Convert IP addresses to integers and protocols to codes
                for ip_col in ['src', 'dst']:
                    if ip_col in df_proc.columns:
                        df_proc[ip_col] = df_proc[ip_col].apply(ip_to_int)

                # Convert protocols to codes
                if 'protocol' in df_proc.columns:
                    def protocol_to_code(p):
                        if isinstance(p, str):
                            p_clean = p.strip().upper()
                            code = PROTOCOL_REVERSE_MAP.get(p_clean, -1)
                            if code == -1:
                                logger.warning(f"[HANDLE FLOW] Unknown protocol: {p}")
                            return code
                        return p

                    df_proc['protocol'] = df_proc['protocol'].apply(protocol_to_code)

                logger.info("[HANDLE FLOW] Processed DataFrame before prediction:")
                logger.info("[HANDLE FLOW] Columns: %s", df_proc.columns.tolist())

                # Predict anomalies (-1 → anomaly → 1, 1 → normal → 0)
                preds = model_instance.predict(df_proc)
                preds = [1 if x == -1 else 0 for x in preds]

                df_proc["anomaly"] = preds
                df["anomaly"] = preds

                logger.info(f"[HANDLE FLOW] {model_instance.__class__.__name__} → Anomalies detected: {sum(preds)}")

                # Continue only if anomalies were detected
                df_anomalous = df_proc[df_proc["anomaly"] == 1]

                if not df_anomalous.empty:
                    logger.info("[HANDLE FLOW] Explaining detected anomalies...")

                    # If no explainability node (SHAP or LIME) is connected
                    if explainability is None or explainability.kind == "none":
                        logger.info("[HANDLE FLOW] No explainability node connected — saving anomaly without explanation.")

                        # Remove the 'anomaly' column from the anomalous DataFrame
                        anomalous_data = df_anomalous.drop(columns=["anomaly"])

                        for i, row in anomalous_data.iterrows():
                            # Construct a simple textual description of the anomaly
                            anomaly_description = build_anomaly_description(row)

                            # Track source IP and port for alerting policies
                            ip_src = df.loc[i, 'src']
                            port_src = df.loc[i, 'src_port']

                            if ip_src:
                                ip_anomaly_counter[ip_src] += 1
                                check_and_send_email_alerts(ip_anomaly_counter, port_anomaly_counter)

                            if port_src != -1:
                                port_anomaly_counter[port_src] += 1
                                check_and_send_email_alerts(ip_anomaly_counter, port_anomaly_counter)

                        logger.info("[HANDLE FLOW] Saving anomaly without explanation.")
                        logger.info("[HANDLE FLOW] Description: %s", anomaly_description)

                        save_anomaly_metrics(
                            model_name=model_instance.__class__.__name__,
                            feature_name="",
                            feature_values="",
                            anomalies=anomaly_description,
                            execution=execution,
                            production=True,
                            anomaly_details=json.dumps(pkt, indent=2),
                            global_shap_images=[],
                            local_shap_images=[],
                            global_lime_images=[],
                            local_lime_images=[] 
                        )

                        continue

                    # An explainability node (SHAP or LIME) is connected
                    else:
                        logger.info(f"[HANDLE PACKET] Explainability node found.")

                        kind = explainability.kind

                        # Determine explainer type and class
                        explainer_module_path = explainability.module or (
                            "shap" if kind == "shap" else "lime"
                        )

                        explainer_type = explainability.explainer_class
                        explainer_kwargs = explainability.explainer_kwargs or {}

                        # Validate configuration before attempting explanation
                        if not explainer_module_path or not explainer_type:
                            logger.warning(f"[HANDLE PACKET] Missing configuration for explainability node of type {kind}")
                        else:
                            # Prepare input data and isolate anomalous rows
                            input_data = df_proc.drop(columns=["anomaly"])
                            anomalous_data = df_anomalous.drop(columns=["anomaly"])

                            def clean_for_json(obj):
                                """
                                Recursively clean an object to ensure it's safe for JSON serialization.
                                
                                - Replaces NaN and infinite floats with 0.0
                                - Replaces None with 0.0
                                - Handles nested dictionaries recursively

                                Parameters:
                                    obj (Any): The input object to clean (can be dict, float, None, or any other type)

                                Returns:
                                    Any: The cleaned object, safe for JSON serialization.
                                """

                                # If the object is a dictionary, clean each key-value pair recursively
                                if isinstance(obj, dict):
                                    return {k: clean_for_json(v) for k, v in obj.items()}
                                elif isinstance(obj, float):
                                    if np.isnan(obj) or np.isinf(obj):
                                        return 0.0
                                elif obj is None:
                                    return 0.0 
                                return obj

                            try:
                                import importlib

                                expl_mod = importlib.import_module(explainer_module_path)
                                explainer_class = getattr(expl_mod, explainer_type)
                            except Exception as e:
                                logger.warning(
                                    "[HANDLE PACKET] Could not import explainer %s.%s: %s",
                                    explainer_module_path,
                                    explainer_type,
                                    e,
                                )
                                explainer_class = None

                            logger.info(f"kind: {kind}, explainer_type: {explainer_type}")

                            for i, row in anomalous_data.iterrows():
                                row_df = row.to_frame().T 

                                # === SHAP Explanation ===
                                if kind == "shap":
                                    if explainer_type == "KernelExplainer":
                                        def anomaly_score(X):
                                            """
                                            Computes the anomaly score using the model's decision function.

                                            This function is designed to be compatible with explainability tools like LIME.
                                            It converts the input to a pandas DataFrame if it is a NumPy array, ensuring that
                                            column names align with those used during training.

                                            Args:
                                                X (np.ndarray or pd.DataFrame): The input data for which to compute the anomaly scores.

                                            Returns:
                                                np.ndarray: The reshaped anomaly scores as a column vector.
                                            """
                                            if isinstance(X, np.ndarray):
                                                X = pd.DataFrame(X, columns=X_train.columns)
                                            scores = model_instance.decision_function(X)
                                            return scores

                                        explainer = explainer_class(anomaly_score, X_train)

                                    elif explainer_type in ["LinearExplainer", "TreeExplainer", "DeepExplainer"]:
                                        explainer = explainer_class(model_instance, X_train)

                                    else:
                                        explainer = explainer_class(model_instance)

                                    shap_values = explainer(row_df)

                                    logger.info(f"[HANDLE FLOW] SHAP input: {row_df.columns}")
                                    logger.info(f"[HANDLE FLOW] SHAP training columns: {X_train.columns}")

                                    # Extract top contributing feature
                                    contribs = shap_values[0].values 
                                    shap_contribs = sorted(
                                        zip(contribs, row.values, row.index),
                                        key=lambda x: abs(x[0]),
                                        reverse=True
                                    )
                                    top_feature = shap_contribs[0]
                                    feature_name = top_feature[2]

                                    # Build human-readable anomaly description
                                    src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                    dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                    anomaly_description = build_anomaly_description(row)

                                    # Track source IP and port for alerting policies
                                    ip_src = df.loc[i, 'src']
                                    port_src = df.loc[i, 'src_port']

                                    if ip_src:
                                        ip_anomaly_counter[ip_src] += 1
                                        check_and_send_email_alerts(ip_anomaly_counter, port_anomaly_counter)

                                    if port_src != -1:
                                        port_anomaly_counter[port_src] += 1
                                        check_and_send_email_alerts(ip_anomaly_counter, port_anomaly_counter)

                                    # Ensure src_port and dst_port are integers
                                    for col in ['src_port', 'dst_port']:
                                        if col in row and not pd.isnull(row[col]):
                                            try:
                                                row[col] = int(row[col])
                                            except:
                                                row[col] = -1

                                    # Convert row to dictionary, applying .item() when needed
                                    feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()

                                    # Ensure IPs are strings and ports are integers
                                    for ip_key in ['src', 'dst']:
                                        val = df.loc[i, ip_key]
                                        feature_values[ip_key] = val if isinstance(val, str) else "UNDEFINED"

                                    for port_key in ['src_port', 'dst_port']:
                                        if port_key in feature_values:
                                            try:
                                                feature_values[port_key] = int(float(feature_values[port_key]))
                                            except:
                                                feature_values[port_key] = "N/A"

                                    # Add protocol information
                                    proto_code = df.loc[i, 'protocol']
                                    feature_values['protocol'] = PROTOCOL_MAP.get(str(proto_code), proto_code)

                                    logger.info(f"[HANDLE FLOW] SHAP anomaly #{i}, top feature: {feature_name}")
                                    logger.info(f"[HANDLE FLOW] Generating anomaly record with index: {image_counter}")

                                    anomaly_details = "\n".join([
                                        f"{k}: {v}" for k, v in feature_values.items()
                                    ])

                                    logger.info("Anomaly details: %s", anomaly_details)

                                    # Save local SHAP explanation as a bar chart
                                    shap_paths = [save_shap_bar_local(shap_values[0], scenario_uuid, image_counter)]

                                    logger.info(f"[HANDLE FLOW] Anomaly record with index: {image_counter} generated")

                                    # Save the anomaly metrics with SHAP explanations
                                    save_anomaly_metrics(
                                        model_name=model_instance.__class__.__name__,
                                        feature_name=feature_name,
                                        feature_values=clean_for_json(feature_values),
                                        anomalies=anomaly_description,
                                        execution=execution,
                                        production=True,
                                        anomaly_details=anomaly_details,
                                        global_shap_images=[],
                                        local_shap_images=shap_paths,
                                        global_lime_images=[],
                                        local_lime_images=[]
                                    )

                                    # Increase index for next anomaly
                                    image_counter += 1

                                # === LIME Explanation ===
                                elif kind == "lime":
                                    logger.info(f"[HANDLE FLOW] Explaining row {i} with LIME...")

                                    explainer = explainer_class(
                                        training_data=X_train.values,
                                        feature_names=X_train.columns.tolist(),
                                        mode="regression"
                                    )

                                    def anomaly_score(X):
                                        """
                                        Computes the anomaly score using the model's decision function.

                                        This function is designed to be compatible with explainability tools like LIME.
                                        It converts the input to a pandas DataFrame if it is a NumPy array, ensuring that
                                        column names align with those used during training.

                                        Args:
                                            X (np.ndarray or pd.DataFrame): The input data for which to compute the anomaly scores.

                                        Returns:
                                            np.ndarray: The reshaped anomaly scores as a column vector.
                                        """
                                        if isinstance(X, np.ndarray):
                                            X = pd.DataFrame(X, columns=X_train.columns)
                                        return model_instance.decision_function(X).reshape(-1, 1)

                                    # Generate local explanation for the current row
                                    exp = explainer.explain_instance(
                                        row.values,
                                        anomaly_score,
                                        num_features=10
                                    )

                                    # Sort contributions by absolute value and get most relevant feature
                                    sorted_contribs = sorted(exp.as_list(), key=lambda x: abs(x[1]), reverse=True)
                                    feature_name = sorted_contribs[0][0] 

                                    # Ensure src_port and dst_port are integers
                                    for col in ['src_port', 'dst_port']:
                                        if col in row and not pd.isnull(row[col]):
                                            try:
                                                row[col] = int(row[col])
                                            except:
                                                row[col] = -1

                                    # Convert row to dictionary, applying .item() when needed
                                    feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()
                                    for ip_key in ['src', 'dst']:
                                        if ip_key in feature_values:
                                            val = feature_values[ip_key]
                                            if isinstance(val, str):
                                                feature_values[ip_key] = val  
                                            elif isinstance(val, (int, float)):
                                                try:
                                                    feature_values[ip_key] = int_to_ip(int(val))
                                                except:
                                                    feature_values[ip_key] = "UNDEFINED"
                                            else:
                                                feature_values[ip_key] = "UNDEFINED"

                                    # Normalize protocol name
                                    feature_values['protocol'] = PROTOCOL_MAP.get(str(feature_values.get('protocol', '')), feature_values.get('protocol', 'UNKNOWN'))

                                    # Build textual anomaly description
                                    src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                    dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                    anomaly_description = build_anomaly_description(row)

                                    # Format full anomaly details for display or database
                                    anomaly_details = "\n".join([
                                        f"{k}: {v}" for k, v in feature_values.items()
                                    ])

                                    # Save local explanation as LIME bar chart
                                    lime_path = [save_lime_bar_local(exp, scenario_uuid, image_counter)]

                                    logger.info("[HANDLE FLOW] Anomaly details: %s", anomaly_details)

                                    # Save the anomaly metrics with LIME explanations
                                    save_anomaly_metrics(
                                        model_name=model_instance.__class__.__name__,
                                        feature_name=feature_name,
                                        feature_values=clean_for_json(feature_values),
                                        anomalies=anomaly_description,
                                        execution=execution,
                                        production=True,
                                        anomaly_details=anomaly_details,
                                        global_shap_images=[],
                                        local_shap_images=[],
                                        global_lime_images=[],
                                        local_lime_images=lime_path
                                    )

                                    # Increase index for next anomaly
                                    image_counter += 1

                                else:
                                    logger.warning(f"[HANDLE FLOW] Explainability kind not supported yet: {kind}")
    