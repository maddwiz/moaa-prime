from __future__ import annotations

from dataclasses import dataclass, field
import re
import textwrap
from typing import Any, Callable

from moaa_prime.tools import (
    extract_python_source_deterministic,
    normalize_python_source,
    verify_python_source_deterministic,
)

try:
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    _SYMPY_AVAILABLE = True
    _SYMPY_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)
except Exception:  # pragma: no cover - optional dependency
    sp = None  # type: ignore[assignment]
    parse_expr = None  # type: ignore[assignment]
    _SYMPY_AVAILABLE = False
    _SYMPY_TRANSFORMS = ()


_PROMPT_NOISE_WORDS = {
    "answer",
    "calculate",
    "compute",
    "equation",
    "evaluate",
    "find",
    "is",
    "only",
    "please",
    "return",
    "simplify",
    "solve",
    "the",
    "value",
    "what",
}
_ALLOWED_MATH_CHARS = re.compile(r"^[A-Za-z0-9_+\-*/^().=,\s]+$")
_MATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_().]+(?:\s*[+\-*/^]\s*[A-Za-z0-9_().]+)*")
_FOR_VAR_RE = re.compile(r"\bfor\s+([A-Za-z_]\w*)\b", re.IGNORECASE)
_FENCED_CODE_RE = re.compile(r"```(?:python|py)?\s*([\s\S]*?)```", re.IGNORECASE)
_DEF_LINE_RE = re.compile(r"^\s*def\s+[A-Za-z_]\w*\s*\(([^)]*)\)\s*:")
_RETURN_PLUS_RE = re.compile(r"^(\s*)return\s+([A-Za-z_]\w*)\s*\+\s*$")


@dataclass(frozen=True)
class MathToolOutcome:
    attempted: bool
    success: bool
    text: str
    mode: str
    extracted: str | None = None
    normalized: str | None = None
    solver: str = "sympy"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeVerification:
    passed: bool
    stage: str
    status: str = ""
    error_type: str | None = None
    error_message: str | None = None
    stdout: str = ""
    line: int | None = None
    column: int | None = None
    exec_ran: bool = False

    def __post_init__(self) -> None:
        if not self.status:
            object.__setattr__(self, "status", "pass" if self.passed else "fail")


@dataclass(frozen=True)
class CodeToolOutcome:
    attempted: bool
    success: bool
    text: str
    extracted: str | None
    final_code: str | None
    verification: CodeVerification
    repairs: tuple[str, ...]
    retries_used: int
    max_retries: int
    metadata: dict[str, Any] = field(default_factory=dict)


