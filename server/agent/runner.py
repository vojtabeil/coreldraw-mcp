"""Agent main loop - calls the LLM API to orchestrate CorelDRAW MCP tools, supports single and batch modes

Supported providers:
    - anthropic (default): Claude models, api.anthropic.com
    - openai: OpenAI-compatible API, supports DeepSeek/Qwen/Tongyi Qianwen etc.

Example:
    agent = SignageAgent(provider="openai", model="deepseek-chat",
                         base_url="https://api.deepseek.com", api_key="sk-xxx")
    result = agent.run_single("Generate door sign 301 R&D Center")
"""

import base64
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Optional, Callable, Literal

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger("runner")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

from agent.prompts import get_system_prompt

# =============================================================================
# Tool registration and definitions (provider-independent)
# =============================================================================

_TOOL_REGISTRY: dict[str, Callable] = {}

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _build_tool_def_anthropic(func: Callable) -> dict:
    """Anthropic-format tool definition"""
    sig = inspect.signature(func)
    props, required = {}, []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        ptype = param.annotation if param.annotation is not inspect.Parameter.empty else str
        json_type = _TYPE_MAP.get(ptype, "string")
        prop = {"type": json_type, "description": f"{name} parameter"}
        has_default = param.default is not inspect.Parameter.empty
        if has_default:
            val = param.default
            if (json_type == "string" and val != "") or (json_type == "number" and val != 0):
                prop["default"] = val
        props[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "name": func.__name__,
        "description": (func.__doc__ or f"CorelDRAW tool: {func.__name__}").strip().split("\n")[0],
        "input_schema": {"type": "object", "properties": props, "required": required},
    }


def _build_tool_def_openai(func: Callable) -> dict:
    """OpenAI-compatible tool definition"""
    anthropic_def = _build_tool_def_anthropic(func)
    return {
        "type": "function",
        "function": {
            "name": anthropic_def["name"],
            "description": anthropic_def["description"],
            "parameters": anthropic_def["input_schema"],
        },
    }


def _register_tools():
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY:
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.connection import init_connection
    from tools import document, shapes, text, colors, layers, export, preflight, data_merge

    if init_connection():
        logger.info("CorelDRAW connected")
    else:
        logger.warning("CorelDRAW connection failed, tool calls will return errors (make sure CorelDRAW is running)")

    modules = [document, shapes, text, colors, layers, export, preflight, data_merge]
    _TOOL_REGISTRY = {}
    for mod in modules:
        for name, obj in inspect.getmembers(mod):
            if inspect.isfunction(obj) and not name.startswith("_") and obj.__module__.startswith("tools."):
                _TOOL_REGISTRY[name] = obj
    logger.info(f"Agent tool registration complete, {len(_TOOL_REGISTRY)} tools")


