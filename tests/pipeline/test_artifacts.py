"""Tests for attractor.pipeline.artifacts."""

from attractor.pipeline.artifacts import ArtifactStore


class TestStoreAndRetrieve:
    def test_small_artifact_inline(self):
        store = ArtifactStore()
        art = store.store("test.txt", "hello world", stage_id="A")
        assert art.inline_data == "hello world"
        assert art.file_path is None
        assert art.size == len("hello world")

        retrieved = store.retrieve(art.id)
        assert retrieved == "hello world"

    def test_retrieve_nonexistent(self):
        store = ArtifactStore()
        assert store.retrieve("nonexistent") is None


class TestListByStage:
    def test_list_all(self):
        store = ArtifactStore()
        store.store("a.txt", "aaa", stage_id="A")
        store.store("b.txt", "bbb", stage_id="B")
        all_arts = store.list()
        assert len(all_arts) == 2

    def test_list_by_stage_id(self):
        store = ArtifactStore()
        store.store("a.txt", "aaa", stage_id="A")
        store.store("b.txt", "bbb", stage_id="B")
        store.store("c.txt", "ccc", stage_id="A")
        a_arts = store.list(stage_id="A")
        assert len(a_arts) == 2
        assert all(a.stage_id == "A" for a in a_arts)


class TestRemove:
    def test_remove_existing(self):
        store = ArtifactStore()
        art = store.store("test.txt", "data")
        assert store.remove(art.id) is True
        assert store.retrieve(art.id) is None

    def test_remove_nonexistent(self):
        store = ArtifactStore()
        assert store.remove("ghost") is False


class TestMetadata:
    def test_media_type(self):
        store = ArtifactStore()
        art = store.store("data.json", '{"key":"val"}', media_type="application/json")
        assert art.media_type == "application/json"

    def test_stage_id_stored(self):
        store = ArtifactStore()
        art = store.store("x.txt", "x", stage_id="nodeX")
        assert art.stage_id == "nodeX"
