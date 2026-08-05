from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from logs.ruleset import BUILDING_RATING_FACTORS, extract_rulesets, fields_payload, is_ruleset_log

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
INDEX_FILE = WEB_DIR / "templates" / "index.html"

app = FastAPI(title="LOGS Extract", version="0.5.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/building-factors")
def building_factor_names() -> dict[str, list[str]]:
    return {"fields": list(BUILDING_RATING_FACTORS)}


@app.post("/api/extract")
async def extract_upload(
    file: UploadFile = File(...),
    ruleset: str = Form(default="Building"),
    mode: str = Form(default="building-factors"),
    fields: str = Form(default=""),
) -> dict:
    raw_name = file.filename or "upload.log"
    suffix = Path(raw_name).suffix or ".log"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    with tempfile.NamedTemporaryFile(prefix="logs-extract-", suffix=suffix, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)

    try:
        text = temp_path.read_text(encoding="utf-8", errors="replace")
        if not is_ruleset_log(text):
            raise HTTPException(
                status_code=400,
                detail="File does not look like a UW ruleset execution log.",
            )

        ruleset_name = ruleset.strip() or None
        extract = extract_rulesets(str(temp_path), ruleset_name=ruleset_name)
        if not extract.rulesets:
            raise HTTPException(
                status_code=404,
                detail=f"No ruleset named {ruleset!r} found in the uploaded log.",
            )

        normalized_mode = mode.strip().lower()
        if normalized_mode in {"building-factors", "factors"}:
            field_names = list(BUILDING_RATING_FACTORS)
            payload = fields_payload(extract, field_names)
            return {
                "mode": "building-factors",
                "filename": raw_name,
                "header": payload["header"],
                "requested_fields": payload["requested_fields"],
                "rulesets": [
                    {
                        "name": item["name"],
                        "precondition": item["precondition"],
                        "fields": item["fields"],
                        "field_details": item["field_details"],
                    }
                    for item in payload["rulesets"]
                ],
            }

        if normalized_mode == "fields":
            field_names = [part.strip() for part in fields.split(",") if part.strip()]
            if not field_names:
                raise HTTPException(
                    status_code=400,
                    detail="Provide a comma-separated fields list when mode=fields.",
                )
            payload = fields_payload(extract, field_names)
            return {
                "mode": "fields",
                "filename": raw_name,
                "header": payload["header"],
                "requested_fields": payload["requested_fields"],
                "rulesets": payload["rulesets"],
            }

        if normalized_mode == "full":
            return {
                "mode": "full",
                "filename": raw_name,
                "header": extract.to_dict()["header"],
                "rulesets": extract.to_dict()["rulesets"],
            }

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported mode {mode!r}. Use building-factors, fields, or full.",
        )
    finally:
        temp_path.unlink(missing_ok=True)


def create_app() -> FastAPI:
    return app
