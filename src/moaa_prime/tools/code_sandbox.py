from __future__ import annotations

import ast
import builtins
import contextlib
from dataclasses import dataclass, field
import io
import re
import textwrap
from typing import Any

_FENCED_CODE_RE = re.compile(r"```(?:python|py)?\s*([\s\S]*?)```", re.IGNORECASE)
_INLINE_DEF_RE = re.compile(r"(def\s+[A-Za-z_]\w*\s*\([^)]*\)\s*:[\s\S]*)")


@dataclass(frozen=True)
class CodeSandboxResult:
    status: str
    passed: bool
    stage: str
    error_type: str | None = None
    error_message: str | None = None
    error: str | None = None
    stdout: str = ""
    line: int | None = None
    column: int | None = None
    exec_ran: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_python_source(source: str) -> str:
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.strip("\n")
    return "\n".join(line.rstrip() for line in normalized.splitlines())


def extract_python_source_deterministic(prompt: str) -> tuple[str, str] | None:
    for block in _FENCED_CODE_RE.findall(prompt):
        candidate = normalize_python_source(textwrap.dedent(block))
        if candidate:
            return candidate, "fenced_block"

    inline_match = _INLINE_DEF_RE.search(prompt)
    if inline_match:
        candidate = normalize_python_source(textwrap.dedent(inline_match.group(1)))
        if candidate:
            return candidate, "inline_def"

    stripped = normalize_python_source(prompt)
    if stripped.startswith(("def ", "class ", "import ", "from ")):
        return stripped, "prompt_as_source"

    return None


def _is_exec_safe(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except Exception:
        return False

    safe_top_level = (
        ast.AnnAssign,
        ast.Assign,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.FunctionDef,
        ast.Import,
        ast.ImportFrom,
        ast.Pass,
        ast.Expr,
    )
    for node in tree.body:
        if not isinstance(node, safe_top_level):
            return False
        if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
            return False
    return True


def _restricted_import(name: str, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".", 1)[0]
    if root in {"math"}:
        return builtins.__import__(name, globals, locals, fromlist, level)
    raise ImportError(f"import '{name}' is blocked")


def _safe_builtins() -> dict[str, Any]:
    return {
        "__build_class__": builtins.__build_class__,
        "__import__": _restricted_import,
        "Exception": Exception,
        "False": False,
        "None": None,
        "True": True,
        "ValueError": ValueError,
        "abs": abs,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "object": object,
        "print": print,
        "range": range,
        "str": str,
        "sum": sum,
    }


def verify_python_source_deterministic(
    source: str,
    *,
    execute: bool = True,
    filename: str = "<tool_first>",
) -> CodeSandboxResult:
    try:
        compiled = compile(source, filename, "exec")
    except SyntaxError as exc:
        return CodeSandboxResult(
            status="fail",
            passed=False,
            stage="compile",
            error_type=exc.__class__.__name__,
            error_message=exc.msg,
            error=f"{exc.__class__.__name__}: {exc.msg}",
            line=exc.lineno,
            column=exc.offset,
            exec_ran=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return CodeSandboxResult(
            status="fail",
            passed=False,
            stage="compile",
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            error=f"{exc.__class__.__name__}: {exc}",
            exec_ran=False,
        )

    if not execute:
        return CodeSandboxResult(status="pass", passed=True, stage="compile", exec_ran=False)

    if not _is_exec_safe(source):
        return CodeSandboxResult(
            status="pass",
            passed=True,
            stage="compile",
            exec_ran=False,
            metadata={"exec_skipped": "unsafe_top_level"},
        )

    stdout_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buffer):
            exec(compiled, {"__builtins__": _safe_builtins(), "__name__": "__tool_first__"}, {})
        return CodeSandboxResult(
            status="pass",
            passed=True,
            stage="exec",
            stdout=stdout_buffer.getvalue(),
            exec_ran=True,
        )
    except Exception as exc:
        return CodeSandboxResult(
            status="fail",
            passed=False,
            stage="exec",
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            error=f"{exc.__class__.__name__}: {exc}",
            stdout=stdout_buffer.getvalue(),
            exec_ran=True,
        )
