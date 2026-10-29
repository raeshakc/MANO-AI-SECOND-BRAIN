"""Core behaviours the README promises: approval gating, conflicts, recall, profile, briefing, calendar."""
import json

import pytest
from datetime import timedelta

import mano_core as core
from mano_core import (
    accept_proposal, add_commitment, add_message, add_proposals, add_time_block, build_prompt,
    calendar_ics, connect, erase_data, export_data, get_profile, get_relevant_history, import_data,
    interest_topics, list_commitments, list_drafts, now_local, pending_proposals,
    personalized_briefing, radar, save_profile, validated_proposals, wants_to_be_heard,
)


def test_actions_wait_for_approval():
    conn = connect()
    add_proposals(conn, [{"kind": "add_task", "title": "Read chapter 4", "due_at": None}])
    assert list_commitments(conn) == []
    accept_proposal(conn, pending_proposals(conn)[0]["id"])
    assert [t["title"] for t in list_commitments(conn)] == ["Read chapter 4"]


def test_email_draft_is_stored_not_sent():
    conn = connect()
    add_proposals(conn, [{"kind": "draft_email", "subject": "Extension request", "body": "Hi Professor,"}])
    accept_proposal(conn, pending_proposals(conn)[0]["id"])
    assert list_drafts(conn)[0]["subject"] == "Extension request"


def test_invalid_model_actions_are_dropped():
    raw = [{"kind": "send_email"}, {"kind": "schedule_block", "title": "x", "start_at": "tomorrow", "end_at": "later"},
           {"kind": "add_task", "title": "Valid", "due_at": "2026-11-02T09:00"}]
    assert [a["title"] for a in validated_proposals(raw)] == ["Valid"]


def test_conflict_radar_reports_exact_overlap():
    conn = connect()
    add_time_block(conn, "Shift", "2026-11-02T10:00", "2026-11-02T14:00")
    add_time_block(conn, "Meeting", "2026-11-02T12:00", "2026-11-02T13:00")
    add_time_block(conn, "Gym", "2026-11-02T14:00", "2026-11-02T15:00")  # touching, not overlapping
    conflicts = radar(conn)["conflicts"]
    assert len(conflicts) == 1
    assert (conflicts[0]["overlap_start"], conflicts[0]["overlap_end"]) == ("2026-11-02T12:00", "2026-11-02T13:00")


def test_yesterday_recall_only_returns_yesterday():
    conn = connect()
    add_message(conn, "user", "Exam talk", now_local() - timedelta(days=1))
    add_message(conn, "user", "Old talk", now_local() - timedelta(days=5))
    assert [m["content"] for m in get_relevant_history(conn, "what did we discuss yesterday?")] == ["Exam talk"]


def test_profile_round_trip_and_limits():
    conn = connect()
    save_profile(conn, {"name": "  Sam  ", "goals": "x" * 5000, "unknown": "ignored"})
    profile = get_profile(conn)
    assert profile["name"] == "Sam"
    assert len(profile["goals"]) == core.PROFILE_FIELDS["goals"][1]
    assert "unknown" not in profile


def test_profile_reaches_prompt_and_current_message_not_duplicated():
    conn = connect()
    save_profile(conn, {"goals": "Get an internship"})
    add_message(conn, "user", "What should I focus on?")
    messages = build_prompt(conn, "What should I focus on?")
    context = json.loads(messages[1]["content"].split("\n", 1)[1])
    assert context["student_profile"] == {"goals": "Get an internship"}
    assert all(m["content"] != "What should I focus on?" for m in context["recent_conversation"])


def test_friend_mode_detection_and_prompt():
    assert wants_to_be_heard("I'm so overwhelmed today and just need to vent")
    assert wants_to_be_heard("I feel like nobody gets it")
    assert not wants_to_be_heard("Can you add a task for my essay due Friday?")
    conn = connect()
    assert "FRIEND MODE IS ON" in build_prompt(conn, "hi", friend_mode=True)[0]["content"]
    assert "FRIEND MODE IS ON" not in build_prompt(conn, "hi", friend_mode=False)[0]["content"]


def test_friend_mode_never_stages_actions(monkeypatch):
    fake = {"reply": "That sounds really hard.", "proposals": [{"kind": "add_task", "title": "Relax", "due_at": None}]}
    monkeypatch.setattr(core, "_nemotron_json", lambda *a, **k: (json.dumps(fake), fake))
    reply, actions = core.ask_nemotron(connect(), "I'm exhausted and just need to vent")
    assert reply == "That sounds really hard." and actions == []


def test_interest_topics_split_and_dedupe():
    assert interest_topics({"interests": "AI, internships; ai\nFormula 1, chess"}) == ["AI", "internships", "Formula 1"]


def test_briefing_uses_only_found_sources(monkeypatch):
    conn = connect()
    save_profile(conn, {"interests": "AI, internships"})
    seen_queries = []

    def fake_search(topic):
        seen_queries.append(topic)
        return [{"title": f"{topic} story", "url": f"https://example.com/{topic}", "snippet": "..."},
                {"title": "dup", "url": "https://example.com/AI", "snippet": "..."}]

    captured = {}

    def fake_model(messages, **kwargs):
        captured["context"] = messages[1]["content"]
        return "", {"reply": "- AI news [1]\n- Internship news [2]", "proposals": []}

    monkeypatch.setattr(core, "_nemotron_json", fake_model)
    result = personalized_briefing(conn, search=fake_search)
    assert seen_queries == ["AI", "internships"]
    assert [s["url"] for s in result["sources"]] == ["https://example.com/AI", "https://example.com/internships"]
    assert "https://example.com/internships" in result["text"]
    assert "internships story" in captured["context"]  # the model sees only the found results


