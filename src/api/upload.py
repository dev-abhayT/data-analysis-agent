import json
import asyncio
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import Session as SessionModel, Dataset
from tools.profiler import profile_dataset
from config.settings import get_settings

log = structlog.get_logger()

router = APIRouter(prefix="/api")


@router.post("/sessions/{session_id}/files")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> dict:
    settings = get_settings()

    # Check session exists
    session = db.get(SessionModel, session_id)
    if session is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    # Check file count limit
    existing_count = db.query(Dataset).filter(Dataset.session_id == session_id).count()
    if existing_count >= 3:
        raise api_error("TOO_MANY_FILES", "Session already has 3 files (max)", 400)

    # Validate file type
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise api_error(
            "UNSUPPORTED_TYPE",
            f"Unsupported file type '{suffix}'. Upload a .csv or .xlsx file.",
            400,
        )

    # Read file (check size)
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise api_error(
            "FILE_TOO_LARGE",
            f"File too large — max {settings.max_upload_bytes // 1048576} MB",
            400,
        )
    if len(content) == 0:
        raise api_error("EMPTY_FILE", "Uploaded file is empty", 422)

    # Save to filesystem
    upload_dir = Path(settings.upload_dir) / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    file_path.write_bytes(content)

    # Profile the file
    try:
        profile = await asyncio.to_thread(profile_dataset, str(file_path))
    except ValueError as exc:
        raise api_error("PARSE_ERROR", str(exc), 422)

    # Generate starter questions via Gemini
    try:
        starter_questions = await asyncio.to_thread(_generate_starter_questions, profile)
    except Exception as exc:
        log.error("starter_questions_failed", error=str(exc))
        starter_questions = []

    # Persist dataset row
    dataset = Dataset(
        session_id=session_id,
        filename=filename,
        file_path=str(file_path),
        row_count=profile["row_count"],
        column_names_json=json.dumps(profile["column_names"]),
        column_types_json=json.dumps(profile["column_types"]),
        null_counts_json=json.dumps(profile["null_counts"]),
        sample_values_json=json.dumps(profile["sample_values"]),
        starter_questions_json=json.dumps(starter_questions),
    )
    db.add(dataset)
    db.flush()

    return ok({
        "dataset_id": dataset.id,
        "filename": filename,
        "row_count": profile["row_count"],
        "column_names": profile["column_names"],
        "column_types": profile["column_types"],
        "null_counts": profile["null_counts"],
        "sample_values": profile["sample_values"],
        "starter_questions": starter_questions,
    })


def _generate_starter_questions(profile: dict) -> list[str]:
    """Call Gemini synchronously to generate 3 starter questions."""
    from llm.client import LLMClient

    columns_desc = "\n".join(
        f"- {col} ({profile['column_types'].get(col, '?')}): "
        f"samples {profile['sample_values'].get(col, [])[:3]}"
        for col in profile["column_names"][:20]  # cap at 20 columns
    )
    prompt = (
        f"You are analyzing a dataset with {profile['row_count']} rows.\n\n"
        f"Columns:\n{columns_desc}\n\n"
        f"Generate exactly 3 concise, specific starter questions that a non-technical user "
        f"would ask about this dataset. "
        f"The questions should reference the actual column names and be answerable with pandas aggregations. "
        f'Return a JSON array of 3 strings. '
        f'Example: ["What is the total X by Y?", "Which Z has the highest W?", "How many rows have missing V?"] '
        f"Return only the JSON array, no other text."
    )

    client = LLMClient()
    result = client.call_json(prompt)
    if isinstance(result, list):
        return result[:3]
    if isinstance(result, dict) and "questions" in result:
        return result["questions"][:3]
    return []
