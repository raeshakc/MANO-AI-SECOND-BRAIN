from datetime import date, datetime
from mano_core import (
    connect, add_commitment, add_time_block, add_proposals, pending_proposals,
    build_rescue_plan, accept_proposal, list_time_blocks, list_commitments,
)

NOW = datetime(2026, 10, 29, 8, 0)


def test_rescue_prioritizes_due_soon_and_avoids_existing_blocks():
    db = connect()
    add_commitment(db, "Club presentation", "2026-10-29T17:00", "career")
    add_commitment(db, "Architecture exam", "2026-10-30T16:00", "academic")
    add_time_block(db, "Class", "2026-10-29T09:00", "2026-10-29T11:00")
    p = build_rescue_plan(db, date(2026, 10, 29), days=2,
                          day_start="09:00", day_end="18:00", at=NOW)
    first = p["proposals"][0]
    assert first["title"] == "Focus: Club presentation"
    assert first["start_at"] == "2026-10-29T11:00"
    assert p["proposals"][1]["start_at"] == "2026-10-29T12:00"


def test_no_plan_when_no_saved_tasks():
    db = connect()
    p = build_rescue_plan(db, date(2026, 10, 29), at=NOW)
    assert p["proposals"] == []
    assert p["considered"] == 0


def test_unavailable_window_reports_unscheduled():
    db = connect()
    add_commitment(db, "Exam tomorrow", "2026-10-29T11:00")
    add_time_block(db, "Shift", "2026-10-29T09:00", "2026-10-29T11:00")
    p = build_rescue_plan(db, date(2026, 10, 29), 1, "09:00", "11:00", 60, at=NOW)
    assert not p["proposals"]
    assert p["unscheduled"] == ["Exam tomorrow"]


def test_plan_uses_user_window_not_unconfirmed_external_availability():
    db = connect()
    add_commitment(db, "Coding practice", None)
    p = build_rescue_plan(db, date(2026, 10, 29), 1, "15:00", "16:00", 60, at=NOW)
    assert p["proposals"][0]["start_at"] == "2026-10-29T15:00"
    assert "not connected" in p["note"]


def test_plan_stage_and_approval_are_separate():
    db = connect()
    add_commitment(db, "Study", "2026-10-30T18:00")
    p = build_rescue_plan(db, date(2026, 10, 29), at=NOW)
    assert add_proposals(db, p["proposals"]) == 1
    assert not list_time_blocks(db)
    assert add_proposals(db, p["proposals"]) == 0
    accept_proposal(db, pending_proposals(db)[0]["id"])
    assert len(list_time_blocks(db)) == 1
    assert not build_rescue_plan(db, date(2026, 10, 29), at=NOW)["proposals"]


def test_duplicate_tasks_are_not_staged_twice():
    db = connect()
    p = {"kind":"add_task", "title":"Exercise", "due_at":"2026-10-30T18:00"}
    assert add_proposals(db, [p,p]) == 1
    assert add_proposals(db, [p]) == 0
    accept_proposal(db, pending_proposals(db)[0]["id"])
    assert add_proposals(db, [p]) == 0
    assert len(list_commitments(db)) == 1


def test_invalid_availability_is_rejected():
    db = connect()
    try:
        build_rescue_plan(db, date(2026, 10, 29), 1, "18:00", "09:00", at=NOW)
    except ValueError:
        pass
    else:
        assert False, "Backwards availability should fail"