def test_briefing_requires_interests():
    try:
        personalized_briefing(connect(), search=lambda q: [])
    except ValueError as exc:
        assert "interests" in str(exc)
    else:
        raise AssertionError("Expected a helpful error when no interests are saved")


def test_profile_in_backup_and_old_backups_still_restore():
    conn = connect()
    save_profile(conn, {"name": "Sam"})
    data = export_data(conn)
    fresh = connect()
    import_data(fresh, data)
    assert get_profile(fresh)["name"] == "Sam"
    old = json.loads(data)
    del old["profile"]
    import_data(fresh, json.dumps(old).encode())  # pre-profile backup format
    assert get_profile(fresh)["name"] == ""


def test_erase_clears_profile():
    conn = connect()
    save_profile(conn, {"name": "Sam"})
    erase_data(conn)
    assert get_profile(conn)["name"] == ""


def test_calendar_export_uses_utc_with_alarm():
    conn = connect()
    add_commitment(conn, "Essay, final", "2026-11-02T18:00")
    ics = calendar_ics(list_commitments(conn)).decode()
    # 18:00 America/Chicago (CST, after DST ends Nov 1) is 00:00 UTC next day.
    assert "DTSTART:20261103T000000Z" in ics
    assert "SUMMARY:Essay\\, final" in ics
    assert "TRIGGER:-PT30M" in ics and ics.endswith("END:VCALENDAR\r\n")


class _FakeOpenAI:
    """Stands in for the Token Factory client: replies come from a queue."""
    queue: list = []
    budgets: list = []

    def __init__(self, **kwargs):
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        from types import SimpleNamespace as NS
        _FakeOpenAI.budgets.append(kwargs["max_tokens"])
        content, reason = _FakeOpenAI.queue.pop(0)
        return NS(choices=[NS(message=NS(content=content), finish_reason=reason)])


def test_empty_cut_off_reply_is_retried_with_bigger_budget(monkeypatch):
    import openai
    monkeypatch.setenv("NEBIUS_API_KEY", "test")
    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)
    _FakeOpenAI.queue = [("", "length"), ('{"reply": "Hi", "proposals": []}', "stop")]
    _FakeOpenAI.budgets = []
    text, parsed = core._nemotron_json([{"role": "user", "content": "hi"}], max_tokens=1000)
    assert parsed["reply"] == "Hi" and _FakeOpenAI.budgets == [1000, 2000]


def test_empty_reply_raises_instead_of_blank_message(monkeypatch):
    import openai
    monkeypatch.setenv("NEBIUS_API_KEY", "test")
    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)
    _FakeOpenAI.queue = [("", "length"), ("", "length")]
    with pytest.raises(RuntimeError, match="empty answer"):
        core._nemotron_json([{"role": "user", "content": "hi"}])


def test_briefing_lists_only_cited_sources_and_rejects_blank(monkeypatch):
    conn = connect()
    save_profile(conn, {"interests": "AI"})
    results = [{"title": f"Story {i}", "url": f"https://news.example/{i}", "snippet": "..."} for i in range(3)]
    monkeypatch.setattr(core, "_nemotron_json", lambda *a, **k: ("", {"reply": "- Big AI news [2]"}))
    text = personalized_briefing(conn, search=lambda q: results)["text"]
    assert "https://news.example/1" in text and "https://news.example/0" not in text
    monkeypatch.setattr(core, "_nemotron_json", lambda *a, **k: ("", {"briefing": {"AI": []}}))
    with pytest.raises(RuntimeError, match="didn't return a briefing"):
        personalized_briefing(conn, search=lambda q: results)


HERO_PROMPT = ("I'm honestly feeling overwhelmed. Everyone around me seems ahead with internships, certifications and side "
               "projects, and I feel like I have to learn everything at once. Can you help me figure out what actually "
               "matters this week, find me a few good resources, and tell me what to let go of for now?")


def test_overwhelm_plus_help_request_gets_mentor_not_friend_mode():
    assert not wants_to_be_heard(HERO_PROMPT)
    assert wants_to_be_heard("I'm so overwhelmed today and just need to vent")
    prompt = build_prompt(connect(), HERO_PROMPT)[0]["content"]
    assert "**This week**" in prompt and "**Resources**" in prompt and "FRIEND MODE IS ON" not in prompt


def test_run_together_mentor_list_is_split_into_lines():
    raw = ("I hear you. **This week** 1. **Assignment** – Due Thursday. 2. **Buildathon** – Due Saturday. "
           "3. **AI cert** – Due Saturday. **Resources** (free) - [A](https://a.example) **Let go of for now** TikTok.")
    out = core.tidy_markdown(raw)
    assert "**This week**\n\n1. **Assignment**" in out
    assert "Thursday.\n2. **Buildathon**" in out and "Saturday.\n3. **AI cert**" in out
    assert "\n\n**Resources** (free)" in out and "\n\n**Let go of for now**" in out
    assert core.tidy_markdown("Plain reply with 2. no bold") == "Plain reply with 2. no bold"
