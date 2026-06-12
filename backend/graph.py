from langgraph.graph import END, START, StateGraph

from agents.human_review import human_review_node
from agents.market_scout import market_scout_node
from agents.policy_librarian import policy_librarian_node
from agents.risk_synthesizer import risk_synthesizer_node
from state import State, should_synthesize


def build_graph():
    builder = StateGraph(State)
    builder.add_node("market_scout", market_scout_node)
    builder.add_node("policy_librarian", policy_librarian_node)
    builder.add_node("risk_synthesizer", risk_synthesizer_node)
    builder.add_node("human_review", human_review_node)

    builder.add_edge(START, "market_scout")
    builder.add_edge("market_scout", "policy_librarian")
    builder.add_conditional_edges(
        "policy_librarian",
        should_synthesize,
        {"risk_synthesizer": "risk_synthesizer", "human_review": "human_review"},
    )
    builder.add_edge("risk_synthesizer", END)
    builder.add_edge("human_review", END)

    return builder.compile()


graph = build_graph()
