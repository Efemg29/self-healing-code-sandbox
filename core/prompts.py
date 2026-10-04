"""System prompts and few-shot examples for code generation and correction."""

CODE_GENERATION_SYSTEM_PROMPT = """
You are an expert Python engineer working inside a self-healing sandbox pipeline.

Requirements:
1. Produce pure Python implementation code with no markdown fences.
2. Produce comprehensive pytest tests that import from `solution` (module name is always `solution`).
3. Prefer simple, correct algorithms over clever ones.
4. Do not access the network, filesystem outside /app, or spawn background processes.
5. Keep code self-contained; only use the Python standard library and pytest.

Return a structured response matching the schema exactly.
""".strip()

CODE_GENERATION_USER_TEMPLATE = """
Task:
{task_description}

Constraints:
- Put the implementation in a module that will be saved as `solution.py`.
- Tests must use `from solution import ...` and be valid pytest.
- Cover happy path and at least one edge case.
""".strip()

CORRECTION_SYSTEM_PROMPT = """
You are a senior Python debugger performing reflection on a failed sandbox run.

Given the previous implementation, tests, and a pruned error trace:
1. Identify the root cause concisely.
2. Decide whether the test is flawed (`is_test_flawed`) or the implementation is wrong.
3. Return patched pure Python implementation and pytest code (no markdown fences).
4. Keep imports as `from solution import ...` in the tests.
5. Fix only what is necessary to make the suite pass.

Return a structured response matching the schema exactly.
""".strip()

CORRECTION_USER_TEMPLATE = """
Original task:
{task_description}

Previous implementation (`solution.py`):
```python
{implementation_code}
```

Previous tests (`test_solution.py`):
```python
{test_code}
```

Pruned sandbox error:
```
{pruned_error}
```
""".strip()

# Few-shot style example used by the mock LLM and as documentation for live prompts.
FEW_SHOT_TASK = "Write a function `add(a, b)` that returns the sum of two numbers."

FEW_SHOT_IMPLEMENTATION = '''def add(a, b):
    """Return the sum of a and b."""
    return a + b
'''

FEW_SHOT_TESTS = '''from solution import add


def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, 1) == 0


def test_add_zero():
    assert add(0, 0) == 0
'''
