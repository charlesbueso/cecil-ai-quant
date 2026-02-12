"""Safe Python code execution tool.

Provides a restricted ``exec``-based sandbox that agents (especially the
Software Developer agent) can use to run generated code.  Only
whitelisted modules are available inside the sandbox.
"""

from __future__ import annotations

import io
import json
import logging
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Modules the sandbox is allowed to import
_ALLOWED_MODULES = {
    "math", "statistics", "json", "datetime", "collections",
    "itertools", "functools", "operator", "re", "textwrap",
    "numpy", "pandas",
}


def _make_sandbox_globals() -> dict[str, Any]:
    """Build a restricted globals dict for ``exec``."""
    import math
    import statistics
    import numpy as np
    import pandas as pd

    safe_builtins = {
        k: v
        for k, v in __builtins__.items()  # type: ignore[union-attr]
        if k
        not in {
            "exec",
            "eval",
            "compile",
            "__import__",
            "open",
            "input",
            "breakpoint",
            "exit",
            "quit",
        }
    }

    def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in _ALLOWED_MODULES:
            raise ImportError(f"Import of '{name}' is not allowed in the sandbox")
        return __import__(name, *args, **kwargs)

    safe_builtins["__import__"] = _safe_import

    return {
        "__builtins__": safe_builtins,
        "np": np,
        "pd": pd,
        "math": math,
        "statistics": statistics,
        "json": json,
    }


@tool
def execute_python_code(code: str) -> str:
    """Execute Python code in a sandboxed environment and return the output.

    The sandbox has access to: numpy (as np), pandas (as pd), math,
    statistics, json, and standard builtins (no file I/O, no exec/eval,
    no arbitrary imports).

    Use ``print()`` to produce output.  The last expression's repr is
    also captured.

    Args:
        code: Python source code to execute.

    Returns:
        JSON with stdout, stderr, result (repr of last expression), and
        any error information.
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    sandbox = _make_sandbox_globals()
    result_value = None
    error = None

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            # Try to capture the last expression value
            lines = code.strip().split("\n")
            if lines:
                try:
                    # If the last line is an expression, capture its value
                    compile(lines[-1], "<sandbox>", "eval")
                    exec_code = "\n".join(lines[:-1])
                    if exec_code.strip():
                        exec(exec_code, sandbox)
                    result_value = eval(lines[-1], sandbox)
                except SyntaxError:
                    exec(code, sandbox)
    except Exception:
        error = traceback.format_exc()

    stdout_text = stdout_buf.getvalue()
    stderr_text = stderr_buf.getvalue()

    # Truncate large outputs
    max_out = 8000
    if len(stdout_text) > max_out:
        stdout_text = stdout_text[:max_out] + "\n... [truncated]"

    output: dict[str, Any] = {
        "stdout": stdout_text,
        "stderr": stderr_text,
    }
    if result_value is not None:
        result_repr = repr(result_value)
        if len(result_repr) > max_out:
            result_repr = result_repr[:max_out] + "... [truncated]"
        output["result"] = result_repr

    if error:
        output["error"] = error

    output["success"] = error is None
    return json.dumps(output)


@tool
def generate_analysis_code(task_description: str) -> str:
    """Generate a Python code template for a financial analysis task.

    This does NOT execute the code – it returns a template string that
    can be reviewed and then passed to ``execute_python_code``.

    Args:
        task_description: Plain-English description of the analysis to perform.

    Returns:
        A Python code string template (not executed).
    """
    # This is a structural helper – the actual code generation is done by LLM.
    # The tool just provides a standardized wrapper pattern.
    template = f'''\
# Auto-generated analysis template
# Task: {task_description}
import numpy as np
import pandas as pd
import json

# ── Data loading ─────────────────────────────────────
# Replace with actual data or tool call results
data = {{}}

# ── Analysis ─────────────────────────────────────────
# TODO: Implement analysis for: {task_description}
results = {{}}

# ── Output ───────────────────────────────────────────
print(json.dumps(results, indent=2, default=str))
'''
    return json.dumps({"template": template, "task": task_description})


# ── Registry ─────────────────────────────────────────────────────────

CODE_TOOLS = [
    execute_python_code,
    generate_analysis_code,
]
