"""Provider de promptfoo para el agente de Parachute S.A. (arquitectura CENTRALIZADA).

Qué hace:
  1. Construye el manager de `hdt5/centralizada/main.py` y lo ejecuta con el mensaje.
  2. Devuelve la respuesta final como `output`.
  3. Expone en `metadata` lo que necesitan los asserts:
       - manager_tool_calls: tools que llamó el manager (consultar_faq / calendarizar_cita)
       - inner_tool_calls:   tools reales de los workers (faq_tool / weather_tool), con
                             argumentos y resultado. El Agents SDK no las muestra en el
                             resultado del manager, así que se registran con un wrapper.
       - retrieved_context:  texto que devolvió faq_tool (para métricas de RAG)

Vars de cada test que entiende este provider:
  - mensaje: lo que escribe el usuario. Acepta [HOY], [HOY+5], [HOY-2] -> fecha ISO real.
             También acepta [HOY+5:DMY] -> fecha real en formato DD/MM/AAAA.
  - weather: seguro | marginal | no_seguro | real   (default: seguro)
             Simula Open-Meteo para que el eval sea determinístico. "real" llama a la API.

IMPORTANTE: patcheamos funciones de módulo, así que promptfoo debe correr con
maxConcurrency: 1 (ya está configurado en promptfooconfig.yaml).
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
# El corpus con hechos reales (100 kg, +502 2300-0000, etc.) es el archivo de HDT5.
os.environ.setdefault("FAQ_BACKEND", "file")

WEATHER_SCENARIOS = {
    "seguro": dict(wind_gust_10m=15.0, temperature_2m=26.0, precipitation=0.0,
                   cloud_cover=10.0, wind_speed_10m=10.0),
    "marginal": dict(wind_gust_10m=30.0, temperature_2m=25.0, precipitation=0.0,
                     cloud_cover=40.0, wind_speed_10m=24.0),
    "no_seguro": dict(wind_gust_10m=45.0, temperature_2m=22.0, precipitation=5.0,
                      cloud_cover=90.0, wind_speed_10m=35.0),
}
VALID_WEATHER_SCENARIOS = {*WEATHER_SCENARIOS, "real"}


def _expand_dates(texto: str) -> str:
    def repl(m: re.Match) -> str:
        delta = int(m.group(1) or 0)
        fecha = date.today() + timedelta(days=delta)
        return fecha.strftime("%d/%m/%Y") if m.group(2) == "DMY" else fecha.isoformat()

    return re.sub(r"\[HOY([+-]\d+)?(?::(DMY))?\]", repl, texto)


def _recorder(nombre: str, real, bucket: list):
    def wrapper(*args, **kwargs):
        resultado = real(*args, **kwargs)
        entrada = args[0] if args else next(iter(kwargs.values()), None)
        bucket.append({"tool": nombre, "input": entrada, "result": resultado})
        return resultado

    return wrapper


def call_api(prompt: str, options: dict, context: dict) -> dict:
    from agents import Runner

    from hdt5.centralizada.main import build_manager
    from hdt5.shared.model_config import get_model

    # OJO: `from hdt5.shared import faq_tool` devuelve la FUNCIÓN (hdt5/shared/__init__.py
    # sobrescribe el nombre del submódulo), por eso se importan los módulos así:
    faq_mod = importlib.import_module("hdt5.shared.faq_tool")
    weather_mod = importlib.import_module("hdt5.shared.weather_tool")

    variables = (context or {}).get("vars", {})
    scenario = variables.get("weather", "seguro")
    if scenario not in VALID_WEATHER_SCENARIOS:
        opciones = ", ".join(sorted(VALID_WEATHER_SCENARIOS))
        return {
            "error": (
                f"Escenario weather desconocido: {scenario!r}. "
                f"Usa uno de: {opciones}."
            )
        }
    mensaje = _expand_dates(prompt)

    inner: list[dict] = []
    patches = [
        patch.object(faq_mod, "_faq_tool_impl",
                     _recorder("faq_tool", faq_mod._faq_tool_impl, inner)),
        patch.object(weather_mod, "_weather_tool_impl",
                     _recorder("weather_tool", weather_mod._weather_tool_impl, inner)),
    ]
    if scenario in WEATHER_SCENARIOS:
        datos = WEATHER_SCENARIOS[scenario]
        patches.append(patch.object(weather_mod, "_fetch_open_meteo",
                                    lambda _fecha, _d=datos: dict(_d)))

    try:
        for p in patches:
            p.start()
        manager = build_manager(get_model())
        resultado = Runner.run_sync(manager, mensaje)
    except Exception as error:  # noqa: BLE001
        return {"error": f"{type(error).__name__}: {error}"}
    finally:
        for p in patches:
            p.stop()

    manager_calls = []
    for item in resultado.new_items:
        if getattr(item, "type", "") == "tool_call_item":
            raw = item.raw_item
            manager_calls.append({
                "tool": getattr(raw, "name", None),
                "arguments": getattr(raw, "arguments", None),
            })

    contexto = [
        str(c["result"].get("resultados", ""))
        for c in inner if c["tool"] == "faq_tool" and isinstance(c["result"], dict)
    ]

    return {
        "output": str(resultado.final_output),
        "metadata": {
            "mensaje_enviado": mensaje,
            "manager_tool_calls": manager_calls,
            "inner_tool_calls": inner,
            "retrieved_context": contexto,
        },
    }
