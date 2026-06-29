from graph.state import AgentState


def after_route(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    if state.get("route_decision") == "clarify":
        return "ask_clarification"
    return "generate_code"


def after_execute(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    if state.get("execution_error"):
        if (state.get("code_retry_count") or 0) < 1:
            return "generate_code"
        return "handle_error"
    return "stream_answer"


def after_stream(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "finalize"
