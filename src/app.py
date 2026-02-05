"""
src/app.py

Streamlit Web Interface for Semi-Insight-Agent.
Run with: streamlit run src/app.py
"""

import streamlit as st
import json
import logging
import sys
import os
import socket
import subprocess
import threading
import time

# Configure logging to display in console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Add project root to path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.workflow.graph_builder import build_agent_graph


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_mcp_server(port: int = 8000, timeout: int = 10) -> bool:
    """
    Start MCP Server in a background thread if not already running.

    Args:
        port: Port for MCP HTTP server
        timeout: Timeout in seconds to wait for server to start

    Returns:
        True if server is running, False otherwise
    """
    if is_port_in_use(port):
        logger.info(f"[MCP] Server already running on port {port}")
        return True

    logger.info(f"[MCP] Starting MCP Server on port {port}...")

    try:
        # Start MCP server as subprocess
        mcp_process = subprocess.Popen(
            [
                sys.executable,
                "src/mcp/server.py",
                "--mode",
                "http",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Wait for server to start
        start_time = time.time()
        while time.time() - start_time < timeout:
            if is_port_in_use(port):
                logger.info(f"[MCP] Server started successfully on port {port}")
                return True
            time.sleep(0.5)

        logger.warning(f"[MCP] Server may not have started within {timeout}s")
        return is_port_in_use(port)

    except Exception as e:
        logger.error(f"[MCP] Failed to start server: {e}")
        return False


def mcp_health_check(port: int = 8000) -> bool:
    """Check if MCP server is healthy."""
    if not is_port_in_use(port):
        return False

    try:
        import httpx

        response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


# Initialize MCP Server on app startup
MCP_PORT = 8002
mcp_available = False

with st.sidebar:
    st.title("🚀 System Status")

    # Check and attempt to start MCP Server
    with st.spinner("Starting MCP Server..."):
        mcp_available = start_mcp_server(MCP_PORT)

    if mcp_available:
        # Wait a moment for server to be fully ready
        time.sleep(0.5)
        if mcp_health_check(MCP_PORT):
            st.success(f"✅ MCP Server: Running on port {MCP_PORT}")
            logger.info(f"[App] MCP Server ready at http://127.0.0.1:{MCP_PORT}")
        else:
            st.warning(f"⚠️ MCP Server: Port {MCP_PORT} open but health check failed")
            logger.warning(f"[App] MCP Server health check failed")
    else:
        st.error(f"❌ MCP Server: Failed to start on port {MCP_PORT}")
        logger.error(f"[App] MCP Server not available")

    st.divider()
    st.markdown("""
    **Available Tools:**
    - 📊 Knowledge Graph (Neo4j)
    - 🌐 Web Search (DuckDuckGo via MCP)
    - 🔍 Reflection (Self-Check)
    - 🗳️ Multi-Agent Debate (Bullish vs Bearish)
    """)

# Page config
st.set_page_config(page_title="Semi-Insight-Agent", page_icon="🧊", layout="wide")

st.title("🧩 Semi-Insight-Agent")
st.caption("Deep semiconductor industry analysis empowered by GraphRAG & Multi-Agents")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


# Initialize the graph (cache it to avoid recompilation)
@st.cache_resource
def get_graph():
    return build_agent_graph()


app = get_graph()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Ask about NVIDIA, TSMC, or industry trends..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process with Agent
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # Initial state for the graph (with debate support)
        initial_state = {
            "messages": [HumanMessage(content=prompt)],
            "reflection_count": 0,
            "max_reflections": 2,
            "context": [],
            "plan": [],
            "error": None,
            "debate_transcript": None,
            "debate_scores": None,
            "debate_key_points": None,
            "debate_assessment": None,
            "final_report": None,
        }

        # Container for intermediate steps (Thinking & Tools)
        with st.status("Analyst is thinking...", expanded=True) as status:
            try:
                # Stream events from LangGraph
                for event in app.stream(initial_state):
                    for node_name, values in event.items():
                        # Handle Reasoning Node
                        if node_name == "reasoning":
                            last_msg = values["messages"][-1]
                            try:
                                decision = json.loads(last_msg.content)
                                action = decision.get("action")

                                if action == "query_graph":
                                    query = decision.get("query")
                                    st.write(
                                        f"🔍 **Checking Knowledge Graph:** `{query}`"
                                    )

                                elif action == "final_answer":
                                    st.write("💡 **Formulating Answer...**")

                            except json.JSONDecodeError:
                                st.error(
                                    f"Failed to parse agent decision: {last_msg.content}"
                                )

                        # Handle Tool Execution Node
                        elif node_name == "tool_execution":
                            last_msg = values["messages"][-1]
                            tool_out = last_msg.content

                            if "Graph Search Result:" in tool_out:
                                label = "📊 Knowledge Graph"
                                display_out = (
                                    tool_out.replace(
                                        "Graph Search Result:", ""
                                    ).strip()[:500]
                                    + "..."
                                    if len(tool_out) > 500
                                    else tool_out.replace(
                                        "Graph Search Result:", ""
                                    ).strip()
                                )
                            elif "Web Search Result:" in tool_out:
                                label = "🌐 Web Search"
                                display_out = (
                                    tool_out.replace("Web Search Result:", "").strip()[
                                        :800
                                    ]
                                    + "..."
                                    if len(tool_out) > 800
                                    else tool_out.replace(
                                        "Web Search Result:", ""
                                    ).strip()
                                )
                            else:
                                label = "🔧 Tool Output"
                                display_out = (
                                    tool_out[:500] + "..."
                                    if len(tool_out) > 500
                                    else tool_out
                                )

                            st.write(f"**{label}:**")
                            st.code(display_out, language="text")

                        # Handle Reflection Node
                        elif node_name == "reflection":
                            last_msg = values["messages"][-1]
                            reflection_content = last_msg.content

                            if "PASSED" in reflection_content:
                                st.success(f"✅ {reflection_content}")
                            elif "FAILED" in reflection_content:
                                st.warning(f"🔄 {reflection_content}")
                            else:
                                st.info(f"🔍 {reflection_content}")

                        # Handle Debate Router Node
                        elif node_name == "debate_router":
                            st.info("📋 **Routing to Multi-Agent Debate...**")

                        # Handle Debate Node
                        elif node_name == "debate":
                            # 获取辩论结果
                            debate_result = values.get("debate_transcript", {})
                            scores = values.get("debate_scores", {})
                            final_report = values.get("final_report", "")

                            if scores:
                                st.divider()
                                st.markdown("### 🗳️ **Multi-Agent Debate Results**")

                                # 显示评分
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric(
                                        "Bullish Score",
                                        f"{scores.get('bull_score', 'N/A')}/100",
                                    )
                                with col2:
                                    st.metric(
                                        "Bearish Score",
                                        f"{scores.get('bear_score', 'N/A')}/100",
                                    )
                                with col3:
                                    st.metric(
                                        "Final Score",
                                        f"{scores.get('final_score', 'N/A')}/100",
                                    )

                                # 显示置信度和建议
                                assessment = values.get("debate_assessment", {})
                                if assessment:
                                    confidence = scores.get("confidence", "N/A")
                                    recommendation = assessment.get(
                                        "recommendation", "N/A"
                                    )
                                    risk_level = assessment.get("risk_level", "N/A")

                                    st.markdown(f"""
                                    - **Confidence:** {confidence.upper()}
                                    - **Recommendation:** {recommendation}
                                    - **Risk Level:** {risk_level.upper()}
                                    """)

                                # 显示关键论点
                                key_points = values.get("debate_key_points", {})
                                if key_points:
                                    col4, col5 = st.columns(2)
                                    with col4:
                                        st.markdown("#### 🟢 Bull Points")
                                        for point in key_points.get("bull", [])[:3]:
                                            st.markdown(f"- {point}")
                                    with col5:
                                        st.markdown("#### 🔴 Bear Points")
                                        for point in key_points.get("bear", [])[:3]:
                                            st.markdown(f"- {point}")

                                # 展开辩论过程
                                with st.expander("📜 View Full Debate Transcript"):
                                    if debate_result:
                                        st.markdown("**Round 1 - Initial Arguments:**")
                                        st.markdown(
                                            f"**Bullish:** {debate_result.get('round_1', {}).get('bullish', 'N/A')[:500]}..."
                                        )
                                        st.markdown(
                                            f"**Bearish:** {debate_result.get('round_1', {}).get('bearish', 'N/A')[:500]}..."
                                        )

                                        st.markdown("**Round 2 - Final Statements:**")
                                        st.markdown(
                                            f"**Bullish:** {debate_result.get('round_2', {}).get('bullish', 'N/A')[:500]}..."
                                        )
                                        st.markdown(
                                            f"**Bearish:** {debate_result.get('round_2', {}).get('bearish', 'N/A')[:500]}..."
                                        )

                                # 保存最终报告
                                full_response = final_report

            except Exception as e:
                st.error(f"An error occurred during execution: {e}")

            status.update(label="Analysis Complete", state="complete", expanded=False)

        # Display Final Response
        if full_response:
            message_placeholder.markdown(full_response)
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response}
            )
        else:
            fallback = (
                "I couldn't generate a final answer. Please check the trace above."
            )
            message_placeholder.markdown(fallback)
            st.session_state.messages.append({"role": "assistant", "content": fallback})
