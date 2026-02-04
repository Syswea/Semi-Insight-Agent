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

        # Initial state for the graph
        initial_state = {"messages": [HumanMessage(content=prompt)]}

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
                                    full_response = decision.get("content")
                                    st.write("💡 **Formulating Answer...**")

                            except json.JSONDecodeError:
                                st.error(
                                    f"Failed to parse agent decision: {last_msg.content}"
                                )

                        # Handle Tool Execution Node
                        elif node_name == "tool_execution":
                            last_msg = values["messages"][-1]
                            # Truncate long tool outputs for display
                            tool_out = last_msg.content
                            display_out = (
                                tool_out[:500] + "..."
                                if len(tool_out) > 500
                                else tool_out
                            )
                            st.code(display_out, language="json")

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
