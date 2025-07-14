import json
import pandas as pd
import numpy as np
import time
from collections import defaultdict
import logging
from .views import ip_to_int, int_to_ip, save_anomaly_metrics, get_next_anomaly_index, find_explainer_class, save_shap_bar_local, save_lime_bar_local, PROTOCOL_MAP, PROTOCOL_REVERSE_MAP, thread_controls

logger = logging.getLogger('backend')

import matplotlib.pyplot as plt

import os

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import matplotlib.font_manager as fm

import os

import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import matplotlib.font_manager as fm
import os
import textwrap

def handle_packet_prediction(proc, pipelines, anomaly_detector, design, config, execution, uuid, scenario):
    image_counter = get_next_anomaly_index(anomaly_detector)
    elements_map = {e["id"]: e for e in design["elements"]}
    connections = design["connections"]

    while thread_controls.get(uuid, True):
        line = proc.stdout.readline()
        if not line:
            continue
        try:
            pkt = json.loads(line.strip())
            if "layers" not in pkt:
                continue
            layers = pkt.get("layers", {})
            logger.info("Nueva paquete:")
            logger.info(layers)
            frame = layers.get("frame", {})
            frame_time = frame.get("frame_frame_time_epoch")
            length = int(frame.get("frame_frame_len", 0))
            time_ = float(pd.to_datetime(frame_time).timestamp())

            src = dst = proto = ttl = None
            ip_layer = layers.get("ip", {})
            ipv6_layer = layers.get("ipv6", {})

            if ipv6_layer:
                proto = ipv6_layer.get("ipv6_ipv6_nxt")
                src = ipv6_layer.get("ipv6_ipv6_src")
                dst = ipv6_layer.get("ipv6_ipv6_dst")
                ttl = ipv6_layer.get("ipv6_ipv6_hlim")
            elif ip_layer:
                proto = ip_layer.get("ip_ip_proto")
                src = ip_layer.get("ip_ip_src")
                dst = ip_layer.get("ip_ip_dst")
                ttl = ip_layer.get("ip_ip_ttl")

            proto_name = PROTOCOL_MAP.get(str(proto), str(proto)) if proto else "UNKNOWN"
            tcp_layer = layers.get("tcp", {})
            udp_layer = layers.get("udp", {})
            src_port = tcp_layer.get("tcp_tcp_srcport") or udp_layer.get("udp_udp_srcport") or -1
            dst_port = tcp_layer.get("tcp_tcp_dstport") or udp_layer.get("udp_udp_dstport") or -1

            try:
                src_port = int(src_port)
            except:
                src_port = -1
            try:
                dst_port = int(dst_port)
            except:
                dst_port = -1

            row = {
                'time': time_,
                'length': length,
                'src': src,
                'dst': dst,
                'src_port': src_port,
                'dst_port': dst_port,
                'protocol': proto_name,
                'ttl': int(ttl) if ttl else None
            }
            df = pd.DataFrame([row])

            if df.empty:
                continue

            for element_id, model_instance, steps, X_train in pipelines:
                            df_proc = df.copy()
                            
                            for step_type, transformer in steps:
                                if step_type in ["StandardScaler", "MinMaxScaler", "Normalizer", "KNNImputer", "PCA"]:
                                    expected_cols = transformer.feature_names_in_
                                    logger.info(f"[INFO] Columnas esperadas por el transformador {step_type}: {expected_cols}")
                                    
                                    df_proc_transformable = df_proc.reindex(columns=expected_cols, fill_value=0)

                                    df_proc_transformed = transformer.transform(df_proc_transformable)

                                    df_proc_transformed = pd.DataFrame(df_proc_transformed, columns=expected_cols, index=df_proc.index)

                                    df_proc[expected_cols] = df_proc_transformed

                                elif step_type == "OneHotEncoding":
                                    df_proc = pd.get_dummies(df_proc)

                            for ip_col in ['src', 'dst']:
                                if ip_col in df_proc.columns:
                                    df_proc[ip_col] = df_proc[ip_col].apply(ip_to_int)

                            if 'protocol' in df_proc.columns:
                                def protocol_to_code(p):
                                    if isinstance(p, str):
                                        p_clean = p.strip().upper()
                                        code = PROTOCOL_REVERSE_MAP.get(p_clean, -1)
                                        if code == -1:
                                            logger.warning(f"[WARN] Protocolo desconocido: {p}")
                                        return code
                                    return p

                                df_proc['protocol'] = df_proc['protocol'].apply(protocol_to_code)

                            logger.info(f"[INFO] DataFrame antes del predict: {df_proc}")
                            logger.info("Columnas al hacer predict: %s", df_proc.columns.tolist())

                            preds = model_instance.predict(df_proc)
                            preds = [1 if x == -1 else 0 for x in preds]

                            df_proc["anomaly"] = preds
                            df["anomaly"] = preds

                            logger.info(f"[MODEL] {model_instance.__class__.__name__} → Anomalías: {sum(preds)}")

                            df_anomalous = df_proc[df_proc["anomaly"] == 1]
                            if not df_anomalous.empty:
                                logger.info("[SHAP] Explicando anomalías con nodo de explicabilidad dinámico...")

                                try:
                                    elements_map = {e["id"]: e for e in design["elements"]}
                                    connections = design["connections"]

                                    explainer_id = next((conn["endId"] for conn in connections if conn["startId"] == element_id and elements_map[conn["endId"]]["type"] in ["SHAP", "LIME"]), None)

                                    if not explainer_id:
                                        logger.info("No se encontró nodo de explicabilidad conectado.")
                                        anomalous_data = df_anomalous.drop(columns=["anomaly"])
                                        for i, row in anomalous_data.iterrows():
                                            anomaly_description = (
                                                f"src: {df.loc[i, 'src']}, "
                                                f"dst: {df.loc[i, 'dst']}, "
                                                f"ports: {df.loc[i, 'src_port']}->{df.loc[i, 'dst_port']} "
                                            )
                                        logger.info(anomaly_description)
                                        save_anomaly_metrics(
                                            detector=anomaly_detector,
                                            model_name=model_instance.__class__.__name__,
                                            feature_name="",
                                            feature_values="",
                                            anomalies=anomaly_description,
                                            execution=execution,
                                            production=True,
                                            anomaly_details=None,
                                            global_shap_images=[],
                                            local_shap_images=[],
                                            global_lime_images=[],
                                            local_lime_images=[] 
                                        )
                                    else:
                                        logger.info(f"Encontrado nodo de explicabilidad: {explainer_id}")
                                        explainer_element = elements_map[explainer_id]
                                        el_type = explainer_element["type"]
                                        params = explainer_element.get("parameters", {})
                                        explainer_type = params.get("explainer_type", "").strip()
                                        explainer_module_path = config["sections"]["dataModel"]["explainability"][0]["class"] if el_type == "SHAP" else "lime"

                                        if not explainer_module_path or not explainer_type:
                                            logger.warning(f"Faltan datos de configuración en el nodo de explicabilidad {el_type}")
                                        else:
                                            explainer_class = find_explainer_class(explainer_module_path, explainer_type)

                                            input_data = df_proc.drop(columns=["anomaly"])
                                            anomalous_data = df_anomalous.drop(columns=["anomaly"])

                                            def clean_for_json(obj):
                                                if isinstance(obj, dict):
                                                    return {k: clean_for_json(v) for k, v in obj.items()}
                                                elif isinstance(obj, float):
                                                    if np.isnan(obj) or np.isinf(obj):
                                                        return 0.0
                                                elif obj is None:
                                                    return 0.0 
                                                return obj

                                            for i, row in anomalous_data.iterrows():
                                                row_df = row.to_frame().T 

                                                if el_type == "SHAP":
                                                    if explainer_type == "KernelExplainer":
                                                        def anomaly_score(X):
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

                                                    logger.info(f"[DEBUG] row_df.columns: {row_df.columns}")
                                                    logger.info(f"[DEBUG] input_data.columns: {X_train.columns}")

                                                    contribs = shap_values[0].values 
                                                    shap_contribs = sorted(
                                                        zip(contribs, row.values, row.index),
                                                        key=lambda x: abs(x[0]),
                                                        reverse=True
                                                    )
                                                    top_feature = shap_contribs[0]
                                                    feature_name = top_feature[2]

                                                    src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                                    dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                                    anomaly_description = (
                                                        f"src: {df.loc[i, 'src']}, "
                                                        f"dst: {df.loc[i, 'dst']}, "
                                                        f"ports: {src_port_str}->{dst_port_str}, "
                                                        f"protocol: {df.loc[i, 'protocol']}"
                                                    )

                                                    for col in ['src_port', 'dst_port']:
                                                        if col in row and not pd.isnull(row[col]):
                                                            try:
                                                                row[col] = int(row[col])
                                                            except:
                                                                row[col] = -1

                                                    feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()

                                                    for ip_key in ['src', 'dst']:
                                                        val = df.loc[i, ip_key]
                                                        feature_values[ip_key] = val if isinstance(val, str) else "UNDEFINED"

                                                    for port_key in ['src_port', 'dst_port']:
                                                        if port_key in feature_values:
                                                            try:
                                                                feature_values[port_key] = int(float(feature_values[port_key]))
                                                            except:
                                                                feature_values[port_key] = "N/A"

                                                    proto_code = df.loc[i, 'protocol']
                                                    feature_values['protocol'] = PROTOCOL_MAP.get(str(proto_code), proto_code)

                                                    '''
                                                    safe_payload = {
                                                        "values": clean_for_json(feature_values),
                                                        "anomaly_indices": anomaly_description
                                                    }
                                                    '''
                                                    safe_payload = {
                                                        "anomaly_indices": anomaly_description
                                                    }

                                                    logger.info(f"[EXPLANATION] Flujo anómalo #{i}, feature destacada: {feature_name}")

                                                    logger.info(f"[EXPLANATION] Generando anomalía con índice: {image_counter}")

                                                    anomaly_details = "\n".join([
                                                        f"{k}: {v}" for k, v in feature_values.items()
                                                    ])

                                                    logger.info(repr(anomaly_details))

                                                    logger.info("Anomaly details: %s", anomaly_details)

                                                    shap_paths = [save_shap_bar_local(shap_values[0], scenario.uuid, image_counter)]

                                                    logger.info(f"[EXPLANATION] Generada anomalía con índice: {image_counter}")

                                                    save_anomaly_metrics(
                                                        detector=anomaly_detector,
                                                        model_name=model_instance.__class__.__name__,
                                                        feature_name=feature_name,
                                                        feature_values=clean_for_json(feature_values),
                                                        anomalies=anomaly_description,
                                                        execution=execution,
                                                        production=True,
                                                        anomaly_details=json.dumps(pkt, indent=2),
                                                        global_shap_images=[],
                                                        local_shap_images=shap_paths,
                                                        global_lime_images=[],
                                                        local_lime_images=[]
                                                    )

                                                    image_counter += 1

                                                elif el_type == "LIME":
                                                    logger.info(f"[LIME] Explicando fila {i} con LIME...")
                                                    explainer = explainer_class(
                                                        training_data=X_train.values,
                                                        feature_names=X_train.columns.tolist(),
                                                        mode="regression"
                                                    )

                                                    def anomaly_score(X):
                                                        if isinstance(X, np.ndarray):
                                                            X = pd.DataFrame(X, columns=X_train.columns)
                                                        return model_instance.decision_function(X).reshape(-1, 1)

                                                    exp = explainer.explain_instance(
                                                        row.values,
                                                        anomaly_score,
                                                        num_features=10
                                                    )

                                                    sorted_contribs = sorted(exp.as_list(), key=lambda x: abs(x[1]), reverse=True)
                                                    feature_name = sorted_contribs[0][0] 

                                                    for col in ['src_port', 'dst_port']:
                                                        if col in row and not pd.isnull(row[col]):
                                                            try:
                                                                row[col] = int(row[col])
                                                            except:
                                                                row[col] = -1

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

                                                    feature_values['protocol'] = PROTOCOL_MAP.get(str(feature_values.get('protocol', '')), feature_values.get('protocol', 'UNKNOWN'))

                                                    src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                                    dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                                    anomaly_description = (
                                                        f"src: {df.loc[i, 'src']}, "
                                                        f"dst: {df.loc[i, 'dst']}, "
                                                        f"ports: {src_port_str}->{dst_port_str}, "
                                                        f"protocol: {df.loc[i, 'protocol']}"
                                                    )

                                                    anomaly_details = "\n".join([
                                                        f"{k}: {v}" for k, v in feature_values.items()
                                                    ])

                                                    lime_path = [save_lime_bar_local(exp, scenario.uuid, image_counter)]

                                                    logger.info(anomaly_details)

                                                    save_anomaly_metrics(
                                                        detector=anomaly_detector,
                                                        model_name=model_instance.__class__.__name__,
                                                        feature_name=feature_name,
                                                        feature_values=clean_for_json(feature_values),
                                                        anomalies=anomaly_description,
                                                        execution=execution,
                                                        production=True,
                                                        anomaly_details=json.dumps(pkt, indent=2),
                                                        global_shap_images=[],
                                                        local_shap_images=[],
                                                        global_lime_images=[],
                                                        local_lime_images=lime_path
                                                    )

                                                    image_counter += 1

                                                else:
                                                    logger.warning(f"Nodo explainability no soportado aún: {el_type}")
                                except Exception as e:
                                    logger.warning(f"[SHAP ERROR] No se pudo interpretar con explainer dinámico: {e}")

        except Exception as e:
            logger.error(f"[ERROR] Error procesando línea: {line.strip()} - {e}")
            continue

