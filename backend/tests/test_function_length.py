"""Keep production functions small enough for direct review, including nested bodies."""

import ast
from pathlib import Path


def test_production_functions_have_fewer_than_fifty_physical_lines() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    violations = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            assert node.end_lineno is not None
            length = node.end_lineno - node.lineno + 1
            if length >= 50:
                relative = path.relative_to(root)
                violations.append(f"{relative}:{node.lineno} {node.name}: {length} lines")
    assert not violations, "Production functions must stay below 50 lines:\n" + "\n".join(
        violations
    )
