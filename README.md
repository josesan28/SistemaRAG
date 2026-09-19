
# Sistema RAG de FAQs — Parachute S.A.

Agente de terminal que responde únicamente con información recuperada del
corpus oficial `Corpus_FAQs_Parachute_SA_2026.txt`. Los embeddings se almacenan
en PostgreSQL con pgvector y el modelo consulta la base mediante function
calling real con el SDK compatible con OpenAI de Groq.

## Hoja de Trabajo 5 — Orquestación multiagente

La continuación del proyecto está en [`hdt5/`](hdt5/README.md). Implementa
el agente de FAQs y calendarización con clima mediante tres arquitecturas:

- [Centralizada](hdt5/centralizada/main.py), con su
  [diagrama](hdt5/centralizada/DIAGRAMA.md).
- [Descentralizada](hdt5/descentralizada/main.py), con su
  [diagrama](hdt5/descentralizada/DIAGRAMA.md).
- [Jerárquica](hdt5/jerarquica/main.py), con su
  [diagrama](hdt5/jerarquica/DIAGRAMA.md).

El [PDF de respuestas](hdt5/Hoja_de_Trabajo_5_Orquestacion-1.pdf) también se
encuentra dentro de esa carpeta.

Los programas se ejecutan desde la raíz:

```bash
python -m hdt5.centralizada.main
python -m hdt5.descentralizada.main
python -m hdt5.jerarquica.main
```

## Infraestructura (PostgreSQL + pgvector)

### 1. Levantar el contenedor

```bash
docker compose up -d
```

(o `podman-compose up -d` si usan Podman)

Esto levanta Postgres 16 con la extensión `pgvector` ya instalada
(imagen `pgvector/pgvector:pg16`) y corre automáticamente `init.sql`
la primera vez, creando la extensión `vector` y la tabla `faqs`.

Comprueben que el servicio está saludable antes de cargar el corpus:

```bash
docker compose ps
```

> Si ya tenían un contenedor de Postgres corriendo de antes (volumen
> ya inicializado), `init.sql` no se vuelve a ejecutar solo. En ese
> caso corran a mano:
> ```bash
> docker exec -i parachute_pgvector psql -U parachute -d parachute_faqs < init.sql
> ```

### 2. Configurar variables de entorno

Copien `.env.example` a `.env` y ajusten si es necesario (los valores
por defecto ya coinciden con `docker-compose.yml`):

```bash
cp .env.example .env
```

Resumen de las variables disponibles:

| Variable | Uso |
| --- | --- |
| `GROQ_API_KEY` | Clave necesaria para autenticar las solicitudes a Groq. |
| `GROQ_MODEL` | Modelo de Groq utilizado para responder y realizar tool calling. |
| `FAQ_MAX_COSINE_DISTANCE` | Descarta vecinos poco relevantes; calibren el valor si cambia el corpus o el modelo. |
| `HF_HUB_DISABLE_PROGRESS_BARS` | Oculta las barras de progreso de Hugging Face Hub. |
| `HF_HUB_DISABLE_SYMLINKS_WARNING` | Oculta la advertencia de symlinks en Windows. |
| `HF_HUB_VERBOSITY` | Controla el nivel de mensajes emitidos por Hugging Face Hub. |
| `TRANSFORMERS_VERBOSITY` | Controla el nivel de mensajes de la librería Transformers. |
| `SHOW_TOOL_TRACE` | Con `true`, muestra en terminal los IDs de las FAQs recuperadas. |
| `POSTGRES_HOST` | Dirección del servidor de PostgreSQL. |
| `POSTGRES_PORT` | Puerto de conexión y puerto que Docker expone en la máquina. |
| `POSTGRES_DB` | Nombre de la base de datos que almacena las FAQs. |
| `POSTGRES_USER` | Usuario utilizado para conectarse a PostgreSQL. |
| `POSTGRES_PASSWORD` | Contraseña del usuario de PostgreSQL. |

Solo `GROQ_API_KEY` debe reemplazarse obligatoriamente. Los demás valores de
`.env.example` funcionan con la configuración incluida en el repositorio.

### 3. Instalar dependencias de Python

```bash
pip install -r requirements.txt
```

La primera ejecución de `sentence-transformers` puede descargar el modelo
multilingüe `paraphrase-multilingual-MiniLM-L12-v2`; por eso requiere conexión
a internet una sola vez, salvo que el modelo ya esté en caché.

### 4. Cargar los FAQs a la base de datos

```bash
python load_faqs.py Corpus_FAQs_Parachute_SA_2026.txt
```

Si ya habían cargado la base con una versión anterior del proyecto, ejecuten
este comando nuevamente: el UPSERT reemplaza los embeddings existentes por los
del modelo multilingüe y no duplica filas.

El script:
1. Parsea el corpus (120 FAQs, delimitadas por bloques `ID:` / `CATEGORÍA:` / `PREGUNTA:` / `RESPUESTA:` / `METADATA:`).
2. Genera un embedding de 384 dimensiones por FAQ con `sentence-transformers`
   (`paraphrase-multilingual-MiniLM-L12-v2`) a partir de la pregunta. Se eligió
   este modelo multilingüe porque las consultas y el corpus están en español;
   evita que las respuestas repetitivas del dump distorsionen la búsqueda.
3. Hace un `UPSERT` a la tabla `faqs` en Postgres (se puede correr varias veces sin duplicar filas).

Para confirmar que cargó bien:

```bash
docker exec -it parachute_pgvector psql -U parachute -d parachute_faqs -c "SELECT count(*) FROM faqs;"
```

Debería devolver `120`.

### 5. Ejecutar el agente

```bash
python main.py
```

El agente conserva una sesión interactiva: escriban `Bye` o usen `Ctrl-C` para
salir. Si `SHOW_TOOL_TRACE=true`, también imprime una línea `[Herramienta]
buscar_faq` con los IDs recuperados. La traza está desactivada por defecto y no
afecta la consulta a PostgreSQL ni la respuesta del agente.

El flujo es el siguiente:

```text
pregunta → modelo solicita buscar_faq → pgvector recupera evidencia
         → resultado con rol tool → modelo redacta usando solo esa evidencia
```

Si ninguna coincidencia supera el umbral de relevancia, el programa devuelve:

> Lo siento, no puedo responder esa pregunta porque no está contemplada en la información disponible de Parachute S.A.

No se incluye el archivo completo en el prompt ni se usa el archivo legado
`FAQs_Parachute_SA_Guatemala_2026.txt` como fuente del agente.

### Pruebas

Las pruebas no requieren Docker, modelo descargado ni una API key:

```bash
python -m unittest discover -s tests -v
```

Cubren el parser del corpus, la validación de la herramienta y el intercambio
de mensajes de function calling, incluido el rechazo cuando no hay evidencia.

### Preguntas de validación

- “¿Cómo llego desde la Ciudad de Guatemala al aeródromo?” (logística).
- “¿Cuál es el límite de peso para realizar el salto?” (requisitos físicos).
- “¿Qué métodos de pago aceptan?” (precios y pagos).
- “¿Puedo llevar mi propia cámara durante el salto?” (multimedia).
- “¿Qué sucede si el clima no permite realizar el salto?” (contingencias).
- “¿Cuál es la capital de Francia?” (debe rechazarla).

Para una pregunta con varias partes, prueben: “¿Cuál es el límite de peso y qué
ocurre si hay mal clima?”. El agente debe limitarse a la evidencia recuperada.

## Video del funcionamiento del Agente

Para ver el video de prueba haz click [aquí](https://youtu.be/LKr61dtvq5M)
