"""Regression tests for duplicate email deletion failure reporting."""

import mailbox

from core.duplicate_email_engine import DuplicateEmailEngine, DuplicateEmailMessage


def _make_mailbox_with_message(directory, filename="mailbox.mbox"):

    path = str(directory / filename)

    mbox = mailbox.mbox(path)
    mbox.lock()

    message = mailbox.mboxMessage()
    message["From"] = "sender@example.com"
    message["To"] = "recipient@example.com"
    message["Subject"] = "Test Message"
    message["Message-ID"] = "<test@example.com>"
    message.set_payload("body")

    key = mbox.add(message)

    mbox.flush()
    mbox.unlock()
    mbox.close()

    return path, key


def _make_record(path, key, name="Inbox"):

    return DuplicateEmailMessage(
        id=f"{path}:{key}",
        mailbox_key=key,
        mailbox_name=name,
        mailbox_path=path,
        subject="Test Message",
    )


def test_delete_messages_reports_valid_delete(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    path, key = _make_mailbox_with_message(tmp_path)
    message = _make_record(path, key)

    engine = DuplicateEmailEngine()
    result = engine.delete_messages([message])

    assert result["deleted"] == [message]
    assert result["failures"] == []
    assert message.deleted is True

    mbox = mailbox.mbox(path)

    try:

        assert list(mbox.keys()) == []

    finally:

        mbox.close()


def test_delete_messages_reports_stale_mailbox_key(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    path, key = _make_mailbox_with_message(tmp_path)
    stale_message = _make_record(path, key + 999)

    engine = DuplicateEmailEngine()
    result = engine.delete_messages([stale_message])

    assert result["deleted"] == []
    assert len(result["failures"]) == 1

    failure = result["failures"][0]

    assert failure.message is stale_message
    assert "KeyError" in failure.reason
    assert stale_message.deleted is False


def test_delete_messages_reports_missing_mailbox_file(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    missing_path = str(tmp_path / "does_not_exist.mbox")
    message = _make_record(missing_path, 0)

    engine = DuplicateEmailEngine()
    result = engine.delete_messages([message])

    assert result["deleted"] == []
    assert len(result["failures"]) == 1

    failure = result["failures"][0]

    assert failure.message is message
    assert "not found" in failure.reason.lower()
    assert message.deleted is False


def test_delete_messages_mixed_valid_and_missing_mailbox(tmp_path, monkeypatch):

    monkeypatch.chdir(tmp_path)

    path, key = _make_mailbox_with_message(tmp_path)
    valid_message = _make_record(path, key)

    missing_path = str(tmp_path / "gone.mbox")
    missing_message = _make_record(missing_path, 0)

    engine = DuplicateEmailEngine()
    result = engine.delete_messages([valid_message, missing_message])

    assert result["deleted"] == [valid_message]
    assert len(result["failures"]) == 1
    assert result["failures"][0].message is missing_message
