"""Agent loop, reusable skills and Opportunity Radar, with Nemotron and Tavily mocked."""
import json
from datetime import timedelta

import pytest

import mano_agent as agent
import mano_core as core
from mano_core import add_commitment, add_time_block, connect, now_local, pending_proposals, save_profile


def script(monkeypatch, responses):
    """Make Nemotron return these JSON objects in order, recording what it was sent."""
    calls = []

    def fake(messages, **kwargs):
        calls.append(messages)
        reply = responses[min(len(calls), len(responses)) - 1]
        return json.dumps(reply), reply

    monkeypatch.setattr(core, "_nemotron_json", fake)
    return calls


def test_agent_chains_a_skill_then_answers(monkeypatch):
    conn = connect()
    add_time_block(conn, "Shift", "2026-11-02T10:00", "2026-11-02T14:00")
    add_time_block(conn, "Meeting", "2026-11-02T12:00", "2026-11-02T13:00")
    calls = script(monkeypatch, [
        {"thought": "See what's on their plate", "skill": "check_schedule", "args": {}},
        {"reply": "Your shift overlaps the meeting from 12 to 1. Your shift is scheduled at 10.", "proposals": []},
    ])
    reply, proposals, steps = agent.run_agent(conn, "What does my week look like?")
    assert "overlaps" in reply and "scheduled at 10" in reply  # factual wording isn't treated as a fake claim
    assert proposals == []
    assert [s["skill"] for s in steps] == ["check_schedule"]
    assert steps[0]["summary"].endswith("1 conflict(s)")
    assert "Skill result" in calls[1][-1]["content"] and "Meeting" in calls[1][-1]["content"]
    assert "AGENT MODE" in calls[0][0]["content"] and "find_opportunities" in calls[0][0]["content"]


def test_planner_blocks_are_staged_only_as_proposals(monkeypatch):
    conn = connect()
    tomorrow = (now_local() + timedelta(days=1)).date()
    add_commitment(conn, "Essay", f"{tomorrow + timedelta(days=1)}T17:00", "academic")
    script(monkeypatch, [
        {"skill": "plan_focus_time", "args": {"available_from": "09:00", "available_until": "12:00",
                                              "start_date": tomorrow.isoformat(), "days": 1}},
        {"reply": "Here's a block for your essay.", "proposals": []},  # model forgets to repeat it
    ])
    reply, proposals, steps = agent.run_agent(conn, "I'm free 9 to noon tomorrow, plan my essay time")
    assert [p["title"] for p in proposals] == ["Focus: Essay"]
    assert proposals[0]["start_at"] == f"{tomorrow}T09:00"
    assert core.list_time_blocks(conn) == []  # nothing saved without approval


def test_planner_refuses_to_guess_hours(monkeypatch):
    result = agent.run_skill(connect(), "plan_focus_time", {})
    assert "needs_input" in result


def test_unknown_skill_and_errors_become_data(monkeypatch):
    conn = connect()
    assert "Unknown skill" in agent.run_skill(conn, "send_email", {})["error"]
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert "TAVILY_API_KEY" in agent.run_skill(conn, "search_news", {"topic": "AI"})["error"]
    # undeclared arguments are dropped, not passed through
    assert "messages" in agent.run_skill(conn, "recall_conversations", {"query": "x", "sql": "DROP TABLE"})


def test_agent_stops_after_skill_budget(monkeypatch):
    conn = connect()
    calls = script(monkeypatch, [{"skill": "check_schedule", "args": {"n": i}} for i in range(10)])
    reply, proposals, steps = agent.run_agent(conn, "help", max_skill_calls=3)
    assert len(steps) == 3 and len(calls) == 5  # 3 skills, the final turn, and one retry for an empty answer
    assert any("used all skill calls" in m["content"] for m in calls[-1])
    assert reply  # a graceful answer, never a crash


def test_repeated_call_is_not_rerun(monkeypatch):
    conn = connect()
    ran = []
    monkeypatch.setitem(agent.SKILLS["check_schedule"], "fn", lambda c: ran.append(1) or {"overdue": [], "due_within_7_days": [], "conflicts": []})
    script(monkeypatch, [{"skill": "check_schedule", "args": {}}, {"skill": "check_schedule", "args": {}},
                         {"reply": "Done", "proposals": []}])
    _, _, steps = agent.run_agent(conn, "what's due?")
    assert len(ran) == 1 and steps[1]["ok"] is False


def test_friend_mode_skips_skills(monkeypatch):
    calls = script(monkeypatch, [{"reply": "That sounds exhausting. I'm here.", "proposals": [{"kind": "add_task", "title": "x"}]}])
    reply, proposals, steps = agent.run_agent(connect(), "I'm so overwhelmed and just need to vent")
    assert steps == [] and proposals == [] and len(calls) == 1
    assert "AGENT MODE" not in calls[0][0]["content"]


