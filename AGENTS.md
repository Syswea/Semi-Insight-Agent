# Agent Guidelines - Semi-Insight-Agent

This document provides essential instructions and conventions for agentic coding assistants (like yourself) operating in the `Semi-Insight-Agent` repository. Adhering to these guidelines ensures consistency, safety, and high-quality contributions to the GraphRAG and multi-agent systems.

## 1. Development & Operations

### Build & Dependency Management
- **Environment:** Python 3.10+ is required.
- **Install Dependencies:** `pip install -r requirements.txt` (or `pip install -e .` if a setup.py is present).
- **Environment Variables:** All secrets (OpenAI API keys, Neo4j credentials) must be stored in a `.env` file. **NEVER** commit the `.env` file.
- **Neo4j Setup:** Use Docker for local development:
  ```bash
  docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j
  ```

### Linting & Formatting
- **Standard Tool:** `ruff` is used for both linting and formatting.
- **Check Linting:** `ruff check .`
- **Fix Linting:** `ruff check --fix .`
- **Format Code:** `ruff format .`
- **Type Checking:** `mypy .` (Strict mode preferred for core logic).

### Testing Procedures
- **Framework:** `pytest` is the primary testing framework.
- **Run All Tests:** `pytest`
- **Run Single Test File:** `pytest tests/test_graph_logic.py`
- **Run Specific Test Case:** `pytest tests/test_graph_logic.py::test_node_transition`
- **Debug Mode:** `pytest -s` (allows seeing stdout/print statements).
- **Mocking:** Use `pytest-mock` to intercept external API calls to OpenAI or Neo4j.

---

## 2. Code Style & Conventions

### Programming Language: Python
- **Naming Conventions:**
  - **Variables/Functions:** `snake_case` (e.g., `query_graph_index`).
  - **Classes:** `PascalCase` (e.g., `SemiconductorAnalyst`).
  - **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_COUNT`).
  - **Private Members:** Prefix with a single underscore `_internal_method`.

### Imports & Structure
- **Order:** 
  1. Standard library (e.g., `os`, `sys`, `typing`)
  2. Third-party libraries (e.g., `langgraph`, `llama_index`)
  3. Local modules (e.g., `src.tools`)
- **Style:** Prefer absolute imports from the project root (`from src.logic import ...`) over relative imports.

### Type Hinting
- **Mandatory:** All function signatures must include type hints for parameters and return values.
- **Modern Syntax:** Use `list[str]` instead of `List[str]` (Python 3.9+) and `int | None` instead of `Optional[int]` (Python 3.10+).

### Error Handling & Logging
- **Exceptions:** Catch specific exceptions, not a generic `Exception`. Define custom exceptions in `src/exceptions.py`.
- **Logging:** Use the standard `logging` library. Avoid `print()` in production code. Use `logger.info` for state transitions and `logger.error` for failures in Agent nodes.

---

## 3. Agentic Architecture (Specifics)

### LangGraph State Management
- **State Definition:** Define the `State` TypedDict clearly. Document what each key represents.
- **Nodes:** Each node function should be atomic and return only the keys of the state it intends to update.
- **Edges:** Use conditional edges for routing based on "Reflection" or "Self-Correction" results.

### LlamaIndex & GraphRAG
- **Indexing:** Use `PropertyGraphIndex` for Neo4j integration as per README.
- **Schema:** Maintain a clear schema of entities (Company, Product, Policy) and relations (SUPPLIES, COMPETES_WITH).
- **Queries:** Encapsulate complex Cypher queries within dedicated "Retriever" classes.

### Tooling (MCP & Functions)
- **Model Context Protocol (MCP):** When implementing MCP servers, ensure they are modular and testable independently of the LLM. Use the standard MCP SDKs where possible.
- **Function Calling:** Tools must have descriptive docstrings. These docstrings are the "UI" for the LLM; explain every parameter clearly, including constraints and expected formats.

---

## 4. Multi-Agent Collaboration (AutoGen)
- **Roles:** Clearly define `SystemMessage` for each agent (e.g., Bullish vs. Bearish analyst). Each agent should have a distinct "personality" and set of evaluation criteria.
- **Orchestration:** Keep the debate logic inside LangGraph as a specific stage to ensure traceability. Use AutoGen's `GroupChat` or `TwoAgentChat` patterns but ensure the final consensus is captured back into the LangGraph state.

---

## 5. Security & Safety

- **Secret Management:** NEVER hardcode API keys or credentials. Use `os.getenv()` or `pydantic-settings`.
- **Data Privacy:** Be mindful of the data being sent to LLM providers. Anonymize sensitive information if required by the project scope.
- **Tool Safety:** Implement validation for all tool inputs. If a tool performs a destructive action (though unlikely in this analyst role), require explicit confirmation logic or a human-in-the-loop (HITL) node in LangGraph.

---

## 6. Documentation & Best Practices
- **Commit Messages:** Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification (e.g., `feat: add graph retriever`, `fix: resolve cycle in langgraph`).
- **Docstrings:** Use Google Style docstrings for all public classes and methods.
- **Comments:** Explain the *logic* behind complex RAG algorithms, Cypher queries, or Agent loops. Avoid stating the obvious.
- **Refactoring:** Before refactoring, check for existing tests. If tests are missing, write them first to ensure parity.
- **Pull Requests:** Keep PRs focused. One feature or bug fix per PR. Include a summary of changes and any new dependencies.

---

## 7. External Rules (Cursor/Copilot)
- **Cursor:** No specific `.cursorrules` or `.mdc` files detected in `.cursor/rules/`. Follow standard Python/LangGraph patterns.
- **Copilot:** No `.github/copilot-instructions.md` detected. Refer to this `AGENTS.md` as the source of truth for all AI-assisted development.

---

*Note: This file is a living document. Agents are encouraged to propose updates to this file as the project evolves.*

---

*Note: This file is a living document. Agents are encouraged to propose updates to this file as the project evolves.*
