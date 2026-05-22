"""Tests for the in-memory MessageStore."""

from __future__ import annotations

from agt.comms import MessageStore


class TestCreateAndList:
    def test_create_returns_message_with_id(self) -> None:
        store = MessageStore()
        msg = store.create(type="info", text="Hello", recipients="all", channel="banner")
        assert msg.id
        assert msg.type == "info"
        assert msg.text == "Hello"

    def test_list_all_returns_created_messages(self) -> None:
        store = MessageStore()
        m1 = store.create(type="info", text="A", recipients="all", channel="banner")
        m2 = store.create(type="warning", text="B", recipients=["alice"], channel="email")
        msgs = store.list_all()
        assert {m.id for m in msgs} == {m1.id, m2.id}


class TestGetPending:
    def test_broadcast_visible_to_any_user(self) -> None:
        store = MessageStore()
        store.create(type="info", text="Broadcast", recipients="all", channel="banner")
        assert len(store.get_pending("alice")) == 1
        assert len(store.get_pending("bob")) == 1

    def test_targeted_only_visible_to_recipient(self) -> None:
        store = MessageStore()
        store.create(type="info", text="For Alice", recipients=["alice"], channel="banner")
        assert len(store.get_pending("alice")) == 1
        assert len(store.get_pending("bob")) == 0

    def test_dismissed_message_not_returned(self) -> None:
        store = MessageStore()
        msg = store.create(type="info", text="Temp", recipients="all", channel="banner")
        store.dismiss("alice", msg.id)
        assert len(store.get_pending("alice")) == 0
        assert len(store.get_pending("bob")) == 1


class TestDismiss:
    def test_dismiss_returns_true_for_valid(self) -> None:
        store = MessageStore()
        msg = store.create(type="info", text="Hi", recipients="all", channel="banner")
        assert store.dismiss("alice", msg.id) is True

    def test_dismiss_returns_false_for_missing(self) -> None:
        store = MessageStore()
        assert store.dismiss("alice", "nonexistent") is False

    def test_dismiss_targeted_returns_false_for_wrong_user(self) -> None:
        store = MessageStore()
        msg = store.create(type="info", text="Hi", recipients=["alice"], channel="banner")
        assert store.dismiss("bob", msg.id) is False

    def test_double_dismiss_is_idempotent(self) -> None:
        store = MessageStore()
        msg = store.create(type="info", text="Hi", recipients="all", channel="banner")
        store.dismiss("alice", msg.id)
        store.dismiss("alice", msg.id)
        assert len(store.get_pending("alice")) == 0
