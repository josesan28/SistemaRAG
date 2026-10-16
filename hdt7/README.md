# Hoja de Trabajo 7 — MCP y A2A

Esta entrega reutiliza el sistema multiagente centralizado de Parachute S.A.
La integración se divide en tres capas independientes:

1. un servidor MCP único para las herramientas de FAQ y clima;
2. un servidor A2A que publica el sistema multiagente como un agente;
3. una terminal que actúa exclusivamente como cliente A2A.

## Parte implementada por Persona 1

Instale las dependencias y arranque el servidor MCP desde la raíz:

```bash
pip install -r requirements.txt
python -m hdt7.mcp_server
```

El endpoint por defecto es `http://127.0.0.1:8000/mcp`. Cada ejecución de
`faq_tool` o `weather_tool` produce logs `tool.start`, `tool.end` o
`tool.error`, que deben mostrarse en el video final.

El módulo `hdt7.multi_agent` contiene el contrato para la Persona 2:

```python
from hdt7.multi_agent import build_manager, create_mcp_client, run_multi_agent
from hdt5.shared.model_config import get_model

async with create_mcp_client() as mcp_server:
    manager = build_manager(get_model(), mcp_server)
    answer, history = await run_multi_agent(manager, "¿Cuál es el peso máximo?")
```

El servidor MCP debe estar ejecutándose antes de abrir ese contexto.

## Variables

| Variable | Valor predeterminado | Uso |
| --- | --- | --- |
| `MCP_HOST` | `127.0.0.1` | Interfaz donde escucha el servidor MCP. |
| `MCP_PORT` | `8000` | Puerto del servidor MCP. |
| `MCP_PATH` | `/mcp` | Ruta Streamable HTTP. |
| `MCP_SERVER_URL` | `http://127.0.0.1:8000/mcp` | URL usada por el MAS. |
| `LOG_LEVEL` | `INFO` | Nivel de logs del servidor. |

Consulte [`evals/REPARTO.md`](../evals/REPARTO.md) para las responsabilidades y
contratos de integración de las tres personas.

