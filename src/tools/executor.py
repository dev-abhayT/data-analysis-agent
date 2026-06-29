import ast
from typing import Any
import numpy as np
import pandas as pd

# Forbidden names that must never appear in generated code
_FORBIDDEN = {
    "subprocess", "os", "sys", "open", "eval", "exec", "__import__",
    "compile", "globals", "locals", "vars", "dir", "getattr", "setattr",
    "delattr", "input", "print",
}

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "format": format,
    "frozenset": frozenset, "hasattr": hasattr, "int": int,
    "isinstance": isinstance, "issubclass": issubclass, "iter": iter,
    "len": len, "list": list, "map": map, "max": max, "min": min,
    "next": next, "range": range, "reversed": reversed, "round": round,
    "set": set, "slice": slice, "sorted": sorted, "str": str, "sum": sum,
    "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
}


def _check_forbidden(code: str) -> None:
    """Raise ValueError if code references forbidden names."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Syntax error in generated code: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN:
            raise ValueError(f"Forbidden name in generated code: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN:
            raise ValueError(f"Forbidden attribute in generated code: {node.attr}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name in _FORBIDDEN:
                    raise ValueError(f"Forbidden import: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _FORBIDDEN:
                raise ValueError(f"Forbidden import from: {node.module}")


def execute_pandas_code(
    code: str,
    dataframes: dict[str, pd.DataFrame],
    *,
    max_rows: int = 100,
) -> dict[str, Any]:
    """
    Execute LLM-generated pandas code in a restricted scope.

    The code should assign its result to a variable named `result`.
    DataFrames are available as variables named by their key in `dataframes`.

    Returns:
        {"columns": [...], "rows": [[...], ...]}  on success
        {"error": "..."}  on failure
    """
    _check_forbidden(code)

    # Build execution namespace
    namespace: dict[str, Any] = {"pd": pd, "__builtins__": _SAFE_BUILTINS}
    namespace.update(dataframes)

    try:
        exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    result = namespace.get("result")
    if result is None:
        # Try to find any DataFrame or Series in namespace that wasn't there before
        for k, v in namespace.items():
            if k.startswith("_") or k == "pd" or k in dataframes or k in _SAFE_BUILTINS:
                continue
            if isinstance(v, (pd.DataFrame, pd.Series)):
                result = v
                break

    if result is None:
        return {
            "error": (
                "Generated code did not assign a result. "
                "Assign your final result to a variable named 'result'."
            )
        }

    if isinstance(result, pd.Series):
        result = result.reset_index()

    # numpy arrays and pandas Index (e.g. df.columns) → treat as a Series
    if isinstance(result, (np.ndarray, pd.Index)):
        result = pd.Series(result, name="value").reset_index(drop=True).to_frame()

    if isinstance(result, pd.DataFrame):
        limited = result.head(max_rows)
        columns = list(limited.columns)
        rows = []
        for _, row in limited.iterrows():
            rows.append([_serialize(v) for v in row.values])
        return {"columns": columns, "rows": rows}

    # Scalar result
    return {"columns": ["result"], "rows": [[_serialize(result)]]}


def _serialize(val: Any) -> Any:
    """Convert numpy/pandas types to JSON-serializable Python types."""
    # numpy scalar types (int64, float64, bool_, etc.) — safe to call .item()
    if isinstance(val, np.generic):
        return val.item()
    # numpy arrays or pandas Index — should not reach here after the DataFrame path,
    # but guard anyway by converting to list
    if isinstance(val, (np.ndarray, pd.Index)):
        return val.tolist()
    try:
        if not isinstance(val, (list, dict, str, bool)) and pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return val
