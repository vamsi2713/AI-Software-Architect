"""
Milestone 7: multi-agent LangGraph graph with a classify-then-route step.

A lightweight classify node asks Groq which specialist should handle
the question (code_analysis, dependency_analysis, architecture_analysis,
or documentation), then routes to that agent's node. Each specialist
uses the same grounding rule from Milestone 6 (never invent code or
relationships not present in the retrieved context) but frames its
answer differently depending on what kind of question it is.
"""

from typing import TypedDict

from langgraph.graph import StateGraph, END

from src.infrastructure.groq_client import GroqClient
from src.core.logging_config import get_logger

logger = get_logger(__name__)

AGENT_TYPES = ["code_analysis", "dependency_analysis", "architecture_analysis", "documentation"]

GROUNDING_RULE = (
    "CRITICAL CONSTRAINT: you have NOT been given the actual source code "
    "of these functions - only their names, file paths, and structural "
    "relationships to each other (which calls, contains, or defines "
    "which). You must NOT invent, guess, or hallucinate implementation "
    "details, code snippets, or logic you were not given. Do not claim a "
    "relationship exists unless it appears explicitly in the provided "
    "context. If the context doesn't fully answer the question, say "
    "plainly what's available and what's missing, rather than filling "
    "the gap with a plausible-sounding guess."
)

CLASSIFY_SYSTEM_PROMPT = (
    "You are a routing classifier for a codebase-analysis system. Given a "
    "question, reply with EXACTLY ONE of these words and nothing else:\n\n"
    "code_analysis - the question asks what a specific function, class, "
    "or file does, or how something is implemented\n"
    "dependency_analysis - the question asks what calls, depends on, or "
    "would break if something changed\n"
    "architecture_analysis - the question asks about overall structure, "
    "components, or how the codebase is organized\n"
    "documentation - the question asks for a plain-language explanation "
    "or summary aimed at a non-technical reader\n\n"
    "Reply with only the single matching word - no punctuation, no "
    "explanation, nothing else."
)

AGENT_SYSTEM_PROMPTS = {
    "code_analysis": (
        "You are a senior software engineer doing code analysis. Focus on "
        "explaining what the specific function(s), class(es), or file(s) "
        "in the question do, based on their names, relationships, and "
        "roles in the retrieved context. " + GROUNDING_RULE
    ),
    "dependency_analysis": (
        "You are a senior software engineer doing dependency and impact "
        "analysis. Focus on what calls the target, what the target calls, "
        "and what could be affected if the target changed - based only on "
        "the CALLS/CONTAINS/DEFINES relationships in the retrieved "
        "context. " + GROUNDING_RULE
    ),
    "architecture_analysis": (
        "You are a senior software architect explaining system structure. "
        "Focus on how files, classes, and components relate to each other "
        "at a structural level - what contains what, what the major "
        "pieces are - based on the retrieved context. " + GROUNDING_RULE
    ),
    "documentation": (
        "You are a technical writer explaining code to a non-technical "
        "reader. Use plain language and analogies where helpful, while "
        "staying strictly accurate to the retrieved context. "
        + GROUNDING_RULE
    ),
}


class ReasoningState(TypedDict):
    question: str
    context: list[dict]
    history: list[dict]  # prior [{"role": ..., "content": ...}, ...] messages in this conversation
    agent_type: str
    answer: str


def _format_context(context: list[dict]) -> str:
    """Turns the raw retrieval results into readable text for the prompt,
    preserving relationship DIRECTION (from_id -> to_id) so the model
    doesn't have to guess who calls whom."""
    lines = []
    for item in context:
        lines.append(f"- {item['name']} ({item['id']}) [similarity: {item['similarity_score']:.2f}]")
        for rel in item.get("related_nodes", []):
            if rel["from_id"] == item["id"]:
                lines.append(f"    {item['name']} --{rel['relationship_type']}--> {rel['name']}")
            else:
                lines.append(f"    {rel['name']} --{rel['relationship_type']}--> {item['name']}")
    return "\n".join(lines)


def _classify_node(state: ReasoningState, groq_client: GroqClient) -> ReasoningState:
    history_text = _format_history(state.get("history", []))
    classify_prompt = f"{history_text}Question: {state['question']}"
    raw = groq_client.generate(CLASSIFY_SYSTEM_PROMPT, classify_prompt)
    agent_type = raw.strip().lower()
    if agent_type not in AGENT_TYPES:
        logger.warning("Unrecognized agent_type %r from classifier, defaulting to code_analysis", raw)
        agent_type = "code_analysis"
    return {**state, "agent_type": agent_type}


def _route(state: ReasoningState) -> str:
    return state["agent_type"]


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    lines = ["Prior conversation in this session:"]
    for msg in history:
        speaker = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{speaker}: {msg['content']}")
    return "\n".join(lines) + "\n\n"


def _agent_node(state: ReasoningState, groq_client: GroqClient, agent_type: str) -> ReasoningState:
    context_text = _format_context(state["context"])
    history_text = _format_history(state.get("history", []))
    user_prompt = (
        f"{history_text}"
        f"Question: {state['question']}\n\nRetrieved context:\n{context_text}"
    )
    answer = groq_client.generate(AGENT_SYSTEM_PROMPTS[agent_type], user_prompt)
    return {**state, "answer": answer}


def build_reasoning_graph(groq_client: GroqClient):
    """
    Builds and compiles the multi-agent LangGraph graph. Called once per
    request from the /query endpoint - cheap to build, no need to cache
    it separately from the GroqClient itself.
    """
    graph = StateGraph(ReasoningState)

    graph.add_node("classify", lambda state: _classify_node(state, groq_client))
    for agent_type in AGENT_TYPES:
        graph.add_node(agent_type, lambda state, a=agent_type: _agent_node(state, groq_client, a))
        graph.add_edge(agent_type, END)

    graph.set_entry_point("classify")
    graph.add_conditional_edges("classify", _route, {a: a for a in AGENT_TYPES})

    return graph.compile()