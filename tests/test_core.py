from datetime import timedelta
from mano_core import (connect, add_message, messages_on_date, now_local,
                       add_commitment, calendar_ics, validated_proposals, add_proposals,
                       pending_proposals, accept_proposal, list_commitments, parse_llm_json,
                       get_relevant_history)


def test_persistent_local_memory(tmp_path):
    path = str(tmp_path / "mano.db")
    c = connect(path)
    yesterday = now_local() - timedelta(days=1)
    add_message(c, "user", "We decided to prioritize the club presentation", yesterday)
    c.close()
    c2 = connect(path)
    assert "club presentation" in messages_on_date(c2, yesterday.date())[0]["content"]
    assert get_relevant_history(c2, "What were we talking about yesterday?")[0]["role"] == "user"


def test_proposals_are_approval_only():
    c = connect()
    proposed = [{"kind": "add_task", "title": "Finish ML assignment", "due_at": "2026-10-29T14:00"}]
    add_proposals(c, proposed)
    assert list_commitments(c) == []
    item = pending_proposals(c)[0]
    assert item["kind"] == "add_task"
    accept_proposal(c, item["id"])
    assert list_commitments(c)[0]["title"] == "Finish ML assignment"
    assert not pending_proposals(c)


def test_invalid_dates_rejected():
    good = validated_proposals([{"kind":"add_task","title":"Study","due_at":"2026-10-29T14:00"}])
    bad = validated_proposals([{"kind":"add_task","title":"Study","due_at":"tomorrow"}])
    assert len(good) == 1 and not bad


def test_calendar_reminder():
    c = connect()
    add_commitment(c, "Finish project", "2026-10-30T09:00")
    ics = calendar_ics(list_commitments(c)).decode()
    assert "BEGIN:VEVENT" in ics and "BEGIN:VALARM" in ics and "Finish project" in ics


def test_parse_fenced_json():
    result = parse_llm_json('```json\n{"reply":"Hello!","proposals":[]}\n```')
    assert result["reply"] == "Hello!"
