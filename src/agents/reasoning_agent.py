"""
Milestone 6: a minimal LangGraph graph with a single reasoning node.

This takes the hybrid-retrieved context from Milestone 5 (semantic
matches + their graph neighbors) and asks Groq to synthesize it into
a real natural-language answer, instead of leaving the caller to read
raw JSON.

Deliberately kept to ONE node for this milestone - a real multi-agent
graph (specialized Code Analysis / Dependency Analysis / Architecture
agents) is Milestone 7's job, not this one. This milestone's job is
just proving the LangGraph + Groq wiring works correctly end-to-end.
"""

from typing import TypedDict

from langgraph.graph import StateGraph, END

from src.infrastructure.groq_client import GroqClient

SYSTEM_PROMPT = (
    "You are a senior software architect explaining a codebase to another "
    "engineer. You are given a question and retrieved context - a list of "
    "code elements (files, classes, functions, methods) found to be "
    "relevant, along with their structural relationships (which calls "
    "which, what contains what, similarity scores). "
    "\n\n"
    "CRITICAL CONSTRAINT: you have NOT been given the actual source code "
    "of these functions - only their names, file paths, and structural "
    "relationships to each other. You must NOT invent, guess, or "
    "hallucinate implementation details, code snippets, or logic you "
    "were not given. Do not write example code. Do not claim a function "
    "calls something unless that exact call appears in the provided "
    "relationships. "
    "\n\n"
    "Answer using ONLY the structural facts given: which files/classes/"
    "functions are relevant, and which of them call, contain, or define "
    "which others. If the context doesn't fully answer the question, say "
    "plainly what structural information is available and what is missing, "
    "rather than filling the gap with a plausible-sounding guess."
)


class ReasoningState(TypedDict):
    question: str
    context: list[dict]
    answer: str


def _reason_node(state: ReasoningState, groq_client: GroqClient) -> ReasoningState:
    context_text = _format_context(state["context"])
    user_prompt = f"Question: {state['question']}\n\nRetrieved context:\n{context_text}"
    answer = groq_client.generate(SYSTEM_PROMPT, user_prompt)
    return {**state, "answer": answer}


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


def build_reasoning_graph(groq_client: GroqClient):
    """
    Builds and compiles the LangGraph graph. Called once per request from
    the /query endpoint - cheap to build, no need to cache it separately
    from the GroqClient itself.
    """
    graph = StateGraph(ReasoningState)
    graph.add_node("reason", lambda state: _reason_node(state, groq_client))
    graph.set_entry_point("reason")
    graph.add_edge("reason", END)
    return graph.compile()