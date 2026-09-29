"""Streamlit Chat UI - CorelDRAW debug chat

Run: streamlit run server/app.py
"""

import sys
from pathlib import Path

import streamlit as st

# Make sure the server/ directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.runner import SignageAgent


st.set_page_config(page_title="CorelDRAW Debug", page_icon="🏗️", layout="wide")

st.title("🏗️ CorelDRAW Debug")
st.caption("Control CorelDRAW with natural language to automatically generate door signs, wayfinding signs and other design files")

# =============================================================================
# Sidebar - model configuration
# =============================================================================

with st.sidebar:
    st.header("⚙️ Model configuration")

    provider = st.selectbox(
        "Provider",
        ["anthropic", "openai"],
        index=0,
        help="Anthropic = Claude models; OpenAI-compatible = DeepSeek / Qwen / Tongyi Qianwen etc.",
    )

    if provider == "openai":
        base_url = st.text_input(
            "API Base URL",
            value=st.session_state.get("base_url", ""),
            placeholder="https://api.deepseek.com",
            help="DeepSeek: api.deepseek.com | Qwen: dashscope.aliyuncs.com/compatible-mode/v1",
        )
        default_model = "deepseek-chat"
    else:
        base_url = ""
        default_model = "claude-sonnet-4-5-20250929"

    model = st.text_input("Model", value=st.session_state.get("model", default_model))

    api_key = st.text_input(
        "API Key",
        type="password",
        value=st.session_state.get("api_key", ""),
        help=f"Anthropic reads ANTHROPIC_API_KEY by default; OpenAI-compatible reads OPENAI_API_KEY / DASHSCOPE_API_KEY",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔗 Connect", use_container_width=True):
            try:
                st.session_state.agent = SignageAgent(
                    provider=provider,
                    model=model,
                    api_key=api_key or None,
                    base_url=base_url or None,
                )
                st.session_state.provider = provider
                st.session_state.model = model
                st.session_state.api_key = api_key
                st.session_state.base_url = base_url
                st.session_state.connected = True
                st.success(f"Connected {model}")
            except Exception as e:
                st.error(f"Connection failed: {e}")
                st.session_state.connected = False
    with col2:
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    if st.session_state.get("connected"):
        st.success(f"✅ {st.session_state.get('model', '')}")

    st.divider()
    st.caption("Tip: on first use, click \"🔗 Connect\" to initialize the agent")

# =============================================================================
# Initialize session state
# =============================================================================

if "agent" not in st.session_state:
    st.session_state.agent = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "connected" not in st.session_state:
    st.session_state.connected = False

# =============================================================================
# Render message history
# =============================================================================

for msg in st.session_state.messages:
    role = msg["role"]

    if role == "separator":
        st.divider()

    elif role == "reasoning":
        with st.chat_message("assistant"):
            with st.expander("🧠 Reasoning", expanded=False):
                st.markdown(msg["content"])

    elif role == "tool_call":
        with st.chat_message("assistant"):
            with st.expander(f"🔧 {msg['name']}", expanded=False):
                cols = st.columns(2)
                with cols[0]:
                    st.caption("Parameters")
                    st.json(msg.get("input", {}))
                with cols[1]:
                    st.caption("Result")
                    result = msg.get("result", {})
                    if isinstance(result, dict):
                        st.json(result)

    elif role == "preview":
        with st.chat_message("assistant"):
            st.image(
                f"data:image/png;base64,{msg['base64']}",
                caption=msg.get("path", "Preview"),
                width=400,
            )

    elif role in ("assistant", "user"):
        with st.chat_message(role):
            st.markdown(msg["content"])

    elif role == "error":
        with st.chat_message("assistant"):
            st.error(msg["content"])

# =============================================================================
# User input and agent execution
# =============================================================================

if prompt := st.chat_input("Enter a design instruction, e.g.: Generate door sign 301, department R&D Center..."):
    if not st.session_state.connected or st.session_state.agent is None:
        st.error("Please configure the model in the left sidebar and click \"🔗 Connect\" first")
        st.stop()

    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    agent: SignageAgent = st.session_state.agent

    # Run the agent, rendering events live
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        tool_results_buffer = {}  # tool_name -> result, used to pair tool_call + tool_result

        for event in agent.run_single_stream(prompt):
            etype = event["type"]

            # ---- thinking ----
            if etype == "thinking":
                status_placeholder.info(f"🤔 Thinking... (turn {event['turn']})")

            # ---- reasoning (chain of thought from DeepSeek reasoning models) ----
            elif etype == "reasoning":
                with st.expander("🧠 Reasoning", expanded=True):
                    st.markdown(event["content"])
                st.session_state.messages.append({"role": "reasoning", "content": event["content"]})

            # ---- text ----
            elif etype == "text":
                if event["content"].strip():
                    st.markdown(event["content"])
                    st.session_state.messages.append({"role": "assistant", "content": event["content"]})

            # ---- tool_call ----
            elif etype == "tool_call":
                name = event["name"]
                inp = event["input"]
                status_placeholder.info(f"🔧 Calling tool: {name}")
                tool_results_buffer[name] = {"input": inp, "result": None}

            # ---- tool_result ----
            elif etype == "tool_result":
                name = event["name"]
                result = event["result"]
                inp = tool_results_buffer.get(name, {}).get("input", {})

                with st.expander(f"🔧 {name}", expanded=True):
                    cols = st.columns(2)
                    with cols[0]:
                        st.caption("Parameters")
                        st.json(inp)
                    with cols[1]:
                        st.caption("Result")
                        st.json(result)

                st.session_state.messages.append({
                    "role": "tool_call", "name": name,
                    "input": inp, "result": result,
                })

            # ---- preview ----
            elif etype == "preview":
                st.image(
                    f"data:image/png;base64,{event['base64']}",
                    caption=event.get("path", "Preview"),
                    width=400,
                )
                st.session_state.messages.append({
                    "role": "preview", "base64": event["base64"],
                    "path": event.get("path", ""),
                })

            # ---- error ----
            elif etype == "error":
                st.error(event["error"])
                st.session_state.messages.append({"role": "error", "content": event["error"]})

            # ---- final ----
            elif etype == "final":
                status_placeholder.empty()
                if event["success"]:
                    msg = f"✅ {event['message']}\n\n> {event['turns']} turns, {event['tool_calls']} tool calls"
                    st.success(msg)
                else:
                    msg = f"❌ {event['message']}"
                    st.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                break
