# Reparto HDT6 — Evals (3 personas)

Arquitectura evaluada: **centralizada** (la elegida en `hdt5/PREGUNTAS.md`).

## Persona 1 — Fundación, latencia e integración (lista para que P2/P3 arranquen)
- [x] `evals/` con `provider.py`, `promptfooconfig.yaml`, `assertions/tool_calls.py`, package.json, README
- [x] Plantillas `tests/faq.yaml` y `tests/scheduling.yaml` con casos de ejemplo
- [x] `tests/latency.yaml` con casos FAQ, cita y consulta mixta
- [x] Validación offline: configuración Promptfoo válida y helpers con pruebas unitarias
- [ ] Correr una vez con GROQ_API_KEY real, confirmar que el grader responde y hacer push a `main`
- [ ] Avisar a P2 y P3 (van con `git pull`)
- [ ] Calibrar los umbrales de latencia tras la primera corrida real
- [ ] Al final: correr todo, generar `evals/reporte/reporte.html`, revisar que todo pase o esté justificado, entregar

## Persona 2 — Evals de FAQs (`tests/faq.yaml`)
- [x] 12-15 casos: pesos, edad, pagos, cámara/GoPro, salud, mal clima, duración, ropa, contacto
- [x] `factuality` (con referencia del .txt) + `icontains`/`regex` para datos exactos
- [x] Tool execution: `consultar_faq` -> `faq_tool`, y `weather_tool` NO llamada
- [x] Rechazo fuera de corpus (capital de Francia, precio de otro producto, prompt injection)
- [x] Variantes con paráfrasis y typos
- [x] Opcional: `context-faithfulness` usando el .txt como `vars.context`
  (assert propio en `assertions/faq_checks.py`; la métrica nativa no parsea las
  respuestas del grader de Groq. Pruebas: `python tests/test_faq_checks.py`)

## Persona 3 — Evals de agendado (`tests/scheduling.yaml`)
- [ ] 12-15 casos: seguro, marginal, no_seguro, fecha pasada, fuera de 16 días, "el próximo sábado", formato raro
- [ ] Tool execution: fecha exacta enviada a `weather_tool` (`weather_date_offset`) y veredicto esperado
- [ ] Mensaje sin fecha -> NO llama `weather_tool` y pide la fecha
- [ ] Consulta mixta FAQ + cita -> ambas tools llamadas
- [ ] `regex`/`icontains` sobre la respuesta y `llm-rubric`/`factuality` para el veredicto explicado

## Cobertura de la rúbrica
| Requisito | FAQs | Citas |
|---|---|---|
| Factuality | P2 | P3 |
| Contains / regex | P2 | P3 |
| Latencia | P1 | P1 |
| Tool execution | P2 | P3 |

## Convención de trabajo
Rama `hdt6/evals-p1` -> PR a `main` YA (esqueleto). Luego P2 solo toca `tests/faq.yaml`
y P3 solo `tests/scheduling.yaml`, así no hay conflictos. Si necesitan un helper nuevo en
`assertions/`, un archivo nuevo por persona (`faq_checks.py`, `scheduling_checks.py`).
