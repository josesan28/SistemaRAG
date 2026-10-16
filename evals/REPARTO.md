# Hoja de Trabajo 7 — reparto entre 3 personas

## Decisiones compartidas

- Se continúa con la arquitectura **centralizada** elegida en la HDT6.
- Las únicas herramientas de negocio son `faq_tool(query)` y
  `weather_tool(fecha)`, publicadas juntas en un servidor MCP.
- El transporte MCP es **Streamable HTTP** y su endpoint predeterminado es
  `http://127.0.0.1:8000/mcp`.
- A2A publica todo el sistema multiagente como un solo agente; ni el cliente de
  terminal ni un cliente A2A conocen los workers internos.
- Los archivos de una persona no deben ser modificados por otra salvo acuerdo,
  para reducir conflictos al integrar ramas.

## Persona 1 — servidor MCP y adaptación del MAS 

Archivos propios:

- `hdt7/mcp_server.py`
- `hdt7/multi_agent.py`
- `hdt7/tests/test_persona1_mcp.py`
- dependencias y documentación base de `hdt7/`

Responsabilidades:

1. Exponer las dos implementaciones de herramientas existentes desde un único
   servidor MCP con transporte Streamable HTTP.
2. Emitir logs visibles al iniciar, terminar o fallar cada ejecución de tool.
3. Migrar los dos especialistas para consumir MCP con
   `MCPServerStreamableHttp`, limitando por nombre qué tool ve cada agente.
4. Entregar a Persona 2 el contrato `build_manager(...)`,
   `create_mcp_client(...)` y `run_multi_agent(...)`.
5. Agregar pruebas del filtro de mínimo privilegio y configuración del endpoint.

Criterio de aceptación: con el MCP activo, el MAS responde una FAQ mediante
`faq_tool` y evalúa una fecha mediante `weather_tool`; la consola del MCP deja
un log por cada llamada.

## Persona 2 — servidor A2A que envuelve el MAS

Archivos reservados sugeridos:

- `hdt7/a2a_server.py`
- `hdt7/a2a_executor.py`
- `hdt7/agent_card.py` (si el SDK elegido lo requiere)
- `hdt7/tests/test_persona2_a2a_server.py`

Responsabilidades:

1. Instalar/fijar el SDK oficial `a2a-sdk` compatible con la versión de Python.
2. Crear un `AgentCard` para “Parachute S.A.” con skills visibles de preguntas
   frecuentes y evaluación climática/calendarización.
3. Implementar el executor A2A reutilizando **sin modificar**
   `hdt7.multi_agent`: abrir un solo `create_mcp_client()` durante el ciclo de
   vida del servidor, construir el manager y llamar `run_multi_agent()`.
4. Traducir mensajes/tareas A2A a texto y publicar la respuesta final, errores
   y estados conforme al SDK.
5. Servir A2A por HTTP y emitir logs de arranque, tarea recibida, completada o
   fallida. Agregar pruebas del Agent Card y del executor con el MAS simulado.

Criterio de aceptación: un cliente A2A descubre el Agent Card y completa una
tarea; el servidor A2A muestra sus logs y la llamada llega al MCP.

## Persona 3 — cliente A2A de terminal, integración y video

Archivos reservados sugeridos:

- `hdt7/terminal_client.py`
- `hdt7/tests/test_persona3_a2a_client.py`
- actualización final de `hdt7/README.md`

Responsabilidades:

1. Reemplazar el acceso directo al `Runner` por el cliente del SDK A2A.
2. Descubrir el Agent Card del servidor, enviar mensajes y mostrar respuestas
   hasta recibir `Bye`/`Ctrl-C`; conservar `context_id` entre turnos si el SDK
   y el servidor lo soportan.
3. Manejar servidor no disponible y respuestas fallidas con mensajes claros.
4. Ejecutar la prueba integral y documentar los tres comandos de arranque.


Criterio de aceptación: la terminal solo se comunica con el servidor A2A y
permite demostrar al menos una FAQ y una consulta de clima válida.

## Orden de integración

1. Persona 1 entrega MCP y el contrato Python del MAS.
2. Persona 2 agrega la envoltura A2A sobre ese contrato.
3. Persona 3 conecta la terminal al endpoint A2A y realiza la prueba end-to-end.
