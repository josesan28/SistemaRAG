# Repository Guidelines

## Project Structure & Module Organization

The root application is a Spanish FAQ RAG system. `main.py` runs the terminal
agent; `load_faqs.py` parses and embeds `Corpus_FAQs_Parachute_SA_2026.txt`;
and `parachute_faq_tool.py` / `parachute_vector_store.py` contain retrieval
and PostgreSQL/pgvector access. `init.sql` defines the database schema and
`docker-compose.yml` runs the local database.

`hdt5/` extends the project with multi-agent orchestration. Keep reusable
business logic in `hdt5/shared/`; each architecture should only wire agents in
its own `centralizada/`, `descentralizada/`, or `jerarquica/` `main.py`.
Root tests live in `tests/`; HDT5 tests live in `hdt5/tests/`. Architecture
notes and diagrams belong alongside their implementation or in `hdt5/`.

## Build, Test, and Development Commands

```bash
cp .env.example .env              # add GROQ_API_KEY; never commit .env
docker compose up -d              # start PostgreSQL with pgvector
pip install -r requirements.txt   # install Python dependencies
python load_faqs.py Corpus_FAQs_Parachute_SA_2026.txt
python main.py                    # run the base interactive agent
python -m hdt5.centralizada.main  # run one orchestration architecture
python -m unittest discover -s tests -v
python -m unittest discover -s hdt5/tests -v
```

Run the relevant test suite before submitting changes. Unit tests are designed
to run without Docker, model downloads, or API keys; mock external services.

## Coding Style & Naming Conventions

Use Python with four-space indentation, `from __future__ import annotations`,
type annotations for public functions, and short Spanish docstrings/messages
where they face users. Follow existing `snake_case` for modules, functions,
and variables; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants.
Keep tools' result contracts stable and put shared logic in `hdt5/shared/`
rather than duplicating it across architectures.

## Testing Guidelines

Use the standard-library `unittest` framework. Name test files `test_*.py`,
test methods `test_*`, and use `unittest.mock.patch` for HTTP, model, or
database boundaries. Add focused regression tests for parser formats, tool
validation, and agent handoff behavior when modifying them.

## Commit & Pull Request Guidelines

Recent history favors concise Conventional Commit subjects such as
`feat(descentralizada): agregar handoff` and `fix(descentralizada): ...`.
Use an imperative, scoped subject when practical. Pull requests should explain
the affected architecture or RAG behavior, link the relevant task/issue, list
tests run, and include terminal output or screenshots when observable behavior
changes. Do not commit API keys, `.env`, database volumes, or generated caches.
