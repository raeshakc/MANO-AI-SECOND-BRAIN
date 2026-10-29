from datetime import timedelta
from mano_core import (
    connect, add_commitment, add_message, add_time_block, list_time_blocks,
    now_local, radar, validated_proposals, pending_proposals, add_proposals,
    accept_proposal, export_data, erase_data, list_commitments, calendar_ics,
    build_prompt, list_drafts,
)


def test_radar_flags_real_overlap_not_adjacent():
    db = connect()
    add_time_block(db, "Class", "2026-10-29T09:00", "2026-10-29T11:00")
    add_time_block(db, "Job shift", "2026-10-29T10:00", "2026-10-29T12:00")
    add_time_block(db, "Gym", "2026-10-29T12:00", "2026-10-29T13:00")
    found = radar(db)["conflicts"]
    assert len(found) == 1
    assert found[0]["first"] == "Class"
    assert found[0]["second"] == "Job shift"
    assert found[0]["overlap_start"] == "2026-10-29T10:00"


def test_pending_schedule_requires_approval_and_a_real_end():
    db = connect()
    assert not validated_proposals([{"kind": "schedule_block", "title": "Study", "start_at": "2026-10-29T11:00", "end_at": "2026-10-29T10:00"}])
    proposal = {"kind": "schedule_block", "title": "Study", "start_at": "2026-10-29T10:00", "end_at": "2026-10-29T11:30"}
    add_proposals(db, [proposal])
    assert not list_time_blocks(db)
    action = pending_proposals(db)[0]
    accept_proposal(db, action["id"])
    assert list_time_blocks(db)[0]["title"] == "Study"
    assert not pending_proposals(db)


def test_ics_includes_schedule_blocks():
    db = connect()
    add_time_block(db, "AI Workshop", "2026-10-29T13:00", "2026-10-29T14:00")
    data = calendar_ics([], list_time_blocks(db)).decode()
    assert "SUMMARY:AI Workshop" in data
    assert "DTSTART;TZID=America/Chicago:20261029T130000" in data
    assert "TRIGGER:-PT15M" in data


def test_briefing_context_contains_radar_and_schedule():
    db = connect()
    add_time_block(db, "Meeting", "2026-10-29T10:00", "2026-10-29T11:00")
    add_time_block(db, "Class", "2026-10-29T10:30", "2026-10-29T11:30")
    prompt = build_prompt(db, "Help me plan this week")
    assert "deadline_and_conflict_radar" in prompt[1]["content"]
    assert "Meeting" in prompt[1]["content"]
    assert "Class" in prompt[1]["content"]


def test_export_and_forget_session():
    db = connect()
    add_message(db, "user", "I need to submit my project")
    add_commitment(db, "Finish assignment", "2026-10-30T11:00")
    before = export_data(db).decode()
    assert "submit my project" in before
    assert "Finish assignment" in before
    erase_data(db)
    assert not list_commitments(db)
    assert b'"messages": []' in export_data(db)


def test_email_draft_is_saved_not_sent():
    db = connect()
    add_proposals(db, [{"kind": "draft_email", "subject": "Club meeting", "body": "Hello, is Thursday okay?"}])
    assert not list_drafts(db)
    accept_proposal(db, pending_proposals(db)[0]["id"])
    assert list_drafts(db)[0]["body"] == "Hello, is Thursday okay?"


def test_radar_identifies_future_deadline_within_week():
    db = connect()
    t = now_local().replace(second=0, microsecond=0)
    due = (t + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    add_commitment(db, "Research notes", due)
    assert radar(db, at=t)["upcoming"][0]["title"] == "Research notes"
