from typing import List, Optional
import json
import pandas as pd
import numpy as np
import logging
from netanoms_runtime.pipeline_def import PipelineDef
from netanoms_runtime.explainability_config import ExplainabilityConfig
from netanoms_runtime.utils import (get_next_anomaly_index, save_shap_bar_local, 
                                    save_lime_bar_local, build_anomaly_description)

from netanoms_runtime.callbacks import save_anomaly_metrics

from .state import thread_controls

logger = logging.getLogger('backend')

"""Handler for real-time syscalls anomaly detection and explainability."""

def handle_syscalls_anomalies(
    proc,
    pipelines: List["PipelineDef"],
    *,
    explainability: Optional["ExplainabilityConfig"] = None,
    execution: int = 1,
    scenario_uuid: Optional[str] = None,
) -> None:
    """
    Handles real-time syscall-based anomaly prediction and explainability.

    This function continuously reads JSON lines from the `proc.stdout` stream,
    converts them into a pandas DataFrame, applies the configured preprocessing
    pipelines, and runs anomaly detection models. For each detected anomaly, it
    optionally generates SHAP or LIME explanations (when an explainability node
    is connected in the design) and persists the results using `save_anomaly_metrics`.

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

    # Keep processing while the thread control flag is True
    while thread_controls.get(scenario_uuid, True):
        # Read a line from the subprocess output
        line = proc.stdout.readline()

        if not line:
            continue

        try:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue 

            df = pd.DataFrame([data])

            df_copy = df.copy() 
            
            if df.empty:
                continue

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
                        logger.info(f"[HANDLE PACKET] Transformer {step_type} expects columns: {expected_cols}")
                        
                        df_proc_transformable = df_proc.reindex(columns=expected_cols, fill_value=0)

                        df_proc_transformed = transformer.transform(df_proc_transformable)

                        df_proc_transformed = pd.DataFrame(df_proc_transformed, columns=expected_cols, index=df_proc.index)

                        df_proc[expected_cols] = df_proc_transformed

                    elif step_type == "OneHotEncoding":
                        df_proc = pd.get_dummies(df_proc)

                
                logger.info("[HANDLE PACKET] Processed DataFrame before prediction:")
                logger.info("[HANDLE PACKET] Columns: %s", df_proc.columns.tolist())

                # Predict anomalies (-1 → anomaly → 1, 1 → normal → 0)
                preds = model_instance.predict(df_proc)
                preds = [1 if x == -1 else 0 for x in preds]

                df_proc["anomaly"] = preds
                df["anomaly"] = preds

                logger.info(f"[HANDLE PACKET] {model_instance.__class__.__name__} → Anomalies detected: {sum(preds)}")

                # Continue only if anomalies were detected
                df_anomalous = df_proc[df_proc["anomaly"] == 1]

                if not df_anomalous.empty:
                    logger.info("[HANDLE PACKET] Explaining detected anomalies...")

                    
                    # If no explainability node (SHAP or LIME) is connected
                    if explainability is None or explainability.kind == "none":
                        logger.info("[HANDLE PACKET] No explainability node connected.")

                        # Remove the 'anomaly' column from the anomalous DataFrame
                        anomalous_data = df_anomalous.drop(columns=["anomaly"])

                        for i, row in anomalous_data.iterrows():

                            # Construct a simple textual description of the anomaly
                            anomaly_description = build_anomaly_description(row)


                        logger.info("[HANDLE PACKET] Saving anomaly without explanation.")
                        logger.info("[HANDLE PACKET] Description: %s", anomaly_description)

                        save_anomaly_metrics(
                            model_name=model_instance.__class__.__name__,
                            feature_name="",
                            feature_values="",
                            anomalies=anomaly_description,
                            execution=execution,
                            production=True,
                            anomaly_details=json.dumps(data, indent=2),
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

                                    logger.info(f"[HANDLE PACKET] SHAP input: {row_df.columns}")
                                    logger.info(f"[HANDLE PACKET] SHAP training columns: {X_train.columns}")

                                    # Extract top contributing feature
                                    contribs = shap_values[0].values 
                                    shap_contribs = sorted(
                                        zip(contribs, row.values, row.index),
                                        key=lambda x: abs(x[0]),
                                        reverse=True
                                    )

                                    top_feature = shap_contribs[0]
                                    feature_name = top_feature[2]

                                    # Construct a detailed anomaly description
                                    if i in df_copy.index:
                                        original_row = df_copy.loc[i]
                                    else:
                                        original_row = row  # fallback si no coincide
                                    anomaly_description = build_anomaly_description(original_row)

                                    feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()

                                    logger.info(f"[HANDLE PACKET] SHAP anomaly #{i}, top feature: {feature_name}")
                                    logger.info(f"[HANDLE PACKET] Generating anomaly record with index: {image_counter}")

                                    anomaly_details = "\n".join([
                                        f"{k}: {v}" for k, v in feature_values.items()
                                    ])

                                    logger.info("[HANDLE PACKET] Anomaly details: %s", anomaly_details)

                                    shap_paths = [save_shap_bar_local(shap_values[0], scenario_uuid, image_counter)]

                                    logger.info(f"[HANDLE PACKET] Anomaly with index: {image_counter} generated")

                                    # Save the anomaly metrics with SHAP explanations
                                    save_anomaly_metrics(
                                        model_name=model_instance.__class__.__name__,
                                        feature_name=feature_name,
                                        feature_values=clean_for_json(feature_values),
                                        anomalies=anomaly_description,
                                        execution=execution,
                                        production=True,
                                        anomaly_details=json.dumps(data, indent=2),
                                        global_shap_images=[],
                                        local_shap_images=shap_paths,
                                        global_lime_images=[],
                                        local_lime_images=[]
                                    )

                                    # Increase index for next anomaly
                                    image_counter += 1

                                # === LIME Explanation ===
                                elif kind == "lime":
                                    logger.info(f"[HANDLE PACKET] Explaining row {i} with LIME...")

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

                                    if i in df_copy.index:
                                        original_row = df_copy.loc[i]
                                    else:
                                        original_row = row  # fallback si no coincide
                                    anomaly_description = build_anomaly_description(original_row)

                                    # Convert row to dictionary, applying .item() when needed
                                    feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()

                                    # Format full anomaly details for display or database
                                    anomaly_details = "\n".join([
                                        f"{k}: {v}" for k, v in feature_values.items()
                                    ])

                                    # Save local explanation as LIME bar chart
                                    lime_path = [save_lime_bar_local(exp, scenario_uuid, image_counter)]

                                    logger.info("[HANDLE PACKET] Anomaly details: %s", anomaly_details)

                                    # Save the anomaly metrics with LIME explanations
                                    save_anomaly_metrics(
                                        model_name=model_instance.__class__.__name__,
                                        feature_name=feature_name,
                                        feature_values=clean_for_json(feature_values),
                                        anomalies=anomaly_description,
                                        execution=execution,
                                        production=True,
                                        anomaly_details=json.dumps(data, indent=2),
                                        global_shap_images=[],
                                        local_shap_images=[],
                                        global_lime_images=[],
                                        local_lime_images=lime_path
                                    )

                                    # Increase index for next anomaly
                                    image_counter += 1

                                else:
                                    logger.warning(f"[HANDLE PACKET ]Explainability kind not supported yet: {kind}")

        except Exception as e:
            logger.error(f"[HANDLE PACKET] Error processing line: {line.strip()} - {e}")
            continue