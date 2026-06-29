def test_graph_compiles():
    """Analysis graph compiles without requiring any env vars."""
    from graph.agent import analysis_agent
    assert analysis_agent is not None
