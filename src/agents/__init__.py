"""
src/agents/__init__.py

AutoGen Debate Agents Package

Modules:
- debate_agents: Agent role definitions and factory functions
"""

from .debate_agents import (
    BULLISH_SYSTEM_MESSAGE,
    BEARISH_SYSTEM_MESSAGE,
    JUDGE_SYSTEM_MESSAGE,
    DEBATE_CONFIG,
    create_bullish_agent,
    create_bearish_agent,
    create_judge_agent,
    create_debate_panel,
    create_debate_intro,
)

__all__ = [
    "BULLISH_SYSTEM_MESSAGE",
    "BEARISH_SYSTEM_MESSAGE",
    "JUDGE_SYSTEM_MESSAGE",
    "DEBATE_CONFIG",
    "create_bullish_agent",
    "create_bearish_agent",
    "create_judge_agent",
    "create_debate_panel",
    "create_debate_intro",
]
