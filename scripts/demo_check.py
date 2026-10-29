"""Deterministic offline demo check, no API key, no private data."""
from datetime import timedelta
from mano_core import (
    accept_proposal, add_proposals, connect, list_commitments, list_time_blocks,
    load_demo_scenario, pending_proposals, radar, now_local, get_relevant_history,
)


def main():
    conn = connect()
    load_demo_scenario(conn)
    result = radar(conn)
    assert result["conflicts"], "Expected at least one synthetic schedule clash"
    assert get_relevant_history(conn, "What were we talking about yesterday?")
    proposed = {"kind": "add_task", "title": "Practice exam questions", "due_at": (now_local()+timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")}
    before = len(list_commitments(conn))
    add_proposals(conn, [proposed])
    assert len(list_commitments(conn)) == before, "No action executes before approval"
    accept_proposal(conn, pending_proposals(conn)[0]["id"])
    assert len(list_commitments(conn)) == before + 1
    print("PASS: Synthetic clash detected; yesterday recalled; task executed only after approval.")
    print("Tasks:", len(list_commitments(conn)), "Blocks:", len(list_time_blocks(conn)))


if __name__ == "__main__":
    main()