def _execute_tool(name: str, arguments: dict) -> dict:
    if name not in _TOOL_REGISTRY:
        return {"success": False, "error": f"Unknown tool: {name}"}
    try:
        result = _TOOL_REGISTRY[name](**arguments)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result if isinstance(result, dict) else {"result": str(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _read_image_base64(path: str) -> Optional[str]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


# =============================================================================
# SignageAgent - unified entry point, dispatches internally by provider
# =============================================================================

class SignageAgent:
    """Automated design agent for the signage industry

    Args:
        provider: "anthropic" (default) or "openai"
        model: Model name. Anthropic e.g. "claude-sonnet-4-6";
               OpenAI-compatible e.g. "deepseek-chat" / "qwen-max" / "gpt-4o"
        api_key: API key. Anthropic reads ANTHROPIC_API_KEY by default,
                 OpenAI-compatible reads OPENAI_API_KEY or DASHSCOPE_API_KEY by default
        base_url: OpenAI-compatible API URL.
                  DeepSeek: https://api.deepseek.com
                  Qwen: https://dashscope.aliyuncs.com/compatible-mode/v1
                  Generic: any OpenAI-compatible endpoint
    """

    def __init__(
        self,
        provider: Literal["anthropic", "openai"] = "anthropic",
        model: str = "",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model or self._default_model()
        self.api_key = api_key or self._resolve_api_key()
        self.base_url = base_url
        self.tools: list[dict] = []
        self._client = None
        self._init_tools()

    def _default_model(self) -> str:
        if self.provider == "anthropic":
            return "claude-sonnet-4-6"
        return "deepseek-chat"

    def _resolve_api_key(self) -> Optional[str]:
        if self.provider == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY")
        return (
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
        )

    # ---- Tool initialization ----

    def _init_tools(self):
        _register_tools()
        if self.provider == "anthropic":
            self.tools = [_build_tool_def_anthropic(f) for f in _TOOL_REGISTRY.values()]
        else:
            self.tools = [_build_tool_def_openai(f) for f in _TOOL_REGISTRY.values()]
        # Deduplicate
        seen = set()
        unique = []
        for t in self.tools:
            key = t.get("name", t.get("function", {}).get("name", ""))
            if key not in seen:
                seen.add(key)
                unique.append(t)
        self.tools = unique

    # ---- Client ----

    def _get_client(self):
        if self._client:
            return self._client
        if self.provider == "anthropic":
            try:
                import anthropic
            except ImportError:
                raise ImportError("Please install anthropic: pip install anthropic")
            self._client = anthropic.Anthropic(api_key=self.api_key)
            return self._client
        else:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError("Please install openai: pip install openai")
            kwargs = {"api_key": self.api_key, "timeout": 300.0}
            if self.base_url:
                kwargs["base_url"] = self.base_url.rstrip("/") + "/v1" if not self.base_url.endswith("/v1") else self.base_url
            self._client = OpenAI(**kwargs)
            return self._client

    # =====================================================================
    # Anthropic call loop
    # =====================================================================

    def _run_anthropic(self, task: str, system: str, max_turns: int) -> dict:
        client = self._get_client()
        messages: list[dict] = [{"role": "user", "content": task}]
        turn, total_calls, errors = 0, 0, []

        while turn < max_turns:
            turn += 1
            logger.info(f"Agent request, turn {turn}...")

            try:
                response = client.messages.create(
                    model=self.model, max_tokens=4096,
                    system=system, tools=self.tools, messages=messages,
                )
            except Exception as e:
                logger.error(f"Claude API call failed: {e}")
                errors.append(f"API error: {e}")
                break

            stop = response.stop_reason

            if stop == "end_turn":
                text = "".join(b.text for b in response.content if b.type == "text")
                return {"success": True, "message": text, "turns": turn, "tool_calls": total_calls, "errors": errors}

            elif stop == "tool_use":
                tool_results = []
                assistant_blocks = []

                for block in response.content:
                    if block.type == "text":
                        assistant_blocks.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        total_calls += 1
                        tool_name = block.name
                        tool_input = block.input if isinstance(block.input, dict) else {}
                        logger.info(f"  Calling tool: {tool_name}({tool_input})")
                        result = _execute_tool(tool_name, tool_input)

                        assistant_blocks.append({
                            "type": "tool_use", "id": block.id,
                            "name": block.name, "input": block.input,
                        })

                        image_b64 = None
                        if tool_name == "export_preview_png" and result.get("success"):
                            png_path = tool_input.get("path", "") or result.get("data", {}).get("path", "")
                            if png_path:
                                image_b64 = _read_image_base64(png_path)

                        tr_block = {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                        if image_b64:
                            tr_block["content"] = [
                                {"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                            ]
                        tool_results.append(tr_block)

                messages.append({"role": "assistant", "content": assistant_blocks})
                messages.append({"role": "user", "content": tool_results})
            else:
                errors.append(f"Unexpected stop_reason: {stop}")
                break

        return {"success": False, "message": f"Reached max turns {max_turns}", "turns": turn, "tool_calls": total_calls, "errors": errors}

    # =====================================================================
    # OpenAI-compatible call loop
    # =====================================================================

    def _run_openai(self, task: str, system: str, max_turns: int) -> dict:
        client = self._get_client()
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        turn, total_calls, errors = 0, 0, []

        while turn < max_turns:
            turn += 1
            logger.info(f"Agent request, turn {turn}...")

            try:
                response = client.chat.completions.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                )
            except Exception as e:
                logger.error(f"API call failed: {e}")
                errors.append(f"API error: {e}")
                break

            choice = response.choices[0]
            msg = choice.message

            # Has tool_calls -> execute tools
            if msg.tool_calls:
                total_calls += len(msg.tool_calls)

                # Append assistant message (with tool_calls)
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                })

                preview_images = []  # Collect preview PNG paths, sent later as user messages

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}
                    logger.info(f"  Calling tool: {tool_name}({tool_input})")
                    result = _execute_tool(tool_name, tool_input)

                    # In OpenAI, each tool result is a separate role=tool message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

                    # Collect previews
                    if tool_name == "export_preview_png" and result.get("success"):
                        png_path = tool_input.get("path", "") or result.get("data", {}).get("path", "")
                        if png_path and os.path.isfile(png_path):
                            preview_images.append(png_path)

                # Visual feedback: after a preview is exported, append a user message so the model can see it
                for img_path in preview_images:
                    image_b64 = _read_image_base64(img_path)
                    if image_b64:
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"This is the preview just exported: {os.path.basename(img_path)}. "
                                                                 "Please check carefully whether the design meets the requirements."},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                            ],
                        })
                        logger.info("  Preview sent to the model for visual check")

            # finish_reason == "stop" -> conversation finished
            elif choice.finish_reason == "stop":
                return {
                    "success": True,
                    "message": msg.content or "",
                    "turns": turn,
                    "tool_calls": total_calls,
                    "errors": errors,
                }
            else:
                errors.append(f"Unexpected finish_reason: {choice.finish_reason}")
                break

        return {"success": False, "message": f"Reached max turns {max_turns}", "turns": turn, "tool_calls": total_calls, "errors": errors}

    # =====================================================================
    # Public interface
    # =====================================================================

    # ---------- Generator versions (consumed by GUIs such as Streamlit) ----------

    def _run_anthropic_stream(self, task: str, system: str, max_turns: int):
        """Anthropic call loop - generator version, yields event by event"""
        client = self._get_client()
        messages: list[dict] = [{"role": "user", "content": task}]
        turn, total_calls, errors = 0, 0, []

        hit_max = False
        while turn < max_turns:
            turn += 1
            yield {"type": "thinking", "turn": turn}

            try:
                response = client.messages.create(
                    model=self.model, max_tokens=4096,
                    system=system, tools=self.tools, messages=messages,
                )
            except Exception as e:
                yield {"type": "error", "error": f"API error (turn {turn}): {e}"}
                errors.append(f"API error: {e}")
                break

            stop = response.stop_reason

            if stop == "end_turn":
                text = "".join(b.text for b in response.content if b.type == "text")
                yield {"type": "text", "content": text}
                yield {"type": "final", "success": True, "message": text, "turns": turn, "tool_calls": total_calls, "errors": errors}
                return

            elif stop == "tool_use":
                tool_results = []
                assistant_blocks = []

                for block in response.content:
                    if block.type == "text":
                        assistant_blocks.append({"type": "text", "text": block.text})
                        yield {"type": "text", "content": block.text}
                    elif block.type == "tool_use":
                        total_calls += 1
                        tool_name = block.name
                        tool_input = block.input if isinstance(block.input, dict) else {}
                        yield {"type": "tool_call", "name": tool_name, "input": tool_input}

                        result = _execute_tool(tool_name, tool_input)
                        yield {"type": "tool_result", "name": tool_name, "result": result}

                        assistant_blocks.append({
                            "type": "tool_use", "id": block.id,
                            "name": block.name, "input": block.input,
                        })

                        image_b64 = None
                        png_path = ""
                        if tool_name == "export_preview_png" and result.get("success"):
                            png_path = tool_input.get("path", "") or result.get("data", {}).get("path", "")
                            if png_path:
                                image_b64 = _read_image_base64(png_path)
                                if image_b64:
                                    yield {"type": "preview", "path": png_path, "base64": image_b64}

                        tr_block = {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                        if image_b64:
                            tr_block["content"] = [
                                {"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                            ]
                        tool_results.append(tr_block)

                messages.append({"role": "assistant", "content": assistant_blocks})
                messages.append({"role": "user", "content": tool_results})
            else:
                yield {"type": "error", "error": f"Unexpected stop_reason: {stop}"}
                errors.append(f"Unexpected stop_reason: {stop}")
                break
        else:
            hit_max = True

        final_msg = f"Reached max turns {max_turns}" if hit_max else f"Task aborted due to error ({turn} turns)"
        yield {"type": "final", "success": False, "message": final_msg, "turns": turn, "tool_calls": total_calls, "errors": errors}

    def _run_openai_stream(self, task: str, system: str, max_turns: int):
        """OpenAI-compatible call loop - generator version, yields event by event"""
        client = self._get_client()
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]
        turn, total_calls, errors = 0, 0, []

        hit_max = False
        while turn < max_turns:
            turn += 1
            yield {"type": "thinking", "turn": turn}

            try:
                response = client.chat.completions.create(
                    model=self.model, max_tokens=4096,
                    messages=messages, tools=self.tools, tool_choice="auto",
                )
            except Exception as e:
                yield {"type": "error", "error": f"API error (turn {turn}): {e}"}
                errors.append(f"API error: {e}")
                break

            choice = response.choices[0]
            msg = choice.message

            reasoning = getattr(msg, "reasoning_content", None)
            if reasoning:
                yield {"type": "reasoning", "content": reasoning}

            if msg.tool_calls:
                total_calls += len(msg.tool_calls)

                messages.append({
                    "role": "assistant", "content": msg.content or "",
                    "tool_calls": [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                   for tc in msg.tool_calls],
                })

                preview_images = []

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}
                    yield {"type": "tool_call", "name": tool_name, "input": tool_input}

                    result = _execute_tool(tool_name, tool_input)
                    yield {"type": "tool_result", "name": tool_name, "result": result}

                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": json.dumps(result, ensure_ascii=False, default=str)})

                    if tool_name == "export_preview_png" and result.get("success"):
                        png_path = tool_input.get("path", "") or result.get("data", {}).get("path", "")
                        if png_path and os.path.isfile(png_path):
                            preview_images.append(png_path)

                for img_path in preview_images:
                    image_b64 = _read_image_base64(img_path)
                    if image_b64:
                        yield {"type": "preview", "path": img_path, "base64": image_b64}
                        messages.append({
                            "role": "user", "content": [
                                {"type": "text", "text": f"This is the preview just exported: {os.path.basename(img_path)}. "
                                                                 "Please check carefully whether the design meets the requirements."},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                            ],
                        })

            elif choice.finish_reason == "stop":
                text = msg.content or ""
                yield {"type": "text", "content": text}
                yield {"type": "final", "success": True, "message": text, "turns": turn, "tool_calls": total_calls, "errors": errors}
                return
            else:
                yield {"type": "error", "error": f"Unexpected finish_reason: {choice.finish_reason}"}
                errors.append(f"Unexpected finish_reason: {choice.finish_reason}")
                break
        else:
            hit_max = True

        final_msg = f"Reached max turns {max_turns}" if hit_max else f"Task aborted due to error ({turn} turns)"
        yield {"type": "final", "success": False, "message": final_msg, "turns": turn, "tool_calls": total_calls, "errors": errors}

    # ---------- Synchronous interface ----------

    def run_single(self, task: str, system_prompt: Optional[str] = None, max_turns: int = 30) -> dict:
        """Run the agent loop for a single task"""
        system = system_prompt or get_system_prompt("full")
        if self.provider == "anthropic":
            return self._run_anthropic(task, system, max_turns)
        return self._run_openai(task, system, max_turns)

    def run_single_stream(self, task: str, system_prompt: Optional[str] = None, max_turns: int = 30):
        """Run the agent loop for a single task - generator version, yields events for a GUI to consume

        Yields events: thinking, text, tool_call, tool_result, preview, final, error
        """
        system = system_prompt or get_system_prompt("full")
        if self.provider == "anthropic":
            yield from self._run_anthropic_stream(task, system, max_turns)
        else:
            yield from self._run_openai_stream(task, system, max_turns)

    def run_batch(
        self, task: str, output_dir: str = "output",
        system_prompt: Optional[str] = None, max_turns_per_record: int = 20,
    ) -> dict:
        """Run the agent loop for a batch task"""
        os.makedirs(output_dir, exist_ok=True)
        batch_task = f"""{task}

Process each file following this workflow:
1. Open the template
2. Replace all placeholder text
3. Visual check (export a preview and inspect it)
4. Preflight (convert to curves, CMYK check)
5. Export files into the print/ and laser/ subdirectories
6. Report progress after each record

Output directory: {output_dir}"""
        return self.run_single(batch_task, system_prompt=system_prompt, max_turns=max_turns_per_record * 50)

    def check_visual(self, image_path: str, context: str = "") -> dict:
        """Run a visual check on a generated preview"""
        image_base64 = _read_image_base64(image_path)
        if not image_base64:
            return {"success": False, "error": f"Cannot read image: {image_path}"}

        system = get_system_prompt("visual")
        user_msg = f"Please check this door sign preview. {context}" if context else "Please check this design preview."

        try:
            if self.provider == "anthropic":
                client = self._get_client()
                response = client.messages.create(
                    model=self.model, max_tokens=1024, system=system,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                            {"type": "text", "text": user_msg},
                        ],
                    }],
                )
                text = "".join(b.text for b in response.content if b.type == "text")
                return {"success": True, "result": text}
            else:
                client = self._get_client()
                resp = client.chat.completions.create(
                    model=self.model, max_tokens=1024,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": [
                            {"type": "text", "text": user_msg},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                        ]},
                    ],
                )
                return {"success": True, "result": resp.choices[0].message.content or ""}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# Convenience entry point
# =============================================================================

def run_signage_task(
    task: str,
    mode: str = "single",
    provider: Literal["anthropic", "openai"] = "anthropic",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    output_dir: str = "output",
) -> dict:
    """Convenience entry point: run a signage design task

    Args:
        task: Task description or Excel file path
        mode: "single" or "batch"
        provider: "anthropic" or "openai"
        model: Model name
        api_key: API Key
        base_url: OpenAI-compatible endpoint (only needed when provider="openai")
        output_dir: Output directory for batch mode

    Examples:
        # Claude
        run_signage_task("Generate door sign 301 R&D Center")

        # DeepSeek
        run_signage_task("Generate door sign 301 R&D Center", provider="openai",
                         model="deepseek-chat", api_key="sk-xxx",
                         base_url="https://api.deepseek.com")

        # Qwen
        run_signage_task("Generate door sign 301 R&D Center", provider="openai",
                         model="qwen-max", api_key="sk-xxx",
                         base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    """
    agent = SignageAgent(provider=provider, model=model or "", api_key=api_key, base_url=base_url)
    if mode == "batch":
        return agent.run_batch(task, output_dir=output_dir)
    return agent.run_single(task)
