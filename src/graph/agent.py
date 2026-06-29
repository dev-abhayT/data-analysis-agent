from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    route_question,
    ask_clarification,
    generate_code,
    execute_code,
    stream_answer,
    handle_error,
    finalize,
    describe_dataset,
)
from graph.edges import (
    after_route,
    after_execute,
    after_stream,
    after_describe,
)


def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("route_question", route_question)
    g.add_node("describe_dataset", describe_dataset)
    g.add_node("ask_clarification", ask_clarification)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("stream_answer", stream_answer)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)

    g.set_entry_point("route_question")

    g.add_conditional_edges(
        "route_question",
        after_route,
        {
            "ask_clarification": "ask_clarification",
            "generate_code": "generate_code",
            "describe_dataset": "describe_dataset",
            "handle_error": "handle_error",
        },
    )

    g.add_conditional_edges(
        "describe_dataset",
        after_describe,
        {
            "stream_answer": "stream_answer",
            "handle_error": "handle_error",
        },
    )

    g.add_edge("ask_clarification", "finalize")

    g.add_edge("generate_code", "execute_code")

    g.add_conditional_edges(
        "execute_code",
        after_execute,
        {
            "generate_code": "generate_code",   # retry path
            "stream_answer": "stream_answer",
            "handle_error": "handle_error",
        },
    )

    g.add_conditional_edges(
        "stream_answer",
        after_stream,
        {
            "finalize": "finalize",
            "handle_error": "handle_error",
        },
    )

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


analysis_agent = _build_graph()
