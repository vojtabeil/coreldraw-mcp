# CorelDRAW Signage Agent — Agent Guidelines

> Only information an agent cannot infer from the code on its own.

## Platform constraints

- **All COM calls work on Windows only.** On macOS/Linux you can only do syntax checks (AST parse + importing modules
  that don't touch COM).
- **Python must be 64-bit** (`pywin32` must match CorelDRAW's bitness; 32-bit Python makes COM calls fail silently).
- **CorelDRAW must already be running.** The MCP server does not launch it if the connection fails.

## Entry points

| Entry point | Command | Purpose |
|------|------|------|
| MCP Server | `cd server && python server.py` | Tool provider for Claude/OpenCode |
| Streamlit UI | `cd server && streamlit run app.py` | Chat UI for designers / debugging |
| Agent script | `from agent.runner import SignageAgent` | Programmatic use |

The MCP server uses the `stdio` transport by default. Set `MCP_TRANSPORT=streamable-http` for HTTP mode (port 8765);
`.mcp.json` already points to that URL. The server does not hot-reload — restart it after changing code in `server/`.

## Tool layer conventions (required when adding/changing tools)

1. **Tools are plain functions** — no `@mcp.tool()` decorator. `register_tools()` in `server/server.py` registers them
   all with `mcp.add_tool()`.
2. **Every tool returns a `ToolResult`** (`from core.models import ToolResult`), built with `ToolResult.ok()` /
   `ToolResult.fail()`.
3. **Standard pattern**:
   ```python
   def tool_name(param: type) -> ToolResult:
       conn = get_connection()
       if not conn.status.connected:
           return ToolResult.fail("CorelDRAW is not connected")
       result = conn.safe_call(lambda: actual_com_work())
       if result["success"]: return ToolResult.ok(...)
       return ToolResult.fail(result.get("error", "Failed"))
   ```
4. **Every tool is registered in `server.py`** — a new tool must also get an `mcp.add_tool()` line there.
5. **The function docstring is the MCP tool description** the agent sees — explain every parameter clearly.
6. **COM constants are hard-coded integers** (`cdrDXF=1296`, `cdrPNG=802`, `cdrSVG=1345`, `cdrMillimeter=3`, etc.).
   They come from the CorelDRAW type library, whose stubs only exist after running `makepy` on Windows — do not try to
   import them from `win32com.client.constants`. Look values up in
   `C:\Program Files\Corel\<suite>\<version>\Programs64\TypeLibs\VGCoreAuto.tlb` (e.g. with
   `pythoncom.LoadTypeLib`) instead of guessing.
7. **Importing and saving**: use `import_file()` and `save_document_as()` from `core.connection`. `Import` belongs to a
   Layer, not a Document, and `SaveAs`/`ImportEx` need their options object passed explicitly — omitting it makes
   pywin32 fail with "The Python instance can not be converted to a COM object".

## Known duplication and special cases

- `_find_shape()` is duplicated in `shapes.py`, `colors.py` and `layers.py` (with small differences; not unified yet).
- `check_rgb_colors` exists in two files: `colors.py` for interactive checks, `preflight.py` for batch QA. The agent
  runner de-duplicates them.
- PNG export has two APIs: `ExportBitmap` (primary) and `Export` (fallback), because CorelDRAW versions behave
  differently.
- The Pantone fill method `FindPantone` lives at different paths in different CorelDRAW versions; there is a
  try/except with two approaches.

## Known pitfalls

- All COM calls must run on the same STA thread (`_COMThread`). In HTTP mode FastMCP dispatches tools on a thread
  pool, so tool functions must never call COM directly — always go through `conn.safe_call()`.
- `disconnect()` only releases COM references and never calls `Quit()`; the user manages CorelDRAW's lifetime.
- `reconnect_on_failure=False`: a failing tool must not trigger a reconnect, to avoid cascading crashes.
- **Shape and colour type numbers are inconsistent in the server code.** The type library and a live check on
  CorelDRAW 2025 give `cdrCurveShape=3`, `cdrBitmapShape=5`, `cdrTextShape=6`, `cdrColorPantone=1`, `cdrColorRGB=5`.
  `colors.py` uses text = 6; `engineering.py`, `preflight.py`, `document.py` and `data_merge.py` use text = 3, and several
  RGB checks test `color.Type == 1`. Verify against the version in use before relying on them (see ROADMAP backlog).
- **`GetActiveObject("CorelDRAW.Application")` can fail with "Operation unavailable"** even while CorelDRAW is running
  (seen on 2025); `Dispatch()` then attaches to the running instance. Check that the process runs first, or `Dispatch`
  will start CorelDRAW.
- **PowerTRACE via COM** (`shape.Bitmap.Trace(...)` → `TraceSettings` → `Finish()`): the colour mode is fixed by the
  `Trace()` call (`SetColorMode` fails afterwards); editing `TraceSettings.Color(i)` has no effect; built-in libraries
  (Pantone, HKS, …) only work in spot mode (`ColorMode=25` + `cdrPaletteID`); traced colours drift by ~1 RGB unit even on
  an already reduced bitmap, so snap fills afterwards.
- **SVG export** writes colours as CSS classes (`.fil0 {fill:#1D3557}`) and sometimes colour names (`white`), always as
  RGB — CMYK and spot information is lost — and sizes in inches regardless of the document unit.
- **`layer.Color` returns a COM object** and cannot go into a dict as-is; convert with `int(c)` or `str(c)`, otherwise
  FastMCP fails to serialize the outputSchema.
- **`register_tools()` imports all tool modules in one statement**: if any module fails to import, no tools get
  registered and the MCP client sees an empty tool list.
- CorelDRAW X6: `ExportEx` and `ExportBitmap` accept `None` arguments but not a COM rect from `app.CreateRect()`; the
  fallback is `doc.Export(path, filter, scope, None, None)`.

## Agent (runner.py) conventions

- `SignageAgent(provider="anthropic"|"openai", model=..., api_key=..., base_url=...)`
- API key env vars: `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY`
- `run_single()` — synchronous, blocking, returns a dict
- `run_single_stream()` — generator yielding events one by one (consumed by Streamlit). Event types: `thinking`,
  `text`, `tool_call`, `tool_result`, `preview`, `final`, `error`
- With provider `openai`: DeepSeek uses `base_url="https://api.deepseek.com"`, Qwen uses
  `base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"`
- Tool definitions are generated automatically from function signatures via `inspect.signature`

## Checks

```
ruff check server/      # lint (line-length=120, py311, E/F/I/N/W)
python test_e2e.py      # end-to-end test (needs Windows + CorelDRAW running)
```

There are no pytest unit tests (dev dependencies are declared but no test files exist yet).

## Environment

```bash
cp .env.example .env   # filling in one LLM API key is enough
```

Minimal `.env`: any one `*_API_KEY` + `MCP_TRANSPORT` (defaults to stdio). Everything else has defaults. The MCP server
itself needs no API key — only the Streamlit UI and `SignageAgent` do.

## Current status

Phase 1 MVP is complete. See `docs/ROADMAP.md` for what's done, deferred and in the backlog.
