# Contributing to DeepMCPAgent

Thanks for taking the time to contribute — you’re awesome! 🎉  
This document explains how to set up your environment, follow our coding standards, and submit great pull requests.

---

## 👋 Ways to contribute

- 🐛 Report bugs and propose fixes
- 🧩 Improve docs, examples, and tutorials
- 🧠 Suggest features or design improvements
- ✅ Add tests and refactor for quality
- 🔌 Create example MCP servers or integration recipes

Before starting larger work, please open an issue to discuss the idea.

---

## 🧰 Development setup

DeepMCPAgent targets **Python 3.10+**.

```bash
# 1) Clone and enter the repo
git clone https://github.com/cryxnet/deepmcpagent.git
cd deepmcpagent

# 2) Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3) Install in editable mode with dev extras
pip install -e ".[dev]"

# (optional) If you plan to use the DeepAgents backend:
pip install -e ".[deep]"
```

> **macOS / Homebrew note:** if you see a PEP 668 “externally-managed-environment” error, make sure you’re inside a virtualenv as shown above.

---

## 🧪 Quality checks (run before committing)

We keep a high bar for code quality. Please run:

```bash
# Format & lint
ruff check .
ruff format .

# Type-check (mypy strict)
mypy

# Tests
pytest -q

# Docs (optional but appreciated)
mkdocs build
```

You can run an example end-to-end:

```bash
# Terminal 1 — start the sample HTTP MCP server
python examples/servers/math_server.py
# serves http://127.0.0.1:8000/mcp

# Terminal 2 — run the demo agent with fancy console output
python examples/use_agent.py
```

---

## 🧑‍💻 Code style & guidelines

- **Typing:** 100% typed. If you must use `Any`, confine it and explain why.
- **Docs:** Public APIs must include clear docstrings (Google style preferred).
- **Structure:** Keep modules focused. Avoid giant files and deeply nested logic.
- **Errors:** Raise precise exceptions with actionable messages.
- **Logging:** Prefer clear return values and exceptions over ad-hoc prints.
- **Dependencies:** Keep runtime deps minimal. Add dev deps under `[project.optional-dependencies].dev`.
- **Compatibility:** Don’t use features newer than the minimum supported Python version.

---

## 🔧 Project-specific conventions

- **MCP connectivity:** Use the FastMCP client for HTTP/SSE servers. If you add server specs or transports, keep them fully typed and documented.
- **Tools:** Convert MCP `inputSchema` → Pydantic → LangChain `BaseTool`. If you extend the schema mapping, add tests.
- **Agent loop:** Prefer **DeepAgents** when installed; otherwise the **LangGraph ReAct** fallback is used. Keep both paths healthy.
- **Prompts:** The default system prompt lives in `src/deepmcpagent/prompt.py`. If changing behavior, document rationale in the PR.

---

## 🌿 Git workflow

1. **Create a branch:**

   ```
   git checkout -b feat/short-description
   ```

2. **Commit using Conventional Commits:**

   - `feat: add HTTP auth headers to server spec`
   - `fix: prevent missing _client in tool wrapper`
   - `docs: expand README Quickstart`
   - `refactor: split agent builder`
   - `test: add coverage for schema mapper`

3. **Keep PRs focused and reasonably small.** Link related issues in the description.
4. **Checklist before opening a PR:**

   - [ ] `ruff check .` and `ruff format .` pass
   - [ ] `mypy` passes (strict)
   - [ ] `pytest` passes locally
   - [ ] Docs / examples updated if behavior changed
   - [ ] Added tests for new logic
   - [ ] No extraneous files (lockfiles, IDE configs, etc.)

---

## 📝 Documentation

We use **MkDocs + mkdocstrings**.

```bash
# Preview docs locally
mkdocs serve
```

- API references live under `docs/` and are generated from docstrings.
- Keep README examples runnable and consistent with `examples/`.

---

## 🧾 License & DCO

By contributing, you agree that your contributions are licensed under the project’s **[Apache License 2.0](LICENSE)**.
We follow a **Developer Certificate of Origin (DCO)** model — include a `Signed-off-by` line in your commits or enable GitHub’s sign-off option:

```
Signed-off-by: Your Name <you@example.com>
```

---

## 🙌 Thank you

Your time and effort make this project better for everyone. We’re excited to collaborate!
