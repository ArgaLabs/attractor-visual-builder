"""Tests for attractor.agent.tools.apply_patch."""

from __future__ import annotations

import pytest

from attractor.agent.tools.apply_patch import apply_patch, parse_patch


class TestParsePatch:
    def test_parse_add_file(self):
        patch = "*** Add File: src/hello.py\n+print('hello')\n+print('world')\n"
        ops = parse_patch(patch)
        assert len(ops) == 1
        assert ops[0].op == "add"
        assert ops[0].path == "src/hello.py"
        assert ops[0].content_lines == ["print('hello')", "print('world')"]

    def test_parse_delete_file(self):
        patch = "*** Delete File: old.txt\n"
        ops = parse_patch(patch)
        assert len(ops) == 1
        assert ops[0].op == "delete"
        assert ops[0].path == "old.txt"

    def test_parse_update_single_hunk(self):
        patch = (
            "*** Update File: main.py\n"
            "@@ def greet\n"
            " def greet():\n"
            "-    print('hi')\n"
            "+    print('hello')\n"
        )
        ops = parse_patch(patch)
        assert len(ops) == 1
        op = ops[0]
        assert op.op == "update"
        assert op.path == "main.py"
        assert len(op.hunks) == 1
        hunk = op.hunks[0]
        assert hunk.context_hint == "def greet"
        assert (" ", "def greet():") in hunk.lines
        assert ("-", "    print('hi')") in hunk.lines
        assert ("+", "    print('hello')") in hunk.lines

    def test_parse_update_with_move(self):
        patch = (
            "*** Update File: old_name.py\n"
            "*** Move to: new_name.py\n"
            "@@ class Foo\n"
            " class Foo:\n"
            "-    x = 1\n"
            "+    x = 2\n"
        )
        ops = parse_patch(patch)
        assert ops[0].new_path == "new_name.py"

    def test_parse_multi_hunk(self):
        patch = (
            "*** Update File: app.py\n"
            "@@ import os\n"
            " import os\n"
            "+import sys\n"
            "@@ def main\n"
            " def main():\n"
            "-    pass\n"
            "+    run()\n"
        )
        ops = parse_patch(patch)
        assert len(ops[0].hunks) == 2


class TestApplyPatch:
    def test_add_file(self, tmp_path):
        patch = "*** Add File: newdir/hello.py\n+print('hello')\n+print('world')\n"
        affected = apply_patch(patch, str(tmp_path))
        assert "newdir/hello.py" in affected

        created = tmp_path / "newdir" / "hello.py"
        assert created.exists()
        content = created.read_text()
        assert "print('hello')" in content
        assert "print('world')" in content

    def test_delete_file(self, tmp_path):
        target = tmp_path / "remove_me.txt"
        target.write_text("bye")
        assert target.exists()

        patch = "*** Delete File: remove_me.txt\n"
        affected = apply_patch(patch, str(tmp_path))
        assert "remove_me.txt" in affected
        assert not target.exists()

    def test_delete_nonexistent_file_no_error(self, tmp_path):
        patch = "*** Delete File: ghost.txt\n"
        affected = apply_patch(patch, str(tmp_path))
        assert "ghost.txt" in affected

    def test_update_single_hunk(self, tmp_path):
        target = tmp_path / "main.py"
        target.write_text("def greet():\n    print('hi')\n    return True\n")

        patch = (
            "*** Update File: main.py\n"
            "@@ def greet\n"
            " def greet():\n"
            "-    print('hi')\n"
            "+    print('hello')\n"
            "     return True"
        )
        affected = apply_patch(patch, str(tmp_path))
        assert "main.py" in affected

        content = target.read_text()
        assert "print('hello')" in content
        assert "print('hi')" not in content
        assert "return True" in content

    def test_update_multi_hunk(self, tmp_path):
        target = tmp_path / "app.py"
        target.write_text("import os\n\ndef main():\n    pass\n")

        patch = (
            "*** Update File: app.py\n"
            "@@ import os\n"
            " import os\n"
            "+import sys\n"
            "@@ def main\n"
            " \n"
            " def main():\n"
            "-    pass\n"
            "+    run()"
        )
        affected = apply_patch(patch, str(tmp_path))
        assert "app.py" in affected

        content = target.read_text()
        assert "import sys" in content
        assert "run()" in content
        assert "pass" not in content

    def test_move_rename(self, tmp_path):
        old = tmp_path / "old_name.py"
        old.write_text("class Foo:\n    x = 1\n")

        patch = (
            "*** Update File: old_name.py\n"
            "*** Move to: new_name.py\n"
            "@@ class Foo\n"
            " class Foo:\n"
            "-    x = 1\n"
            "+    x = 2"
        )
        affected = apply_patch(patch, str(tmp_path))
        assert "new_name.py" in affected

        assert not old.exists()
        new = tmp_path / "new_name.py"
        assert new.exists()
        content = new.read_text()
        assert "x = 2" in content

    def test_context_matching_via_hint(self, tmp_path):
        target = tmp_path / "code.py"
        target.write_text("def alpha():\n    return 1\n\ndef beta():\n    return 2\n")

        patch = (
            "*** Update File: code.py\n@@ def beta\n \n def beta():\n-    return 2\n+    return 42"
        )
        apply_patch(patch, str(tmp_path))
        content = target.read_text()
        assert "return 42" in content
        assert "return 1" in content

    def test_update_file_not_found_raises(self, tmp_path):
        patch = "*** Update File: nonexistent.py\n@@ line\n line\n-old\n+new"
        with pytest.raises(FileNotFoundError, match="nonexistent.py not found"):
            apply_patch(patch, str(tmp_path))

    def test_multiple_operations_in_one_patch(self, tmp_path):
        existing = tmp_path / "existing.py"
        existing.write_text("x = 1\n")

        patch = (
            "*** Add File: brand_new.py\n"
            "+hello = True\n"
            "*** Update File: existing.py\n"
            "@@ x = 1\n"
            "-x = 1\n"
            "+x = 2"
        )
        affected = apply_patch(patch, str(tmp_path))
        assert len(affected) == 2
        assert (tmp_path / "brand_new.py").exists()
        assert "x = 2" in existing.read_text()
