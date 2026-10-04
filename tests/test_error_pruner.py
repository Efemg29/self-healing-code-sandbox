"""Unit tests for the error pruner (no Docker / LLM required)."""

from sandbox.error_pruner import prune_error_log


def test_strips_stdlib_paths_and_keeps_assertion():
    stderr = """
============================= FAILURES ==============================
___________________________ test_add_positive ___________________________
/usr/lib/python3.11/site-packages/pytest/runner.py:100: in run
    something()
/app/test_solution.py:5: in test_add_positive
    assert add(2, 3) == 5
E   AssertionError: assert 6 == 5
E    +  where 6 = add(2, 3)
"""
    pruned = prune_error_log(stderr)
    assert "AssertionError" in pruned
    assert "test_add_positive" in pruned
    assert "/usr/lib/python3.11" not in pruned


def test_truncates_from_top_keeping_bottom():
    long_stderr = "\n".join(f"noise line {i}" for i in range(200))
    long_stderr += "\nAssertionError: boom\n"
    pruned = prune_error_log(long_stderr, max_chars=200)
    assert len(pruned) <= 220  # allow truncation marker
    assert "AssertionError: boom" in pruned
    assert pruned.startswith("...[truncated]...") or "AssertionError" in pruned
