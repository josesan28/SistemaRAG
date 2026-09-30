# HT5 — Orquestación (CC3116)

Continuación de la HDT4: al agente de FAQs de Parachute S.A. se le agrega la
capacidad de calendarizar citas de salto revisando el clima con Open-Meteo,
implementada en 3 arquitecturas de orquestación multiagente con el
**OpenAI Agents SDK**.

## Instalación

Desde la raíz del repositorio, usando el mismo archivo `.env` de la HDT4:

```bash
pip install -r requirements.txt
```

No se necesita ninguna API key nueva: Open-Meteo es gratuita y no requiere
autenticación. Se sigue usando `GROQ_API_KEY` (ya definido en el `.env` de
la HDT4) — el Agents SDK está configurado en `hdt5/shared/model_config.py`
para hablar con el endpoint compatible de Groq en vez del de OpenAI.

## Fuente de FAQs

Las tres arquitecturas usan el mismo `faq_tool`. La variable `FAQ_BACKEND`
permite escoger la implementación sin cambiar código:

- `file` (predeterminada): carga
  `FAQs_Parachute_SA_Guatemala_2026.txt` y no requiere PostgreSQL.
- `database`: reutiliza la búsqueda vectorial de HDT4 con PostgreSQL,
  pgvector y el modelo de embeddings.

En el archivo `.env`:

```dotenv
FAQ_BACKEND=file
```

Para usar la base de datos, cambia el valor a `database`, levanta el
contenedor y carga previamente `Corpus_FAQs_Parachute_SA_2026.txt` siguiendo
las instrucciones del [README principal](../README.md).


## Estructura

```
hdt5/
├── shared/                  # Capa común — NO duplicar esta lógica en ninguna arquitectura
│   ├── model_config.py      # Configura el Agents SDK para usar Groq
│   ├── faq_tool.py          # faq_tool(query): consulta la base compartida de FAQs
│   ├── weather_tool.py      # weather_tool(fecha): Open-Meteo + criterios de seguridad
│   └── agents_factory.py    # build_faq_agent() y build_weather_agent(): los 2 workers reutilizables
├── centralizada/main.py     # 1 manager, workers llamados con Agent.as_tool()     [Persona 1 — LISTO]
├── descentralizada/main.py  # Agentes independientes con handoffs                [Persona 2 — LISTO]
└── jerarquica/main.py       # Manager principal + sub-managers por dominio         [Persona 3 — LISTO]
```

## Entregables

- [Programa centralizado](centralizada/main.py) y [diagrama](centralizada/DIAGRAMA.md).
- [Programa descentralizado](descentralizada/main.py) y
  [diagrama](descentralizada/DIAGRAMA.md).
- [Programa jerárquico](jerarquica/main.py) y [diagrama](jerarquica/DIAGRAMA.md).
- [PDF con las respuestas](Hoja_de_Trabajo_5_Orquestacion-1.pdf).
- [Fuente editable de las respuestas](PREGUNTAS.md).


Cada `main.py` se ejecuta con, por ejemplo:

```bash
python -m hdt5.centralizada.main
python -m hdt5.descentralizada.main
python -m hdt5.jerarquica.main
```

La interfaz compartida que deben consumir las tres arquitecturas es:

```python
from hdt5.shared import faq_tool, weather_tool
```

Para comprobar la capa compartida sin consumir las APIs de Groq u Open-Meteo:

```bash
python -m unittest discover -s hdt5/tests -v
```

## Por qué está separado así

Si Parachute S.A. pide un requerimiento nuevo (ya avisaron que van a
seguir), el flujo es: agregar la tool en `shared/`, exponerla como un nuevo
worker en `agents_factory.py`, y solo cablear ese worker en los 3
`main.py`. La lógica de negocio (criterios de clima, búsqueda de FAQ) vive
en un solo lugar — nunca se toca dentro de `centralizada/`,
`descentralizada/` o `jerarquica/`.