def handle_flow_prediction(proc, pipelines, anomaly_detector, design, config, execution, uuid, scenario):
    image_counter = get_next_anomaly_index(anomaly_detector)
    elements_map = {e["id"]: e for e in design["elements"]}
    connections = design["connections"]

    flow_dict = defaultdict(list)
    last_flush = time.time()
    interval = 1

    while thread_controls.get(uuid, True):
        line = proc.stdout.readline()
        if not line:
            continue
        try:
            pkt = json.loads(line.strip())
            if "layers" not in pkt:
                continue
            layers = pkt.get("layers", {})
            frame = layers.get("frame", {})
            frame_time = frame.get("frame_frame_time_epoch")
            time_ = float(pd.to_datetime(frame_time).timestamp())
            length = int(frame.get("frame_frame_len", 0))

            src = dst = proto = ttl = None
            ip_layer = layers.get("ip", {})
            ipv6_layer = layers.get("ipv6", {})

            if ipv6_layer:
                proto = ipv6_layer.get("ipv6_ipv6_nxt")
                src = ipv6_layer.get("ipv6_ipv6_src")
                dst = ipv6_layer.get("ipv6_ipv6_dst")
                ttl = ipv6_layer.get("ipv6_ipv6_hlim")
            elif ip_layer:
                proto = ip_layer.get("ip_ip_proto")
                src = ip_layer.get("ip_ip_src")
                dst = ip_layer.get("ip_ip_dst")
                ttl = ip_layer.get("ip_ip_ttl")

            proto_name = PROTOCOL_MAP.get(str(proto), str(proto)) if proto else "UNKNOWN"
            tcp_layer = layers.get("tcp", {})
            udp_layer = layers.get("udp", {})
            src_port = tcp_layer.get("tcp_tcp_srcport") or udp_layer.get("udp_udp_srcport") or -1
            dst_port = tcp_layer.get("tcp_tcp_dstport") or udp_layer.get("udp_udp_dstport") or -1

            try:
                src_port = int(src_port)
            except:
                src_port = -1
            try:
                dst_port = int(dst_port)
            except:
                dst_port = -1

            if proto_name in ['TCP', 'UDP']:
                flow_key = tuple(sorted([(src, src_port), (dst, dst_port)])) + (proto_name,)
            else:
                flow_key = (src, dst, proto_name)

            flow_dict[flow_key].append({
                'time': time_,
                'length': length,
                'ttl': int(ttl) if ttl else None
            })

        except Exception:
            continue

        if time.time() - last_flush >= interval:
            rows = []
            for flow, packets in flow_dict.items():
                times = [p['time'] for p in packets if p['time'] is not None]
                lengths = [p['length'] for p in packets if p['length'] is not None]
                ttls = [p['ttl'] for p in packets if p['ttl'] is not None]

                try:
                    if isinstance(flow[0], tuple):
                        src, src_port = flow[0]
                        dst, dst_port = flow[1]
                        proto = flow[2]
                    else:
                        src, dst, proto = flow
                        src_port = dst_port = -1

                    rows.append({
                        'src': src,
                        'src_port': src_port,
                        'dst': dst,
                        'dst_port': dst_port,
                        'protocol': proto,
                        'packet_count': len(packets),
                        'total_bytes': sum(lengths),
                        'avg_packet_size': sum(lengths) / len(lengths) if lengths else 0,
                        'flow_duration': max(times) - min(times) if times else 0,
                        'avg_ttl': sum(ttls) / len(ttls) if ttls else None,
                    })
                except Exception:
                    continue

            flow_dict.clear()
            last_flush = time.time()
            df = pd.DataFrame(rows)

            if df.empty:
                continue

            for element_id, model_instance, steps, X_train in pipelines:
                            df_proc = df.copy()
                            
                            for step_type, transformer in steps:
                                if step_type in ["StandardScaler", "MinMaxScaler", "Normalizer", "KNNImputer", "PCA"]:
                                    expected_cols = transformer.feature_names_in_
                                    logger.info(f"[INFO] Columnas esperadas por el transformador {step_type}: {expected_cols}")
                                    
                                    df_proc_transformable = df_proc.reindex(columns=expected_cols, fill_value=0)

                                    df_proc_transformed = transformer.transform(df_proc_transformable)

                                    df_proc_transformed = pd.DataFrame(df_proc_transformed, columns=expected_cols, index=df_proc.index)

                                    df_proc[expected_cols] = df_proc_transformed

                                elif step_type == "OneHotEncoding":
                                    df_proc = pd.get_dummies(df_proc)

                            for ip_col in ['src', 'dst']:
                                if ip_col in df_proc.columns:
                                    df_proc[ip_col] = df_proc[ip_col].apply(ip_to_int)

                            if 'protocol' in df_proc.columns:
                                def protocol_to_code(p):
                                    if isinstance(p, str):
                                        p_clean = p.strip().upper()
                                        code = PROTOCOL_REVERSE_MAP.get(p_clean, -1)
                                        if code == -1:
                                            logger.warning(f"[WARN] Protocolo desconocido: {p}")
                                        return code
                                    return p

                                df_proc['protocol'] = df_proc['protocol'].apply(protocol_to_code)

                            logger.info(f"[INFO] DataFrame antes del predict: {df_proc}")
                            logger.info("Columnas al hacer predict: %s", df_proc.columns.tolist())

                            preds = model_instance.predict(df_proc)
                            preds = [1 if x == -1 else 0 for x in preds]

                            df_proc["anomaly"] = preds
                            df["anomaly"] = preds

                            logger.info(f"[MODEL] {model_instance.__class__.__name__} → Anomalías: {sum(preds)}")

                            df_anomalous = df_proc[df_proc["anomaly"] == 1]
                            if not df_anomalous.empty:
                                logger.info("[SHAP] Explicando anomalías con nodo de explicabilidad dinámico...")

                                try:
                                    elements_map = {e["id"]: e for e in design["elements"]}
                                    connections = design["connections"]

                                    explainer_id = next((conn["endId"] for conn in connections if conn["startId"] == element_id and elements_map[conn["endId"]]["type"] in ["SHAP", "LIME"]), None)

                                    if not explainer_id:
                                        logger.info("No se encontró nodo de explicabilidad conectado.")
                                        anomalous_data = df_anomalous.drop(columns=["anomaly"])
                                        for i, row in anomalous_data.iterrows():
                                            anomaly_description = (
                                                f"src: {df.loc[i, 'src']}, "
                                                f"dst: {df.loc[i, 'dst']}, "
                                                f"ports: {df.loc[i, 'src_port']}->{df.loc[i, 'dst_port']} "
                                            )
                                        logger.info(anomaly_description)
                                        save_anomaly_metrics(
                                            detector=anomaly_detector,
                                            model_name=model_instance.__class__.__name__,
                                            feature_name="",
                                            feature_values="",
                                            anomalies=anomaly_description,
                                            execution=execution,
                                            production=True,
                                            anomaly_details=None,
                                            global_shap_images=[],
                                            local_shap_images=[],
                                            global_lime_images=[],
                                            local_lime_images=[] 
                                        )
                                    else:
                                        logger.info(f"Encontrado nodo de explicabilidad: {explainer_id}")
                                        explainer_element = elements_map[explainer_id]
                                        el_type = explainer_element["type"]
                                        params = explainer_element.get("parameters", {})
                                        explainer_type = params.get("explainer_type", "").strip()
                                        explainer_module_path = config["sections"]["dataModel"]["explainability"][0]["class"] if el_type == "SHAP" else "lime"

                                        if not explainer_module_path or not explainer_type:
                                            logger.warning(f"Faltan datos de configuración en el nodo de explicabilidad {el_type}")
                                        else:
                                            explainer_class = find_explainer_class(explainer_module_path, explainer_type)

                                            input_data = df_proc.drop(columns=["anomaly"])
                                            anomalous_data = df_anomalous.drop(columns=["anomaly"])

                                            def clean_for_json(obj):
                                                if isinstance(obj, dict):
                                                    return {k: clean_for_json(v) for k, v in obj.items()}
                                                elif isinstance(obj, float):
                                                    if np.isnan(obj) or np.isinf(obj):
                                                        return 0.0
                                                elif obj is None:
                                                    return 0.0 
                                                return obj

                                            for i, row in anomalous_data.iterrows():
                                                row_df = row.to_frame().T 

                                                if el_type == "SHAP":
                                                    if explainer_type == "KernelExplainer":
                                                        def anomaly_score(X):
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

                                                    logger.info(f"[DEBUG] row_df.columns: {row_df.columns}")
                                                    logger.info(f"[DEBUG] input_data.columns: {X_train.columns}")

                                                    contribs = shap_values[0].values 
                                                    shap_contribs = sorted(
                                                        zip(contribs, row.values, row.index),
                                                        key=lambda x: abs(x[0]),
                                                        reverse=True
                                                    )
                                                    top_feature = shap_contribs[0]
                                                    feature_name = top_feature[2]

                                                    src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                                    dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                                    anomaly_description = (
                                                        f"src: {df.loc[i, 'src']}, "
                                                        f"dst: {df.loc[i, 'dst']}, "
                                                        f"ports: {src_port_str}->{dst_port_str}, "
                                                        f"protocol: {df.loc[i, 'protocol']}"
                                                    )

                                                    for col in ['src_port', 'dst_port']:
                                                        if col in row and not pd.isnull(row[col]):
                                                            try:
                                                                row[col] = int(row[col])
                                                            except:
                                                                row[col] = -1

                                                    feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()

                                                    for ip_key in ['src', 'dst']:
                                                        val = df.loc[i, ip_key]
                                                        feature_values[ip_key] = val if isinstance(val, str) else "UNDEFINED"

                                                    for port_key in ['src_port', 'dst_port']:
                                                        if port_key in feature_values:
                                                            try:
                                                                feature_values[port_key] = int(float(feature_values[port_key]))
                                                            except:
                                                                feature_values[port_key] = "N/A"

                                                    proto_code = df.loc[i, 'protocol']
                                                    feature_values['protocol'] = PROTOCOL_MAP.get(str(proto_code), proto_code)

                                                    '''
                                                    safe_payload = {
                                                        "values": clean_for_json(feature_values),
                                                        "anomaly_indices": anomaly_description
                                                    }
                                                    '''
                                                    safe_payload = {
                                                        "anomaly_indices": anomaly_description
                                                    }
                                                    anomalies_json = json.dumps(safe_payload)

                                                    logger.info(f"[EXPLANATION] Flujo anómalo #{i}, feature destacada: {feature_name}")

                                                    logger.info(f"[EXPLANATION] Generando anomalía con índice: {image_counter}")

                                                    anomaly_details = "\n".join([
                                                        f"{k}: {v}" for k, v in feature_values.items()
                                                    ])

                                                    logger.info("Anomaly details: %s", anomaly_details)

                                                    shap_paths = [save_shap_bar_local(shap_values[0], scenario.uuid, image_counter)]

                                                    logger.info(f"[EXPLANATION] Generada anomalía con índice: {image_counter}")

                                                    save_anomaly_metrics(
                                                        detector=anomaly_detector,
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

                                                    image_counter += 1

                                                elif el_type == "LIME":
                                                    logger.info(f"[LIME] Explicando fila {i} con LIME...")
                                                    explainer = explainer_class(
                                                        training_data=X_train.values,
                                                        feature_names=X_train.columns.tolist(),
                                                        mode="regression"
                                                    )

                                                    def anomaly_score(X):
                                                        if isinstance(X, np.ndarray):
                                                            X = pd.DataFrame(X, columns=X_train.columns)
                                                        return model_instance.decision_function(X).reshape(-1, 1)

                                                    exp = explainer.explain_instance(
                                                        row.values,
                                                        anomaly_score,
                                                        num_features=10
                                                    )

                                                    sorted_contribs = sorted(exp.as_list(), key=lambda x: abs(x[1]), reverse=True)
                                                    feature_name = sorted_contribs[0][0] 

                                                    for col in ['src_port', 'dst_port']:
                                                        if col in row and not pd.isnull(row[col]):
                                                            try:
                                                                row[col] = int(row[col])
                                                            except:
                                                                row[col] = -1

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

                                                    feature_values['protocol'] = PROTOCOL_MAP.get(str(feature_values.get('protocol', '')), feature_values.get('protocol', 'UNKNOWN'))

                                                    src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                                    dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                                    anomaly_description = (
                                                        f"src: {df.loc[i, 'src']}, "
                                                        f"dst: {df.loc[i, 'dst']}, "
                                                        f"ports: {src_port_str}->{dst_port_str}, "
                                                        f"protocol: {df.loc[i, 'protocol']}"
                                                    )

                                                    anomaly_details = "\n".join([
                                                        f"{k}: {v}" for k, v in feature_values.items()
                                                    ])

                                                    lime_path = [save_lime_bar_local(exp, scenario.uuid, image_counter)]

                                                    logger.info(anomaly_details)

                                                    save_anomaly_metrics(
                                                        detector=anomaly_detector,
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

                                                    image_counter += 1

                                                else:
                                                    logger.warning(f"Nodo explainability no soportado aún: {el_type}")
                                except Exception as e:
                                    logger.warning(f"[SHAP ERROR] No se pudo interpretar con explainer dinámico: {e}")

def get_next_anomaly_index(anomaly_detector):
    from .models import AnomalyMetric
    current = AnomalyMetric.objects.filter(detector=anomaly_detector, execution=anomaly_detector.execution, production=True).count()
    return current + 1