def test_opportunity_query_uses_profile_and_cycle():
    profile = {"interests": "machine learning, robotics", "school": "CS sophomore", "location": "Austin, TX"}
    q = agent.opportunity_query(profile, "internships")
    assert "machine learning robotics" in q and "internship" in q
    cycle = now_local().year + (1 if now_local().month >= 8 else 0)
    assert str(cycle) in q
    assert "Austin, TX" in agent.opportunity_query(profile, "events")
    assert agent.opportunity_query(profile, "bogus").endswith("application")  # falls back to internships


def test_radar_cards_only_point_at_real_results(monkeypatch):
    conn = connect()
    save_profile(conn, {"interests": "AI", "goals": "SWE internship"})
    future = (now_local().date() + timedelta(days=40)).isoformat()
    results = [{"title": "Acme AI Internship", "url": "https://acme.example/jobs/1", "snippet": f"Apply by {future}"},
               {"title": "Dup", "url": "https://acme.example/jobs/1", "snippet": ""},
               {"title": "Blog listicle", "url": "https://blog.example/top", "snippet": "..."}]
    script(monkeypatch, [{"items": [
        {"source": 1, "title": "Acme AI Intern", "organization": "Acme", "deadline": future, "why_it_fits": "Matches your SWE goal"},
        {"source": 1, "title": "Same card twice"},
        {"source": 9, "title": "Hallucinated"},
        {"source": 2, "title": "Old one", "deadline": "2020-01-01"},
        {"source": "x"},
    ]}])
    out = agent.opportunity_radar(conn, "internships", search=lambda q: results)
    assert [s["url"] for s in out["sources"]] == ["https://acme.example/jobs/1", "https://blog.example/top"]
    assert [i["url"] for i in out["items"]] == ["https://acme.example/jobs/1", "https://blog.example/top"]
    assert out["items"][0]["deadline"] == future and out["items"][1]["deadline"] is None


def test_tracking_an_opportunity_needs_approval():
    conn = connect()
    item = {"title": "Acme AI Intern", "organization": "Acme", "deadline": "2027-01-15", "url": "https://acme.example/1"}
    assert core.add_proposals(conn, [agent.opportunity_task(item)]) == 1
    assert core.add_proposals(conn, [agent.opportunity_task(item)]) == 0  # no duplicates
    assert core.list_commitments(conn) == []
    assert pending_proposals(conn)[0]["payload"]["due_at"] == "2027-01-15T23:59"


@pytest.mark.parametrize("name", list(agent.SKILLS))
def test_every_skill_is_described(name):
    spec = agent.SKILLS[name]
    assert spec["label"] and spec["description"] and name in agent.agent_protocol()


def test_agent_context_is_a_snapshot_so_skills_do_the_lookup(monkeypatch):
    conn = connect()
    add_commitment(conn, "Secret essay title", "2026-11-02T17:00")
    calls = script(monkeypatch, [{"reply": "ok", "proposals": []}])
    agent.run_agent(conn, "what's due?")
    context = calls[0][1]["content"]
    assert '"open_tasks": 1' in context and "Secret essay title" not in context


def test_schedule_skill_gives_weekday_labels():
    conn = connect()
    add_commitment(conn, "Essay", "2026-10-30T18:00")
    due = agent.run_skill(conn, "check_schedule", {})
    assert any(t["due"] == "Fri Oct 30, 6:00 PM" for t in due["due_within_7_days"] + due["overdue"])


def test_demo_chat_weekdays_match_the_deadlines():
    conn = connect()
    core.load_demo_scenario(conn)
    said = core.recent_messages(conn)[0]["content"]
    exam = next(t for t in core.list_commitments(conn) if "exam" in t["title"])
    from datetime import datetime
    assert datetime.fromisoformat(exam["due_at"]).strftime("%A") in said


def test_empty_or_json_scrap_reply_is_retried_never_shown(monkeypatch):
    conn = connect()
    calls = script(monkeypatch, [{"reply": '{"": ""}'}, {"reply": "I'm your friend and mentor, Raesha.", "proposals": []}])
    reply, _, _ = agent.run_agent(conn, "Who are you to me exactly")
    assert reply == "I'm your friend and mentor, Raesha." and len(calls) == 2
    script(monkeypatch, [{"reply": ""}])
    assert agent.run_agent(conn, "hello?")[0] == core.LOST_WORDS


def test_mano_knows_a_person_not_a_file():
    prompt = core.build_prompt(connect(), "what do you know about me")[0]["content"]
    assert "Know them as a person, not a file" in prompt and "never a list of data" in prompt
    assert "never save them as interests" in prompt and "about (who they are" in prompt
