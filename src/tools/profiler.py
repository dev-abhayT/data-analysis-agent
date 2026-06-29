import json
import pandas as pd
from pathlib import Path


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
            df = pd.read_csv(file_path)
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
        # Convert numpy types to Python primitives
        samples = [s.item() if hasattr(s, "item") else s for s in samples]
        sample_values[col] = [str(s) for s in samples]

    return {
        "row_count": len(df),
        "column_names": list(df.columns),
        "column_types": column_types,
        "null_counts": null_counts,
        "sample_values": sample_values,
    }
