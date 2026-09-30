# Evals — HDT6 (CC3116) · Parachute S.A.

Evalúa la arquitectura **centralizada** de HDT5 (manager + `consultar_faq` + `calendarizar_cita`)
con [promptfoo](https://www.promptfoo.dev/docs/getting-started/).

## Setup (una vez)

Desde la **raíz del repo**, instala primero las dependencias de Python:

```bash
pip install -r requirements.txt
cp .env.example .env                      # poner GROQ_API_KEY (sirve también como key del grader)
```

Luego instala Promptfoo desde el directorio que contiene `package.json`:

```bash
cd evals
npm ci
```

En PowerShell con una política de ejecución restrictiva, usa `npm.cmd` y
`npx.cmd` en lugar de `npm` y `npx`.

Requiere Node 20+ y que `python` esté en el PATH (o `PROMPTFOO_PYTHON=ruta/al/python`).
No necesitan Docker: los evals usan `FAQ_BACKEND=file` y clima **simulado**.

## Correr

Desde `evals/`:

```bash
npm run eval                              # todo + reporte HTML/JSON, sin caché
npm run eval:latency                      # solo los tres casos de latencia
npm run check                             # valida YAML, rutas y esquema sin llamar a Groq
npm run test:helpers                      # prueba fechas y asserts custom sin llamar a Groq
npx promptfoo eval -c promptfooconfig.yaml --filter-pattern "FAQ"  # solo FAQs
npm run view                              # UI local con resultados
```

La opción `--no-cache` es obligatoria al medir latencia; una respuesta tomada
de la caché no representa el tiempo real del agente.

## Estructura y dueños

| Archivo | Qué es | Dueño |
|---|---|---|
| `provider.py` | Ejecuta el agente y expone tool calls + contexto | P1 |
| `promptfooconfig.yaml` | Config, grader, concurrencia | P1 |
| `tests/latency.yaml` | Evals de latencia | P1 |
| `tests/faq.yaml` | Evals de FAQs | P2 |
| `tests/scheduling.yaml` | Evals de agendado de citas | P3 |
| `assertions/tool_calls.py` | Assert de *tool execution* (`check_tools`) | P1 crea, P3/P2 extienden |

## Cómo escribir un test

```yaml
- description: "FAQ · límite de peso"
  vars:
    mensaje: "¿Cuál es el límite de peso?"      # acepta [HOY], [HOY+5], [HOY-1] -> fecha ISO
    weather: seguro                             # seguro | marginal | no_seguro | real
  assert:
    - type: factuality                          # LLM compara con la referencia
      value: "El límite de peso máximo es de 100 kg."
    - type: icontains                           # determinístico
      value: "100 kg"
    - type: regex
      value: '\+?502\s?2300-0000'
    - type: latency
      threshold: 15000
    - type: python                              # tool execution
      value: file://assertions/tool_calls.py:check_tools
      config:
        manager_called: [consultar_faq]
        called: [faq_tool]
        not_called: [weather_tool]
```

Claves de `check_tools`: `manager_called`, `called`, `not_called`, `weather_date_offset`,
`weather_verdict`, `weather_valido`.

## Cosas a tener en cuenta

- **El clima está simulado** (`weather:` en vars) para que los resultados no dependan de Open-Meteo
  ni del día en que se corra. Usen `weather: real` solo para una prueba de integración.
- **Corpus:** los evals de FAQs usan `FAQs_Parachute_SA_Guatemala_2026.txt` (hechos reales). El corpus de
  120 FAQs de la base vectorial tiene respuestas genéricas sin datos concretos, así que no sirve para `factuality`.
- Con `FAQ_BACKEND=file`, `faq_tool` devuelve el documento completo (no hay *retrieval*), por lo que
  métricas como `context-recall` no aportan; si las usan, justifíquenlo en el reporte.
- Groq tiene rate limit: no suban `maxConcurrency`. Si el grader falla, cambien el modelo en `promptfooconfig.yaml`.
- Cada corrida cuesta llamadas reales a Groq (manager + worker + grader). Usen `--filter-pattern` mientras desarrollan.
- Tras la primera corrida real, **calibren los umbrales de latencia** en `tests/latency.yaml`.

## Entrega

Link al repo + `evals/reporte/reporte.html` (o `.json`) generado con `npm run eval`.
