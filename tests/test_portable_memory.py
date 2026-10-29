import json
import pytest
from mano_core import (connect, add_message, add_commitment, add_time_block,
                       export_data, import_data, erase_data, list_commitments,
                       recent_messages, list_time_blocks)


def test_portable_backup_restores_conversation_and_schedule():
    first = connect()
    add_message(first, "user", "I want to become a Google software engineer")
    add_commitment(first, "Practice DSA", "2026-10-30T09:00", "career")
    add_time_block(first, "Work shift", "2026-10-29T10:00", "2026-10-29T16:00")
    backup = export_data(first)
    second = connect()
    counts = import_data(second, backup)
    assert counts["messages"] == 1
    assert "Google software engineer" in recent_messages(second)[0]["content"]
    assert list_commitments(second)[0]["title"] == "Practice DSA"
    assert list_time_blocks(second)[0]["title"] == "Work shift"


def test_bad_import_doesnt_erase_data():
    db = connect()
    add_message(db, "user", "Original message")
    with pytest.raises(ValueError):
        import_data(db, b'{"messages": []}')
    assert recent_messages(db)[0]["content"] == "Original message"


def test_cannot_restore_giant_vault():
    with pytest.raises(ValueError):
        import_data(connect(), b'x'*1_000_001)
