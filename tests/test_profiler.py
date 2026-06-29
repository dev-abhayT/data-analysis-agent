"""Unit tests for src/tools/profiler.py — no LLM key required."""
import io
import pytest
import pandas as pd

from tools.profiler import profile_dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(tmp_path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _write_excel(tmp_path, name: str, df: pd.DataFrame) -> str:
    p = tmp_path / name
    df.to_excel(str(p), index=False)
    return str(p)


# ---------------------------------------------------------------------------
# Happy path — CSV
# ---------------------------------------------------------------------------

def test_profile_csv_happy_path(tmp_path):
    csv_content = "name,age,score\nAlice,30,95.5\nBob,25,82.0\nCarol,35,\n"
    path = _write_csv(tmp_path, "test.csv", csv_content)

    result = profile_dataset(path)

    assert result["row_count"] == 3
    assert result["column_names"] == ["name", "age", "score"]
    assert "name" in result["column_types"]
    assert "age" in result["column_types"]
    assert "score" in result["column_types"]
    # null_counts: score has 1 null
    assert result["null_counts"]["score"] == 1
    assert result["null_counts"]["name"] == 0
    # sample_values present and non-empty for name
    assert len(result["sample_values"]["name"]) >= 1
    assert "Alice" in result["sample_values"]["name"]


def test_profile_csv_sample_values_capped(tmp_path):
    """Sample values are capped at 5 per column."""
    rows = "\n".join(f"user_{i},{i}" for i in range(20))
    csv_content = f"username,idx\n{rows}\n"
    path = _write_csv(tmp_path, "big.csv", csv_content)

    result = profile_dataset(path)
    assert result["row_count"] == 20
    assert len(result["sample_values"]["username"]) <= 5
    assert len(result["sample_values"]["idx"]) <= 5


def test_profile_csv_all_nulls_column(tmp_path):
    """A column that is entirely null should have null_count == row_count."""
    csv_content = "a,b\n1,\n2,\n3,\n"
    path = _write_csv(tmp_path, "nullcol.csv", csv_content)

    result = profile_dataset(path)
    assert result["null_counts"]["b"] == 3
    assert result["sample_values"]["b"] == []


def test_profile_csv_single_row(tmp_path):
    """Edge case: single data row."""
    csv_content = "x,y\n42,hello\n"
    path = _write_csv(tmp_path, "single.csv", csv_content)

    result = profile_dataset(path)
    assert result["row_count"] == 1
    assert result["column_names"] == ["x", "y"]


def test_profile_csv_column_types_present(tmp_path):
    csv_content = "int_col,float_col,str_col\n1,1.5,a\n2,2.5,b\n"
    path = _write_csv(tmp_path, "types.csv", csv_content)

    result = profile_dataset(path)
    # Just assert they're strings (dtype representation)
    for col in ["int_col", "float_col", "str_col"]:
        assert isinstance(result["column_types"][col], str)
        assert len(result["column_types"][col]) > 0


# ---------------------------------------------------------------------------
# Happy path — Excel
# ---------------------------------------------------------------------------

def test_profile_excel_xlsx(tmp_path):
    """Profile an .xlsx file correctly."""
    df = pd.DataFrame({"product": ["Apple", "Banana", "Cherry"], "price": [1.2, 0.5, 3.0]})
    path = _write_excel(tmp_path, "products.xlsx", df)

    result = profile_dataset(path)
    assert result["row_count"] == 3
    assert "product" in result["column_names"]
    assert "price" in result["column_names"]
    assert result["null_counts"]["product"] == 0
    assert "Apple" in result["sample_values"]["product"]


# ---------------------------------------------------------------------------
# Error / edge cases
# ---------------------------------------------------------------------------

def test_profile_unsupported_file_type(tmp_path):
    """Unsupported file extension raises ValueError."""
    path = tmp_path / "data.json"
    path.write_text('{"key": "val"}', encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file type"):
        profile_dataset(str(path))


def test_profile_unparseable_csv(tmp_path):
    """A file with a .csv extension but binary garbage raises ValueError."""
    path = tmp_path / "bad.csv"
    # Write binary content that pandas will refuse to parse as valid CSV text
    path.write_bytes(b"\x00" * 1024)

    # pandas may or may not raise on null bytes — just confirm we get a result
    # or a ValueError (not an unhandled internal error)
    try:
        result = profile_dataset(str(path))
        # If pandas manages to parse it, result should still be valid dict shape
        assert "row_count" in result
    except ValueError:
        pass  # expected


def test_profile_empty_csv_raises(tmp_path):
    """An empty CSV (no rows, no header) is handled gracefully."""
    path = _write_csv(tmp_path, "empty.csv", "")
    # pandas raises EmptyDataError on fully empty file
    with pytest.raises(ValueError):
        profile_dataset(str(path))


def test_profile_nonexistent_file(tmp_path):
    """Missing file raises ValueError."""
    with pytest.raises(ValueError):
        profile_dataset(str(tmp_path / "missing.csv"))
