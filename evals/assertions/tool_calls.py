"""Asserts custom (Python) para verificar TOOL EXECUTION.

Uso en un test:

    - type: python
      value: file://assertions/tool_calls.py:check_tools
      config:
        manager_called: [consultar_faq]      # el manager delegó al worker correcto
        called: [faq_tool]                   # el worker llamó su tool real
        not_called: [weather_tool]           # NO debe haberse llamado
        call_counts: {weather_tool: 1}       # cantidad exacta de ejecuciones
        weather_date_offset: 5               # la fecha enviada a weather_tool = hoy+5
        weather_next_weekday: 5              # próximo sábado (lunes=0, domingo=6)
        weather_verdict: seguro              # veredicto que devolvió la tool
        weather_valido: false                # (opcional) resultado.valido esperado

Todas las claves de config son opcionales; solo se evalúan las que pongas.
"""

from __future__ import annotations

from datetime import date, timedelta


def _meta(context: dict) -> dict:
    respuesta = context.get("providerResponse") or {}
    return respuesta.get("metadata") or context.get("metadata") or {}


def _resultado(ok: bool, motivo: str) -> dict:
    return {"pass": ok, "score": 1.0 if ok else 0.0, "reason": motivo}


def check_tools(output: str, context: dict) -> dict:
    cfg = context.get("config") or {}
    meta = _meta(context)
    if not meta:
        return _resultado(False, "El provider no devolvió metadata (revisa provider.py).")

    inner = meta.get("inner_tool_calls", [])
    manager = [c.get("tool") for c in meta.get("manager_tool_calls", [])]
    inner_names = [c["tool"] for c in inner]

    for nombre in cfg.get("manager_called", []):
        if nombre not in manager:
            return _resultado(False, f"El manager no llamó a '{nombre}'. Llamó: {manager}")
    for nombre in cfg.get("called", []):
        if nombre not in inner_names:
            return _resultado(False, f"No se ejecutó '{nombre}'. Se ejecutó: {inner_names}")
    for nombre in cfg.get("not_called", []):
        if nombre in inner_names or nombre in manager:
            return _resultado(False, f"'{nombre}' no debía llamarse. inner={inner_names} manager={manager}")
    for nombre, cantidad in cfg.get("call_counts", {}).items():
        recibida = inner_names.count(nombre)
        if recibida != cantidad:
            return _resultado(
                False,
                f"'{nombre}' se ejecutó {recibida} veces, se esperaban {cantidad}.",
            )

    weather = next((c for c in inner if c["tool"] == "weather_tool"), None)
    if "weather_date_offset" in cfg:
        esperado = (date.today() + timedelta(days=cfg["weather_date_offset"])).isoformat()
        if not weather or weather["input"] != esperado:
            recibido = weather["input"] if weather else None
            return _resultado(False, f"weather_tool recibió fecha {recibido}, esperada {esperado}")
    if "weather_next_weekday" in cfg:
        weekday = cfg["weather_next_weekday"]
        if not isinstance(weekday, int) or not 0 <= weekday <= 6:
            return _resultado(False, "weather_next_weekday debe ser un entero entre 0 y 6.")
        dias = (weekday - date.today().weekday()) % 7 or 7
        esperado = (date.today() + timedelta(days=dias)).isoformat()
        if not weather or weather["input"] != esperado:
            recibido = weather["input"] if weather else None
            return _resultado(
                False,
                f"weather_tool recibió fecha {recibido}, se esperaba el próximo "
                f"día {weekday}: {esperado}",
            )
    if "weather_verdict" in cfg:
        veredicto = ((weather or {}).get("result") or {}).get("veredicto")
        if veredicto != cfg["weather_verdict"]:
            return _resultado(False, f"Veredicto {veredicto}, esperado {cfg['weather_verdict']}")
    if "weather_valido" in cfg:
        valido = ((weather or {}).get("result") or {}).get("valido")
        if valido != cfg["weather_valido"]:
            return _resultado(False, f"valido={valido}, esperado {cfg['weather_valido']}")

    return _resultado(True, f"OK. manager={manager} inner={inner_names}")
