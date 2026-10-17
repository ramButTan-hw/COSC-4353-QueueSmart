"""Behavioral unit tests for notification and history business rules."""
from datetime import datetime, timezone
import pytest
from a3_activity import Activity, ApiError


def join(**overrides):
    return {"type": "joined", "participationId": "visit-a", "userId": "alice",
            "serviceId": 1, "serviceName": "Help Desk", "position": 4,
            "queueOpen": True, **overrides}


def position(value, open=True):
    return {"type": "position", "participationId": "visit-a", "position": value, "queueOpen": open}


def rejects(activity, events, status):
    with pytest.raises(ApiError) as error:
        activity.apply(events)
    assert error.value.status == status


def ms(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def test_join_creates_targeted_notification_and_exact_history_timestamp():
    activity = Activity(clock=lambda: 1000)
    activity.apply([join()])
    notice, = activity.notifications.list("alice")
    assert notice["kind"] == "joined"
    assert "position 4" in notice["message"]
    assert notice["ts"] == 1000
    assert notice["read"] is False
    assert activity.notifications.list("bob") == []
    record, = activity.history.list("alice")
    assert record["outcome"] == "Waiting"
    assert record["joinedAt"] == 1000
    assert record["completedAt"] is None
    assert record["serviceName"] == "Help Desk"
    assert activity.history.list("bob") == []
    record["outcome"], notice["read"] = "Tampered", True
    assert activity.history.list("alice")[0]["outcome"] == "Waiting"
    assert activity.notifications.list("alice")[0]["read"] is False


def test_near_front_message_waits_for_open_queue_and_fires_once_per_visit():
    activity = Activity()
    activity.apply([join(), position(3), position(2, False)])
    assert len(activity.notifications.list("alice")) == 1
    activity.apply([position(2), position(1), position(4), position(2)])
    reminders = [n for n in activity.notifications.list("alice") if n["kind"] == "close"]
    assert len(reminders) == 1
    assert "nearly next" in reminders[0]["message"]
    activity.apply([join(participationId="b", userId="bob", position=1)])
    assert "You're next" in activity.notifications.list("bob")[0]["message"]


@pytest.mark.parametrize(("event_type", "outcome"), [("served", "Served"), ("left", "Left queue"), ("removed", "Removed")])
def test_completion_outcomes_preserve_record_and_allow_rejoining(event_type, outcome):
    now = [1000]
    activity = Activity(clock=lambda: now[0])
    activity.apply([join()])
    now[0] = 61000
    activity.apply([{"type": event_type, "participationId": "visit-a"}])
    assert activity.history.list("alice") == [{
        "id": "visit-a", "userId": "alice", "serviceId": 1, "serviceName": "Help Desk",
        "joinedAt": 1000, "completedAt": 61000, "date": 61000, "outcome": outcome,
    }]
    rejects(activity, [{"type": event_type, "participationId": "visit-a"}], 409)
    rejects(activity, [position(1)], 409)
    activity.apply([join(participationId="new-visit", position=1)])
    assert [r["id"] for r in activity.history.list("alice")] == ["new-visit", "visit-a"]
    assert len([n for n in activity.notifications.list("alice") if n["kind"] == "close"]) == 1


def test_duplicates_and_missing_visits_do_not_change_existing_history():
    activity = Activity()
    activity.apply([join()])
    before = activity.history.list("alice")
    rejects(activity, [join()], 409)
    rejects(activity, [join(participationId="other")], 409)
    rejects(activity, [{"type": "left", "participationId": "missing"}], 404)
    assert activity.history.list("alice") == before


def test_failed_batch_restores_reminder_state_visits_and_recipient_messages():
    activity = Activity()
    activity.apply([join(), join(participationId="b", userId="bob", position=2)])
    alice, bob = activity.notifications.list("alice"), activity.notifications.list("bob")
    history = activity.history.list("alice")
    rejects(activity, [position(2), {"type": "served", "participationId": "visit-a"},
                       join(participationId="second", position=1),
                       {"type": "left", "participationId": "missing"}], 404)
    assert activity.history.list("alice") == history
    assert activity.notifications.list("alice") == alice
    assert activity.notifications.list("bob") == bob
    activity.apply([position(2)])
    assert len([n for n in activity.notifications.list("alice") if n["kind"] == "close"]) == 1


def test_read_and_clear_affect_only_the_target_user_and_not_history():
    activity = Activity()
    activity.apply([join(), join(participationId="b", userId="bob")])
    notification_id = activity.notifications.list("alice")[0]["id"]
    with pytest.raises(ApiError) as error:
        activity.notifications.mark_read("bob", notification_id)
    assert error.value.status == 404
    assert activity.notifications.mark_read("alice", notification_id)["read"] is True
    activity.apply([position(2)])
    activity.notifications.mark_all_read("alice")
    assert len(activity.notifications.list("alice")) == 2
    assert all(n["read"] for n in activity.notifications.list("alice"))
    assert not any(n["read"] for n in activity.notifications.list("bob"))
    activity.notifications.clear("alice")
    assert activity.notifications.list("alice") == []
    assert len(activity.notifications.list("bob")) == 1
    assert len(activity.history.list("alice")) == 1


def test_clearing_messages_does_not_retrigger_near_front_reminder():
    activity = Activity()
    activity.apply([join(position=1)])
    activity.notifications.clear("alice")
    activity.apply([position(4), position(1)])
    assert activity.notifications.list("alice") == []
    activity.apply([{"type": "left", "participationId": "visit-a"},
                    join(participationId="next-visit", position=2)])
    assert sorted(n["kind"] for n in activity.notifications.list("alice")) == ["close", "joined"]


@pytest.mark.parametrize("invalid", [None, [], "event", {}, join(type="unknown"),
    join(participationId=""), join(participationId="p" * 101),
    join(userId=8), join(userId="u" * 255), join(serviceName=" "),
    join(serviceName="s" * 101), join(serviceId="1"), join(serviceId=0),
    join(serviceId=True), join(position=1.2), join(position=-1),
    join(position=9007199254740992), join(queueOpen="true"),
    join(queueOpen=1), join(unexpected="value")])
def test_invalid_events_are_rejected_without_partial_updates(invalid):
    activity = Activity()
    rejects(activity, [join(userId="bob", participationId="b"), invalid], 400)
    assert activity.history.list("bob") == []
    assert activity.notifications.list("bob") == []


@pytest.mark.parametrize("batch", [None, {}, [], [join()] * 1001])
def test_batch_shape_and_size_are_validated(batch):
    rejects(Activity(), batch, 400)


def test_maximum_field_lengths_work_and_one_extra_character_fails():
    activity = Activity()
    valid = join(participationId="p" * 100, userId="u" * 254, serviceName="s" * 100)
    activity.apply([valid])
    assert activity.history.list(valid["userId"])[0]["serviceName"] == valid["serviceName"]
    for field in ("participationId", "userId", "serviceName"):
        rejects(Activity(), [{**valid, field: valid[field] + "x"}], 400)


def test_text_fields_are_trimmed():
    activity = Activity()
    activity.apply([join(userId=" x ", serviceName=" Help ")])
    assert activity.history.list("x")[0]["serviceName"] == "Help"


def test_date_filter_includes_midnight_boundaries_by_join_time():
    midnight = ms("2026-10-16T00:00:00Z")
    now = [midnight]
    activity = Activity(clock=lambda: now[0])
    for visit, timestamp in [("before", midnight - 1), ("start", midnight),
                             ("end", midnight + 86400000 - 1), ("after", midnight + 86400000)]:
        now[0] = timestamp
        activity.apply([join(participationId=visit)])
        now[0] = midnight + 2 * 86400000
        activity.apply([{"type": "served", "participationId": visit}])
    def ids(start, end):
        return [r["id"] for r in activity.history.list("alice", start, end)]
    assert ids("2026-10-16", "2026-10-16") == ["end", "start"]
    assert ids("2026-10-17", None) == ["after"]
    assert ids(None, "2026-10-15") == ["before"]
    assert ids("2026-10-18", "2026-10-18") == []


@pytest.mark.parametrize(("start", "end"), [("2026-02-30", None),
    ("2026-13-01", None), ("", None), ("today", None),
    ("2026-10-17", "2026-10-16")])
def test_invalid_dates_return_validation_error(start, end):
    with pytest.raises(ApiError) as error:
        Activity().history.list("alice", start, end)
    assert error.value.status == 400
