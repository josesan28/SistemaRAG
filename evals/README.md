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
`PROMPTFOO_PYTHON="$(realpath -s ../.venv/bin/python)" npm run eval`
(en Windows: `$env:PROMPTFOO_PYTHON="..\.venv\Scripts\python.exe"`).
Usen `realpath -s`: sin `-s` se sigue el enlace simbólico hasta el Python del
sistema y falla con `No module named 'dotenv'`. Una ruta relativa también
funciona, pero muestra avisos `RuntimeWarning: Unexpected value in sys.prefix`.

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
- **Cuota diaria de Groq:** el plan gratuito permite 200 000 tokens por día (TPD) con
  `openai/gpt-oss-20b`, en una ventana móvil de 24 h. Una corrida completa consume
  aproximadamente 70 000-80 000 tokens, así que caben unas dos corridas al día.
  Si se agota, `provider.py` marca el error como cuota (`rateLimitKind: quota`) y cada
  caso falla al instante con el mensaje de Groq, en lugar de reintentar ~4 min por caso.
  Cuando se libere la cuota, repitan solo los casos con error:
  `npx promptfoo eval -c promptfooconfig.yaml --env-file ../.env --no-cache --retry-errors`.
- Una corrida completa con cuota disponible tarda ~8 min (casos en serie, `delay: 3000`).
- **Fechas y `weather_tool`:** si la solicitud trae una fecha concreta (`AAAA-MM-DD` o
  `DD/MM/AAAA`) que existe en el calendario, el agente de citas está obligado a llamar
  `weather_tool` (`tool_choice="required"`), incluso si la fecha ya pasó o está fuera de la
  ventana de 16 días: la tool es la que valida. Sin fecha o con una fecha imposible
  (31/02) el modelo decide y pide aclaración.
- Los asserts de texto con espacios usan regex con `\s`: el modelo a veces escribe
  espacios Unicode (U+202F) que `icontains` no reconoce.
- Los umbrales de latencia en `tests/latency.yaml` ya están calibrados con la primera corrida real.

## Entrega

Link al repo + `evals/reporte/reporte.html` (o `.json`) generado con `npm run eval`.
