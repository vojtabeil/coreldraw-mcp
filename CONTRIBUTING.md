# Contributing to CorelDRAW Signage MCP

## Platform requirements

The core functionality depends on **Windows + the CorelDRAW COM API**. Development requires:

- Windows 10/11
- CorelDRAW X6 or later (installed and activated)
- Python 3.11+, **64-bit** (must match CorelDRAW's bitness)

On non-Windows systems you can only run static checks (`ruff check`); end-to-end tests cannot run.

---

## Quick start

```bash
git clone https://github.com/<your-fork>/coreldraw-mcp
cd coreldraw-mcp

python -m venv .venv
.venv\Scripts\activate

pip install -e ".[dev]"

cp .env.example .env
# Fill in at least one LLM API key
```

---

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|------|------|
| `feat:` | New tool or feature |
| `fix:` | Bug fix |
| `docs:` | Documentation changes |
| `refactor:` | Code restructuring with no functional change |
| `chore:` | Build/tooling changes |

## Code style

Run the linter before committing:

```bash
ruff check server/
```

Configuration is in `pyproject.toml`: `line-length=120`, `target-version=py311`, `select=E,F,I,N,W`.

---

## Adding an MCP tool

A new tool needs all three of the following:

1. **Implement the function** in the matching module under `server/tools/`, returning a `ToolResult` — see the
   standard pattern in [CLAUDE.md](CLAUDE.md)
2. **Register the tool** with `mcp.add_tool()` in `register_tools()` in `server/server.py`
3. **Write the docstring** — it is exposed to the agent as the tool description, so explain every parameter

COM constants are hard-coded integers (`cdrPNG=776`, etc.); do not import them from `win32com.client.constants`.

---

## Pull requests

1. Fork → create a branch (`feat/your-feature` or `fix/your-bug`)
2. Implement it and make sure `ruff check` passes
3. In the PR description, list the tools you changed and the CorelDRAW version you tested with
4. If you could not test locally (non-Windows), say so in the PR

---

## Reporting issues

- Bugs: open a GitHub issue with your CorelDRAW version, Python version and the error log
- Feature ideas: open an issue for discussion first to avoid duplicated work
