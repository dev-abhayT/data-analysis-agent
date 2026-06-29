import numpy as np
import pandas as pd
from pathlib import Path


def _read_csv_robust(file_path: str) -> pd.DataFrame:
    """Try multiple encodings and fallback options to parse a CSV file."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    last_exc: Exception = RuntimeError("unknown error")
    for encoding in encodings:
        for engine in ("c", "python"):
            try:
                kwargs: dict = {
                    "encoding": encoding,
                    "on_bad_lines": "skip",
                    "engine": engine,
                }
                if engine == "python":
                    # auto-detect separator when the C engine failed
                    kwargs["sep"] = None
                    kwargs["encoding_errors"] = "replace"
                return pd.read_csv(file_path, **kwargs)
            except UnicodeDecodeError:
                last_exc = UnicodeDecodeError("utf-8", b"", 0, 1, "bad encoding")
                break  # try next encoding
            except Exception as exc:
                last_exc = exc
    raise ValueError(
        f"Could not parse this CSV file — check that it is valid and not corrupted. "
        f"Detail: {last_exc}"
    )


def profile_dataset(file_path: str) -> dict:
    """
    Returns a profile dict:
    {
      "row_count": int,
      "column_names": [str, ...],
      "column_types": {col: dtype_str, ...},
      "null_counts": {col: int, ...},
      "sample_values": {col: [val, ...], ...}  # up to 5 non-null samples per column
    }
    Raises ValueError on unreadable file.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            df = _read_csv_robust(file_path)
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Cannot parse file: {exc}") from exc

    column_types = {col: str(df[col].dtype) for col in df.columns}
    null_counts = {col: int(df[col].isna().sum()) for col in df.columns}
    sample_values = {}
    for col in df.columns:
        non_null = df[col].dropna()
        samples = non_null.head(5).tolist()
        # Convert numpy scalar types to Python primitives safely
        samples = [s.item() if isinstance(s, np.generic) else s for s in samples]
        sample_values[col] = [str(s) for s in samples]

    return {
        "row_count": len(df),
        "column_names": list(df.columns),
        "column_types": column_types,
        "null_counts": null_counts,
        "sample_values": sample_values,
    }
