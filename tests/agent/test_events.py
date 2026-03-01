"""Tests for attractor.agent.events."""

from __future__ import annotations

from attractor.agent.events import EventEmitter, EventKind, SessionEvent


class TestEventEmitter:
    def test_emit_calls_handlers(self):
        emitter = EventEmitter()
        received: list[SessionEvent] = []
        emitter.on(lambda e: received.append(e))

        event = SessionEvent(kind=EventKind.SESSION_START, session_id="s1")
        emitter.emit(event)

        assert len(received) == 1
        assert received[0].kind == EventKind.SESSION_START
        assert received[0].session_id == "s1"

    def test_multiple_handlers(self):
        emitter = EventEmitter()
        results_a: list[SessionEvent] = []
        results_b: list[SessionEvent] = []
        emitter.on(lambda e: results_a.append(e))
        emitter.on(lambda e: results_b.append(e))

        event = SessionEvent(kind=EventKind.USER_INPUT, session_id="s2")
        emitter.emit(event)

        assert len(results_a) == 1
        assert len(results_b) == 1

    def test_handler_exception_does_not_break_emission(self):
        emitter = EventEmitter()
        received: list[SessionEvent] = []

        def bad_handler(e: SessionEvent) -> None:
            raise RuntimeError("boom")

        emitter.on(bad_handler)
        emitter.on(lambda e: received.append(e))

        event = SessionEvent(kind=EventKind.ERROR, session_id="s3")
        emitter.emit(event)

        assert len(received) == 1

    def test_emit_simple_creates_proper_event(self):
        emitter = EventEmitter()
        received: list[SessionEvent] = []
        emitter.on(lambda e: received.append(e))

        emitter.emit_simple(EventKind.TOOL_CALL_START, "sess_abc", name="read_file")

        assert len(received) == 1
        event = received[0]
        assert event.kind == EventKind.TOOL_CALL_START
        assert event.session_id == "sess_abc"
        assert event.data["name"] == "read_file"
        assert event.timestamp > 0

    def test_emit_simple_with_no_data(self):
        emitter = EventEmitter()
        received: list[SessionEvent] = []
        emitter.on(lambda e: received.append(e))

        emitter.emit_simple(EventKind.SESSION_END, "sess_xyz")

        assert len(received) == 1
        assert received[0].data == {}

    def test_no_handlers_no_error(self):
        emitter = EventEmitter()
        event = SessionEvent(kind=EventKind.WARNING, session_id="s4")
        emitter.emit(event)  # should not raise
