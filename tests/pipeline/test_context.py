"""Tests for attractor.pipeline.context.Context."""

from attractor.pipeline.context import Context


class TestSetGet:
    def test_set_and_get(self):
        ctx = Context()
        ctx.set("key", "value")
        assert ctx.get("key") == "value"

    def test_get_default(self):
        ctx = Context()
        assert ctx.get("missing") is None
        assert ctx.get("missing", 42) == 42

    def test_initial_data(self):
        ctx = Context({"a": 1, "b": 2})
        assert ctx.get("a") == 1
        assert ctx.get("b") == 2


class TestUpdate:
    def test_update_multiple(self):
        ctx = Context({"x": 1})
        ctx.update({"y": 2, "z": 3})
        assert ctx.get("y") == 2
        assert ctx.get("z") == 3

    def test_update_overwrites(self):
        ctx = Context({"x": 1})
        ctx.update({"x": 99})
        assert ctx.get("x") == 99


class TestDelete:
    def test_delete_existing(self):
        ctx = Context({"a": 1})
        ctx.delete("a")
        assert ctx.get("a") is None

    def test_delete_nonexistent(self):
        ctx = Context()
        ctx.delete("nope")


class TestHas:
    def test_has_true(self):
        ctx = Context({"x": 1})
        assert ctx.has("x") is True

    def test_has_false(self):
        ctx = Context()
        assert ctx.has("x") is False


class TestKeys:
    def test_keys(self):
        ctx = Context({"a": 1, "b": 2})
        assert sorted(ctx.keys()) == ["a", "b"]

    def test_keys_empty(self):
        ctx = Context()
        assert ctx.keys() == []


class TestClone:
    def test_clone_isolation(self):
        ctx = Context({"x": [1, 2, 3]})
        clone = ctx.clone()
        clone.set("x", [99])
        assert ctx.get("x") == [1, 2, 3]

    def test_clone_has_same_data(self):
        ctx = Context({"a": 1, "b": 2})
        clone = ctx.clone()
        assert clone.get("a") == 1
        assert clone.get("b") == 2

    def test_clone_deep_copy(self):
        nested = {"inner": [1, 2]}
        ctx = Context({"data": nested})
        clone = ctx.clone()
        clone.get("data")["inner"].append(3)
        assert ctx.get("data")["inner"] == [1, 2]


class TestSnapshot:
    def test_snapshot_returns_dict(self):
        ctx = Context({"a": 1})
        snap = ctx.snapshot()
        assert isinstance(snap, dict)
        assert snap == {"a": 1}

    def test_snapshot_is_deep_copy(self):
        ctx = Context({"items": [1, 2]})
        snap = ctx.snapshot()
        snap["items"].append(3)
        assert ctx.get("items") == [1, 2]


class TestApplyUpdates:
    def test_apply_updates(self):
        ctx = Context({"a": 1})
        ctx.apply_updates({"b": 2, "a": 10})
        assert ctx.get("a") == 10
        assert ctx.get("b") == 2
