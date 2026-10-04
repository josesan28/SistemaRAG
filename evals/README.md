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

La versión fijada de Promptfoo requiere Node 22.22+ y que `python` esté en el PATH
(o `PROMPTFOO_PYTHON=ruta/al/python`). Si instalaron las dependencias en un
entorno virtual, apunten a ese intérprete, por ejemplo
`PROMPTFOO_PYTHON=../.venv/bin/python npm run eval`
(en Windows: `$env:PROMPTFOO_PYTHON="..\.venv\Scripts\python.exe"`).

Los scripts `eval` y `eval:latency` cargan `../.env` con `--env-file`: el grader
de `factuality` corre en Node y, sin ese flag, no encuentra `GROQ_API_KEY`
(error "API key is not set"). Si corren `npx promptfoo eval` a mano, agreguen
`--env-file ../.env`.
No necesitan Docker: los evals usan `FAQ_BACKEND=file` y clima **simulado**.

## Correr

Desde `evals/`:

```bash
npm run eval                              # todo + reporte HTML/JSON, sin caché
npm run eval:latency                      # solo los tres casos de latencia
npm run check                             # valida YAML, rutas y esquema sin llamar a Groq
npm run test:helpers                      # prueba fechas y asserts custom sin llamar a Groq
npx promptfoo eval -c promptfooconfig.yaml --env-file ../.env --filter-pattern "FAQ"  # solo FAQs
npm run view                              # UI local con resultados
```

La opción `--no-cache` es obligatoria al medir latencia; una respuesta tomada
de la caché no representa el tiempo real del agente.

## Estructura

| Archivo | Propósito |
|---|---|
| `provider.py` | Ejecuta el agente y expone las llamadas a herramientas y el contexto. |
| `promptfooconfig.yaml` | Define la configuración, el grader y la concurrencia. |
| `tests/latency.yaml` | Evalúa la latencia de los flujos principales. |
| `tests/faq.yaml` | Evalúa las respuestas a preguntas frecuentes. |
| `tests/scheduling.yaml` | Evalúa el flujo de agendado de citas. |
| `assertions/tool_calls.py` | Verifica la ejecución y los argumentos de las herramientas. |

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

Claves de `check_tools`: `manager_called`, `called`, `not_called`, `call_counts`,
`weather_date_offset`, `weather_next_weekday`, `weather_verdict` y `weather_valido`.

Los mensajes aceptan marcadores de fecha relativos para mantener los casos vigentes:
`[HOY]`, `[HOY+5]`, `[HOY-1]` y `[HOY+5:DMY]`. El sufijo `:DMY` genera
`DD/MM/AAAA`; sin sufijo se usa `AAAA-MM-DD`.

## Cosas a tener en cuenta

- **El clima está simulado** (`weather:` en vars) para que los resultados no dependan de Open-Meteo
  ni del día en que se corra. Usen `weather: real` solo para una prueba de integración.
- **Corpus:** los evals de FAQs usan `FAQs_Parachute_SA_Guatemala_2026.txt` (hechos reales). El corpus de
  120 FAQs de la base vectorial tiene respuestas genéricas sin datos concretos, así que no sirve para `factuality`.
- Con `FAQ_BACKEND=file`, `faq_tool` devuelve el documento completo. Esto mantiene
  los evals reproducibles y evita depender de PostgreSQL durante la evaluación.
- Groq tiene rate limit: no suban `maxConcurrency`. Si el grader falla, cambien el modelo en `promptfooconfig.yaml`.
- Cada corrida cuesta llamadas reales a Groq (manager + worker + grader). Usen `--filter-pattern` mientras desarrollan.
- Los umbrales de latencia en `tests/latency.yaml` ya están calibrados con la primera corrida real.

## Entrega

Link al repo + `evals/reporte/reporte.html` (o `.json`) generado con `npm run eval`.
