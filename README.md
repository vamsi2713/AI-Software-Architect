# AI Software Architect

An AI system that understands an entire software codebase. It uses retrieval-augmented generation, but goes beyond naive text-similarity RAG — retrieval combines vector search with graph traversal, so the LLM reasons over real structural relationships in the code (what calls what, what contains what), not just semantically similar text..

**Live demo:** [add your deployed URL here once live]

## Why this exists

Most "chat with your codebase" tools are just RAG over source files — they find text that _looks_ similar to your question, with no understanding of how the code actually connects together. This project takes a different approach: it parses Python source with the `ast` module (not regex, not an LLM — 100% accurate against however Python itself parses the file), builds a real graph of relationships between code elements, and combines **semantic search** with **graph traversal** to answer questions with actual structural grounding.

Ask "what would break if I change this function?" and get a real multi-hop dependency chain traced through the call graph — not a guess.

## How it works

1. **Parse** — an AST-based parser walks Python source files and extracts classes, functions, methods, imports, and function calls.
2. **Convert** — parsed code is converted into OKF (Open Knowledge Format), a unified shape for nodes and relationships, independent of the source language.
3. **Ingest** — OKF nodes and relationships are written to a graph database (Neo4j), and each node is embedded and written to a vector database (Qdrant) for semantic search.
4. **Retrieve** — a query is embedded and matched semantically against the vector store, then each match is expanded with its graph neighbors — combining "what's conceptually similar" with "what's structurally connected."
5. **Reason** — retrieved context is routed to one of four specialized agents (code analysis, dependency analysis, architecture analysis, documentation) via LangGraph, each with a narrow system prompt and a hard grounding rule: never invent relationships or code that weren't in the retrieved context.
6. **Impact analysis** — a dedicated endpoint traces the full transitive chain of everything that depends on a given function, at any depth, not just one hop.

## Tech stack

| Layer               | Technology                             |
| ------------------- | -------------------------------------- |
| API framework       | FastAPI                                |
| Agent orchestration | LangGraph                              |
| Graph database      | Neo4j AuraDB                           |
| Vector database     | Qdrant Cloud                           |
| Embeddings          | Google Gemini (`gemini-embedding-001`) |
| Reasoning LLM       | Groq (`openai/gpt-oss-20b`)            |
| Frontend            | React (Vite)                           |
| Containerization    | Docker                                 |

All heavy/stateful infrastructure runs on free-tier managed cloud services — the only thing that runs locally is the lightweight FastAPI app itself, a deliberate architectural choice to keep this runnable on hardware with limited RAM.

## Key design decisions

- **Dependency injection everywhere** — every infrastructure client is constructor-injected via `Settings`, so tests substitute fakes without touching real cloud services.
- **Idempotent writes** — Neo4j writes use `MERGE`, not `CREATE`; Qdrant point IDs are a deterministic SHA-256 hash of the node ID, so re-running ingestion updates existing data instead of duplicating it.
- **Grounded reasoning** — every reasoning agent is explicitly instructed that it was given structural relationships only, never source code, and must not fabricate implementation details it wasn't given.
- **Hybrid retrieval, not pure RAG** — semantic similarity finds conceptually relevant code; graph traversal finds structurally connected code. Combining both gives more accurate context than either alone.

## Running locally

```bash
# Backend
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
# add credentials to .env (see .env.example)
uvicorn src.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Requires free-tier accounts for Neo4j AuraDB, Qdrant Cloud, and API keys for Gemini and Groq.

## API endpoints

- `POST /ingest?repo_path=...` — parse and ingest a repository into the knowledge graph
- `POST /query?question=...` — hybrid retrieval + multi-agent reasoning over a natural language question
- `GET /impact?name=...` — multi-hop dependency/impact analysis for a given function or method name
- `GET /health` — service health check across all connected infrastructure

## Testing

```bash
pytest -v
```

## Status

Built as a portfolio project to demonstrate senior-level AI system architecture — not a toy demo, but a real working pipeline from source code to graph to grounded reasoning, with test coverage on the core logic (parsing, call resolution, impact analysis).
