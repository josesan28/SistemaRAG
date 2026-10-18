# Hoja de Trabajo 7 — MCP y A2A

Esta entrega reutiliza el sistema multiagente centralizado de Parachute S.A.
La integración se divide en tres capas independientes, cada una en su propio
proceso:

1. un servidor MCP único para las herramientas de FAQ y clima;
2. un servidor A2A que publica el sistema multiagente como un solo agente;
3. una terminal que actúa exclusivamente como cliente A2A.

```text
Terminal (cliente A2A) ──A2A / JSON-RPC──▶ Servidor A2A :9999
                                             └─ Manager ─┬─ Agente FAQ ─────┐
                                                         └─ Agente de Citas ┤
                                                                            ▼
                                             Servidor MCP :8000/mcp (Streamable HTTP)
                                               ├─ faq_tool
                                               └─ weather_tool ──▶ Open-Meteo
```

## Ejecución

Instale las dependencias una vez desde la raíz (`pip install -r requirements.txt`)
y configure `GROQ_API_KEY` en `.env`. Luego abra **tres terminales** en la raíz
del repositorio y ejecute, en este orden:

```bash
python -m hdt7.mcp_server
python -m hdt7.a2a_server
python -m hdt7.terminal_client
```

El orden importa: el servidor A2A se conecta al MCP al arrancar y la terminal
descubre el Agent Card del servidor A2A al iniciar.

### Qué debe verse en el video

| Terminal | Logs esperados |
| --- | --- |
| `hdt7.mcp_server` | `tool.start` y `tool.end` por cada ejecución de `faq_tool` o `weather_tool` (`tool.error` si falla). |
| `hdt7.a2a_server` | `server.started` al arrancar; `task.received` y `task.completed` por cada mensaje (`task.failed` si falla). |
| `hdt7.terminal_client` | El Agent Card descubierto y al menos una FAQ y una consulta climática válida. |

Ejemplos para la terminal (la fecha debe estar dentro de los próximos 16 días):

```text
¿Cuál es el límite de peso para saltar?
¿Puedo saltar el AAAA-MM-DD?
Bye
```

En el log A2A, los mensajes de una misma conversación tienen distinto
`task_id` pero el mismo `context_id`.

## Servidor MCP (Persona 1)

El endpoint por defecto es `http://127.0.0.1:8000/mcp` con transporte
Streamable HTTP. Expone `faq_tool` y `weather_tool`; cada especialista del MAS
solo ve la herramienta que le corresponde (mínimo privilegio).

El módulo `hdt7.multi_agent` es el contrato que reutiliza el servidor A2A:

```python
from hdt7.multi_agent import build_manager, create_mcp_client, run_multi_agent
from hdt5.shared.model_config import get_model

async with create_mcp_client() as mcp_server:
    manager = build_manager(get_model(), mcp_server)
    answer, history = await run_multi_agent(manager, "¿Cuál es el peso máximo?")
```

## Servidor A2A (Persona 2)

`hdt7.a2a_server` abre una sola conexión MCP durante su ciclo de vida, publica
el Agent Card en `http://127.0.0.1:9999/.well-known/agent-card.json` (A2A 1.0,
binding JSON-RPC, sin streaming) con dos skills —preguntas frecuentes y
evaluación climática— y convierte cada mensaje en una tarea A2A cuya respuesta
se entrega como artefacto de texto. Guarda el historial por `context_id`.

## Terminal cliente A2A (Persona 3)

`hdt7.terminal_client` usa exclusivamente el cliente oficial de `a2a-sdk`; no
importa ni llama a `Runner`, `build_manager()` ni `run_multi_agent()`. Para
cada sesión:

1. Descubre el Agent Card en `A2A_PUBLIC_URL` y verifica que tenga nombre y
   una interfaz JSON-RPC.
2. Crea el cliente con `ClientConfig(streaming=False)`.
3. Envía cada entrada como `SendMessageRequest`. Como `send_message()` devuelve
   elementos `StreamResponse`, toma la tarea final de `response.task` cuando
   `response.WhichOneof("payload") == "task"` y muestra el texto de sus
   artefactos.
4. Guarda el `context_id` que asigna el servidor y lo envía en los mensajes
   siguientes, para que el agente recuerde la conversación. No reenvía el
   `task_id`: cada mensaje es una tarea nueva.
5. Termina con `Bye` (sin importar mayúsculas), Ctrl-C o Ctrl-D.

Mensajes de error que muestra:

| Situación | Comportamiento |
| --- | --- |
| Servidor A2A apagado al iniciar | Indica que se ejecute `python -m hdt7.a2a_server` y sale con código 1. |
| Agent Card ausente (404), no JSON o sin interfaz JSON-RPC | Explica por qué el Agent Card no es utilizable y sale con código 1. |
| Tarea en estado `FAILED` | Muestra el motivo enviado por el servidor y permite seguir conversando. |
| Tarea completada sin artefactos de texto | Lo indica y permite seguir conversando. |
| Servidor caído o lento durante la conversación | Indica la pérdida de conexión o el timeout y permite reintentar. |

Opciones: `python -m hdt7.terminal_client --url http://host:puerto --timeout 120`.

El timeout por defecto es de 120 s porque un turno del MAS (manager,
especialista, MCP y Groq) tarda de 15 a 40 s; el de httpx por defecto (5 s)
cortaría la mayoría de las respuestas.

## Variables

| Variable | Valor predeterminado | Uso |
| --- | --- | --- |
| `MCP_HOST` | `127.0.0.1` | Interfaz donde escucha el servidor MCP. |
| `MCP_PORT` | `8000` | Puerto del servidor MCP. |
| `MCP_PATH` | `/mcp` | Ruta Streamable HTTP. |
| `MCP_SERVER_URL` | `http://127.0.0.1:8000/mcp` | URL del MCP que usa el MAS. |
| `A2A_HOST` | `127.0.0.1` | Interfaz donde escucha el servidor A2A. |
| `A2A_PORT` | `9999` | Puerto del servidor A2A. |
| `A2A_PUBLIC_URL` | `http://127.0.0.1:9999` | URL anunciada en el Agent Card y usada por la terminal. |
| `A2A_CLIENT_TIMEOUT` | `120` | Segundos que la terminal espera cada respuesta. |
| `LOG_LEVEL` | `INFO` | Nivel de logs de los servidores. |

Si el puerto 8000 ya está ocupado por otro programa, cambie `MCP_PORT` y
`MCP_SERVER_URL` en `.env` (por ejemplo, a `8001` y
`http://127.0.0.1:8001/mcp`); ambos servidores leen el mismo `.env`.

## Pruebas

No requieren servidores en ejecución ni `GROQ_API_KEY`:

```bash
python -m unittest discover -s hdt7/tests -t . -v
```

Las pruebas de la terminal levantan el servidor A2A real en memoria con el MAS
simulado y usan servidores HTTP simulados para los casos de error.

Consulte [`evals/REPARTO.md`](../evals/REPARTO.md) para las responsabilidades y
contratos de integración de las tres personas.
