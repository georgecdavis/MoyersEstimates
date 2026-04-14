import logging
import os
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, jsonify, request, send_file

from config import APP_PASSWORD, MAX_UPLOAD_MB
from services.pdf_ingestion import rasterize_pdf, validate_pdf
from services.vision_extractor import extract_from_pages
from services.excel_builder import build_excel

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")

# ── In-memory job store ──────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=3)

ALLOWED_EXTENSIONS = {"pdf"}
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _job_update(job_id: str, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _check_password(req) -> bool:
    provided = (
        req.headers.get("X-App-Password")
        or req.args.get("password")
        or req.form.get("password")
        or (req.get_json(silent=True) or {}).get("password")
    )
    return provided == APP_PASSWORD


def _process_job(job_id: str, pdf_path: str, original_filename: str, work_dir: str):
    try:
        _job_update(job_id, status="processing", message="Rasterizing pages…", progress=5)

        pages_dir = os.path.join(work_dir, "pages")
        page_paths = rasterize_pdf(pdf_path, pages_dir)
        total_pages = len(page_paths)
        logger.info("Job %s: %d pages rasterized", job_id, total_pages)

        _job_update(job_id, message=f"Analyzing {total_pages} pages with AI…", progress=15)

        def on_progress(pages_done: int, total: int):
            pct = 15 + int((pages_done / total) * 70)
            _job_update(
                job_id,
                progress=pct,
                message=f"Analyzing page {pages_done} of {total}…"
            )

        metadata, line_items = extract_from_pages(page_paths, progress_callback=on_progress)
        logger.info("Job %s: extracted %d line items", job_id, len(line_items))

        _job_update(job_id, message="Building Excel workbook…", progress=88)

        # Derive output filename
        insured = metadata.get("insured_name", "").strip()
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in insured)
        safe_name = safe_name.replace(" ", "_") or "Estimate"
        output_filename = f"Moyers_{safe_name}_Estimate.xlsx"
        output_path = os.path.join(work_dir, output_filename)

        build_excel(metadata, line_items, output_path)

        _job_update(
            job_id,
            status="complete",
            message=f"Done — {len(line_items)} line items extracted.",
            progress=100,
            output_path=output_path,
            output_filename=output_filename,
            line_item_count=len(line_items),
        )
        logger.info("Job %s complete: %s", job_id, output_filename)

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        _job_update(job_id, status="error", message=f"Error: {e}", progress=0)
        shutil.rmtree(work_dir, ignore_errors=True)


# ── Endpoints ────────────────────────────────────────────────────────────────

@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/parse", methods=["POST"])
def parse():
    if not _check_password(request):
        return jsonify({"error": "Invalid password."}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted."}), 400

    raw = file.read()
    if len(raw) > MAX_BYTES:
        return jsonify({"error": f"File too large (max {MAX_UPLOAD_MB} MB)."}), 413

    job_id = str(uuid.uuid4())
    work_dir = tempfile.mkdtemp(prefix=f"moyers_{job_id}_")
    pdf_path = os.path.join(work_dir, "upload.pdf")

    with open(pdf_path, "wb") as f:
        f.write(raw)

    try:
        validate_pdf(pdf_path)
    except ValueError as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 400

    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "message": "Queued…",
            "output_path": None,
            "output_filename": None,
            "line_item_count": 0,
        }

    _executor.submit(_process_job, job_id, pdf_path, file.filename, work_dir)
    return jsonify({"job_id": job_id}), 202


@api_bp.route("/status/<job_id>")
def status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    return jsonify({
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "line_item_count": job.get("line_item_count", 0),
        "output_filename": job.get("output_filename"),
    })


@api_bp.route("/download/<job_id>")
def download(job_id: str):
    if not _check_password(request):
        return jsonify({"error": "Invalid password."}), 401

    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["status"] != "complete":
        return jsonify({"error": "File not ready yet."}), 409
    if not job.get("output_path") or not os.path.exists(job["output_path"]):
        return jsonify({"error": "Output file missing."}), 500

    return send_file(
        job["output_path"],
        as_attachment=True,
        download_name=job["output_filename"],
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
