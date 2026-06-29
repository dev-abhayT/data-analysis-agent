# Capability: File Upload and Profile

## What It Does

Accepts a CSV or Excel file upload, persists the file to local storage, computes a dataset profile (row count, column names, data types, null counts, and 3 sample values per column), and returns the profile plus 3 Gemini-generated starter questions tailored to the dataset's columns.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| `session_id` | UUID string | URL path parameter | Yes |
| `file` | Multipart file upload | HTTP request body (multipart/form-data) | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `dataset_id` | UUID string | JSON response body |
| `profile` | Object: `{row_count, column_count, columns: [{name, dtype, null_count, sample_values}]}` | JSON response body |
| `starter_questions` | Array of 3 strings | JSON response body |
| Dataset file | File bytes | Local filesystem at `data/uploads/{session_id}/{filename}` |
| `datasets` row | DB record | SQLite `datasets` table |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | Write file to `data/uploads/{session_id}/{filename}` | Return HTTP 500; do not create DB row |
| pandas | `read_csv` or `read_excel`, dtype inference, null counting, `.sample(3)` per column | Return HTTP 422 with parse error message |
| Gemini API | Single non-streaming call to generate 3 starter questions from column names and sample values | Return profile without starter questions (empty list); log warning with structlog |

## Business Rules

- Only `.csv`, `.xlsx`, and `.xls` file extensions are accepted; any other extension returns HTTP 400 with message `"Unsupported file type"`.
- Maximum file size is 100 MB; files above this limit return HTTP 413 with message `"File too large (max 100 MB)"`.
- Maximum row count is 1,000,000 rows; files exceeding this return HTTP 422 with message `"File too large (max 1,000,000 rows)"`.
- `session_id` must reference an existing `sessions` row; if not found, return HTTP 404.
- Multiple files may be uploaded to the same session (required for Phase 2 multi-file join); filenames within a session must be unique or overwrite the prior file.
- Sample values per column are drawn from the first non-null 3 values; if a column has fewer than 3 non-null values, fewer samples are returned.
- Profile JSON is stored verbatim in `datasets.profile_json` for later use by the query graph.
- Starter questions must reference actual column names from the dataset, not generic placeholders.

## Success Criteria

- [ ] Uploading a valid CSV returns HTTP 200 with `dataset_id`, `profile` containing accurate `row_count`, `column_count`, and per-column metadata, and exactly 3 `starter_questions`.
- [ ] Uploading a valid Excel `.xlsx` file returns the same response structure with correct data.
- [ ] Uploading a file larger than 100 MB returns HTTP 413.
- [ ] Uploading a file with an unsupported extension (e.g. `.json`) returns HTTP 400.
- [ ] The uploaded file exists on the local filesystem at the expected path after upload.
- [ ] A `datasets` row is created in SQLite with `profile_json` matching the returned `profile` object.
- [ ] Starter questions contain the actual column names from the uploaded dataset (not generic text).
- [ ] If Gemini is unreachable, the endpoint still returns HTTP 200 with the profile; `starter_questions` is `[]`.
