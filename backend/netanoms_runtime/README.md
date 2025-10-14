# netanoms-runtime

Pequeña librería en **un solo fichero** que envuelve tu `utils.py` original para poder ejecutar
la producción (tshark + detección y explicabilidad) tanto desde **Django** como desde un
**script Python normal** (en host o dentro de un contenedor Docker).

## Instalación (editable)

```bash
pip install -e .
```

## Uso en Django

En tu view `play_scenario_production_by_uuid`, cambia el target del hilo a:

```python
from netanoms_runtime.detection import run_live_production

# ...
run_live_production(
    mode=analysis_mode,                # "packet" o "flow"
    proc=proc,                         # Popen ssh+tshark -T ek
    pipelines=pipelines,
    anomaly_detector=anomaly_detector,
    design=design,
    config=config,
    execution=execution,
    uuid=str(uuid),
    scenario=scenario,
)
```

## Uso fuera de Django (host o Docker)

```bash
python examples/run_from_host.py
```

Edita el ejemplo para construir `proc` (ssh + tshark), `pipelines`, etc. Puedes pasar callbacks
(`on_anomaly`, `on_status`, `on_error`) si no tienes BD.