def _strip_prompt_noise(text: str) -> str:
    out = text.replace("−", "-").replace("×", "*").replace("÷", "/")
    out = re.sub(r"\s+", " ", out).strip()
    for word in _PROMPT_NOISE_WORDS:
        out = re.sub(rf"(?i)\b{re.escape(word)}\b", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _normalize_math_fragment(fragment: str) -> str:
    out = fragment.strip().rstrip(".!?")
    out = re.sub(r"[^A-Za-z0-9_+\-*/^().=,\s]", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _reduce_to_expression(fragment: str) -> str:
    matches = _MATH_TOKEN_RE.findall(fragment)
    if not matches:
        return fragment.strip()
    return max(matches, key=lambda m: (bool(re.search(r"[+\-*/^]", m)), bool(re.search(r"\d", m)), len(m))).strip()


def _extract_equation(prompt: str) -> str | None:
    for raw_line in prompt.splitlines():
        line = raw_line.strip()
        if "=" not in line:
            continue
        if ":" in line and line.rfind(":") < line.find("="):
            line = line.rsplit(":", 1)[-1]
        cleaned = _normalize_math_fragment(_strip_prompt_noise(line))
        if "=" not in cleaned:
            continue
        lhs, rhs = cleaned.split("=", 1)
        lhs_expr = _reduce_to_expression(lhs)
        rhs_expr = _reduce_to_expression(rhs)
        if not lhs_expr or not rhs_expr:
            continue
        candidate = f"{lhs_expr} = {rhs_expr}"
        if _ALLOWED_MATH_CHARS.fullmatch(candidate):
            return candidate
    return None


def _extract_expression(prompt: str) -> str | None:
    cleaned = _normalize_math_fragment(_strip_prompt_noise(prompt))
    if not cleaned or "=" in cleaned:
        return None
    candidate = _reduce_to_expression(cleaned)
    if not candidate:
        return None
    has_math_signal = bool(re.search(r"[+\-*/^]", candidate) or re.search(r"\d", candidate))
    if not has_math_signal:
        return None
    if not _ALLOWED_MATH_CHARS.fullmatch(candidate):
        return None
    return candidate


def _extract_math_candidate(prompt: str) -> tuple[str, str | None, str]:
    for block in _FENCED_CODE_RE.findall(prompt):
        block_text = block.strip()
        if not block_text:
            continue
        equation = _extract_equation(block_text)
        if equation is not None:
            return "equation", equation, "fenced_block"
        expression = _extract_expression(block_text)
        if expression is not None:
            return "expression", expression, "fenced_block"

    equation = _extract_equation(prompt)
    if equation is not None:
        return "equation", equation, "prompt_line"

    expression = _extract_expression(prompt)
    if expression is not None:
        return "expression", expression, "prompt_text"

    return "none", None, "none"


def _parse_sympy_expr(expr_text: str):
    if not _SYMPY_AVAILABLE or parse_expr is None:
        raise RuntimeError("sympy unavailable")
    normalized = expr_text.replace("^", "**").strip()
    if not _ALLOWED_MATH_CHARS.fullmatch(normalized):
        raise ValueError("unsupported characters")
    return parse_expr(normalized, transformations=_SYMPY_TRANSFORMS, evaluate=True)


def _pick_symbol(prompt: str, symbols) -> Any:
    names = {s.name: s for s in symbols}
    match = _FOR_VAR_RE.search(prompt)
    if match:
        wanted = match.group(1)
        if wanted in names:
            return names[wanted]
    if "x" in names:
        return names["x"]
    return sorted(symbols, key=lambda s: s.name)[0]


def run_math_tool_first(prompt: str) -> MathToolOutcome:
    mode, extracted, extraction_method = _extract_math_candidate(prompt)
    if extracted is None:
        return MathToolOutcome(
            attempted=False,
            success=False,
            text="",
            mode="none",
            metadata={"reason": "no_math_candidate", "extraction_method": extraction_method},
        )

    if not _SYMPY_AVAILABLE:
        return MathToolOutcome(
            attempted=True,
            success=False,
            text="",
            mode=mode,
            extracted=extracted,
            normalized=extracted,
            error="sympy unavailable",
            metadata={"reason": "sympy_unavailable", "extraction_method": extraction_method},
        )

    try:
        if mode == "equation":
            lhs_raw, rhs_raw = extracted.split("=", 1)
            lhs_norm = lhs_raw.strip().replace("^", "**")
            rhs_norm = rhs_raw.strip().replace("^", "**")
            lhs_expr = _parse_sympy_expr(lhs_norm)
            rhs_expr = _parse_sympy_expr(rhs_norm)
            all_symbols = sorted(lhs_expr.free_symbols.union(rhs_expr.free_symbols), key=lambda s: s.name)

            if not all_symbols:
                residual = sp.simplify(lhs_expr - rhs_expr) if sp is not None else lhs_expr - rhs_expr
                truthy = bool(residual == 0)
                return MathToolOutcome(
                    attempted=True,
                    success=True,
                    text=str(truthy),
                    mode=mode,
                    extracted=extracted,
                    normalized=f"{lhs_norm} = {rhs_norm}",
                    metadata={"extraction_method": extraction_method, "symbol_count": 0},
                )

            target = _pick_symbol(prompt, all_symbols)
            eq = sp.Eq(lhs_expr, rhs_expr)  # type: ignore[union-attr]
            solutions = sp.solve(eq, target)  # type: ignore[union-attr]

            if not solutions:
                result_text = f"No solution for {target}"
            elif len(solutions) == 1:
                result_text = f"{target} = {solutions[0]}"
            else:
                joined = ", ".join(str(v) for v in solutions)
                result_text = f"{target} in [{joined}]"

            return MathToolOutcome(
                attempted=True,
                success=True,
                text=result_text,
                mode=mode,
                extracted=extracted,
                normalized=f"{lhs_norm} = {rhs_norm}",
                metadata={
                    "extraction_method": extraction_method,
                    "target_symbol": str(target),
                    "solution_count": len(solutions),
                },
            )

        expr_norm = extracted.strip().replace("^", "**")
        expr = _parse_sympy_expr(expr_norm)
        if getattr(expr, "free_symbols", None):
            rendered = str(sp.simplify(expr))  # type: ignore[union-attr]
            result_text = f"Simplified: {rendered}"
        else:
            rendered = str(sp.simplify(expr))  # type: ignore[union-attr]
            result_text = rendered

        return MathToolOutcome(
            attempted=True,
            success=True,
            text=result_text,
            mode=mode,
            extracted=extracted,
            normalized=expr_norm,
            metadata={"extraction_method": extraction_method},
        )
    except Exception as exc:
        return MathToolOutcome(
            attempted=True,
            success=False,
            text="",
            mode=mode,
            extracted=extracted,
            normalized=extracted,
            error=str(exc),
            metadata={"reason": "sympy_error", "extraction_method": extraction_method},
        )


def _normalize_code_source(source: str) -> str:
    return normalize_python_source(source)


def extract_python_source(prompt: str) -> tuple[str, str] | None:
    return extract_python_source_deterministic(prompt)


def verify_python_source(source: str, *, execute: bool = True) -> CodeVerification:
    sandbox = verify_python_source_deterministic(source, execute=execute, filename="<tool_first>")
    return CodeVerification(
        status=sandbox.status,
        passed=sandbox.passed,
        stage=sandbox.stage,
        error_type=sandbox.error_type,
        error_message=sandbox.error_message,
        stdout=sandbox.stdout,
        line=sandbox.line,
        column=sandbox.column,
        exec_ran=sandbox.exec_ran,
    )


def _repair_missing_colon(source: str, verification: CodeVerification) -> tuple[str, str] | None:
    if verification.error_type != "SyntaxError":
        return None
    if "expected ':'" not in (verification.error_message or ""):
        return None
    if verification.line is None:
        return None

    lines = source.splitlines()
    idx = verification.line - 1
    if idx < 0 or idx >= len(lines):
        return None
    target = lines[idx]
    if target.rstrip().endswith(":"):
        return None
    if not re.match(r"^\s*(def|if|elif|else|for|while|try|except|finally|class|with)\b", target):
        return None

    lines[idx] = target.rstrip() + ":"
    return "\n".join(lines), "add_missing_colon"


def _repair_expected_indent(source: str, verification: CodeVerification) -> tuple[str, str] | None:
    if "expected an indented block" not in (verification.error_message or ""):
        return None
    if verification.line is None:
        return None

    lines = source.splitlines()
    idx = verification.line - 1
    if 0 <= idx < len(lines):
        line = lines[idx]
        if line.strip() and not line.startswith((" ", "\t")):
            lines[idx] = f"    {line}"
            return "\n".join(lines), "indent_expected_block"

    def_idx = max(0, idx - 1)
    if def_idx < len(lines) and re.match(r"^\s*def\s+[A-Za-z_]\w*\s*\([^)]*\)\s*:\s*$", lines[def_idx]):
        lines.insert(def_idx + 1, "    pass")
        return "\n".join(lines), "insert_pass_block"

    return None


def _repair_tabs(source: str, _verification: CodeVerification) -> tuple[str, str] | None:
    if "\t" not in source:
        return None
    return source.replace("\t", "    "), "tabs_to_spaces"


def _parse_def_params(def_line: str) -> list[str]:
    m = _DEF_LINE_RE.match(def_line)
    if not m:
        return []
    raw = m.group(1)
    out: list[str] = []
    for chunk in raw.split(","):
        p = chunk.strip()
        if not p:
            continue
        p = p.split("=", 1)[0].strip()
        p = p.lstrip("*")
        if re.fullmatch(r"[A-Za-z_]\w*", p):
            out.append(p)
    return out


def _repair_trailing_plus_return(source: str, verification: CodeVerification) -> tuple[str, str] | None:
    if verification.error_type != "SyntaxError":
        return None
    if "invalid syntax" not in (verification.error_message or ""):
        return None

    lines = source.splitlines()
    for idx, line in enumerate(lines):
        m = _RETURN_PLUS_RE.match(line)
        if not m:
            continue
        leading_ws, lhs_name = m.groups()
        params: list[str] = []
        for def_idx in range(idx, -1, -1):
            params = _parse_def_params(lines[def_idx])
            if params:
                break
        if len(params) < 2:
            continue
        if lhs_name != params[0]:
            continue
        rhs_name = params[1]
        lines[idx] = f"{leading_ws}return {lhs_name} + {rhs_name}"
        return "\n".join(lines), "repair_trailing_plus_return"
    return None


def _repair_whitespace(source: str, _verification: CodeVerification) -> tuple[str, str] | None:
    normalized = _normalize_code_source(textwrap.dedent(source))
    if normalized == source:
        return None
    return normalized, "normalize_whitespace"


_REPAIR_RULES: tuple[Callable[[str, CodeVerification], tuple[str, str] | None], ...] = (
    _repair_missing_colon,
    _repair_expected_indent,
    _repair_tabs,
    _repair_trailing_plus_return,
    _repair_whitespace,
)


def _apply_repair(source: str, verification: CodeVerification) -> tuple[str, str] | None:
    for rule in _REPAIR_RULES:
        patched = rule(source, verification)
        if patched is not None and patched[0] != source:
            return patched
    return None


def _render_code_text(success: bool, source: str, verification: CodeVerification, repairs: list[str]) -> str:
    if success:
        if repairs:
            status = f"Verified after {len(repairs)} deterministic repair(s)."
        elif verification.exec_ran:
            status = "Verified (compile + restricted exec)."
        else:
            status = "Verified (compile only)."
        return f"{status}\n```python\n{source}\n```"

    error_name = verification.error_type or "Error"
    error_msg = verification.error_message or "unknown failure"
    return f"Verification failed at {verification.stage}: {error_name}: {error_msg}\n```python\n{source}\n```"


def run_code_tool_first(prompt: str, *, max_retries: int = 2, execute: bool = True) -> CodeToolOutcome:
    retries = max(0, int(max_retries))
    extracted = extract_python_source(prompt)
    if extracted is None:
        return CodeToolOutcome(
            attempted=False,
            success=False,
            text="",
            extracted=None,
            final_code=None,
            verification=CodeVerification(
                passed=False,
                stage="extract",
                error_type="ExtractionError",
                error_message="no_python_source_found",
                exec_ran=False,
            ),
            repairs=(),
            retries_used=0,
            max_retries=retries,
            metadata={"reason": "extraction_failed"},
        )

    current, extraction_method = extracted
    current = _normalize_code_source(current)
    verification = verify_python_source(current, execute=execute)

    repairs: list[str] = []
    while not verification.passed and len(repairs) < retries:
        repaired = _apply_repair(current, verification)
        if repaired is None:
            break
        current, rule_name = repaired
        repairs.append(rule_name)
        verification = verify_python_source(current, execute=execute)

    success = verification.passed
    text = _render_code_text(success, current, verification, repairs)
    return CodeToolOutcome(
        attempted=True,
        success=success,
        text=text,
        extracted=extracted[0],
        final_code=current,
        verification=verification,
        repairs=tuple(repairs),
        retries_used=len(repairs),
        max_retries=retries,
        metadata={"extraction_method": extraction_method, "execute_requested": bool(execute)},
    )
