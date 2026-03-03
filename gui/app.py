#!/usr/bin/env python3
"""
extract-xiso WebUI — Flask backend
Serves the gorgeous Xbox-themed UI and wraps the extract-xiso CLI.
"""

from __future__ import annotations

import os
import sys
import json
import uuid
import shutil
import tempfile
import threading
import subprocess
import time
import queue
import zipfile
from pathlib import Path
from typing import Optional

# ── Auto-install dependencies if missing ──────────────────────────────────────
def _ensure_deps() -> None:
    missing = []
    for pkg in ("flask", "flask_cors", "werkzeug"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg.replace("_", "-"))
    if missing:
        print(f"[setup] Installing: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        )

_ensure_deps()

from flask import Flask, request, jsonify, Response, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ── Constants ─────────────────────────────────────────────────────────────────
VERSION = "2.7.1"
PORT = 7860
MAX_CONTENT_LENGTH = 8 * 1024 * 1024 * 1024  # 8 GB
TEMP_DIR = Path(tempfile.gettempdir()) / "extract-xiso-gui"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
CLEANUP_AGE_SECONDS = 3600  # 1 hour

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
CORS(app)

# ── Job tracking ──────────────────────────────────────────────────────────────
# jobs[job_id] = {"status": "running"|"done"|"error", "queue": Queue, "result": ...}
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


def new_job() -> tuple[str, queue.Queue]:
    job_id = str(uuid.uuid4())
    q: queue.Queue = queue.Queue()
    with jobs_lock:
        jobs[job_id] = {"status": "running", "queue": q, "result": None}
    return job_id, q


def finish_job(job_id: str, result: dict, error: bool = False) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["status"] = "error" if error else "done"
            jobs[job_id]["result"] = result
            # Send sentinel
            jobs[job_id]["queue"].put(None)


# ── Binary discovery ──────────────────────────────────────────────────────────
def find_binary() -> Optional[str]:
    """Find the extract-xiso binary."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    candidates = [
        repo_root / "build" / "extract-xiso",
        repo_root / "build" / "extract-xiso.exe",
        repo_root / "extract-xiso",
        repo_root / "extract-xiso.exe",
        Path("build") / "extract-xiso",
        Path("build") / "extract-xiso.exe",
        Path("extract-xiso"),
    ]
    for c in candidates:
        if c.exists() and os.access(str(c), os.X_OK):
            return str(c)

    # Check system PATH
    found = shutil.which("extract-xiso")
    if found:
        return found

    return None


BINARY = find_binary()


# ── Temp file cleanup ─────────────────────────────────────────────────────────
def cleanup_old_temp_files() -> None:
    """Remove temp files older than CLEANUP_AGE_SECONDS."""
    now = time.time()
    for item in TEMP_DIR.iterdir():
        try:
            if now - item.stat().st_mtime > CLEANUP_AGE_SECONDS:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
        except Exception:
            pass


def cleanup_scheduler() -> None:
    while True:
        time.sleep(600)  # every 10 min
        cleanup_old_temp_files()


threading.Thread(target=cleanup_scheduler, daemon=True).start()


# ── Helpers ───────────────────────────────────────────────────────────────────
def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def sse_event(data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data)
    return f"data: {data}\n\n"


def run_command(
    cmd: list[str],
    job_id: str,
    cwd: Optional[str] = None,
) -> tuple[int, list[str]]:
    """Run a command, streaming output lines to the job queue."""
    q = jobs[job_id]["queue"]
    lines: list[str] = []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd,
        )
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.rstrip()
            lines.append(line)
            q.put({"type": "log", "text": line})

        proc.wait()
        return proc.returncode, lines
    except FileNotFoundError:
        msg = f"Binary not found: {cmd[0]}"
        q.put({"type": "log", "text": msg})
        return 1, [msg]
    except Exception as exc:
        msg = str(exc)
        q.put({"type": "log", "text": msg})
        return 1, [msg]


def save_upload(file_storage, suffix: str = "") -> Path:
    """Save a werkzeug FileStorage to temp dir. Returns the path."""
    name = secure_filename(file_storage.filename or f"upload{suffix}")
    dest = TEMP_DIR / f"{uuid.uuid4()}_{name}"
    file_storage.save(str(dest))
    return dest


def parse_list_output(lines: list[str]) -> list[dict]:
    """Parse extract-xiso -l output into a list of file entries."""
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # typical format: "   12345  /path/to/file.txt"
        # or just: "/path/to/file.txt"
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            size = int(parts[0])
            path = parts[1].lstrip("/")
            entries.append({"path": path, "size": size, "size_human": human_size(size)})
        elif len(parts) == 1:
            entries.append({"path": parts[0].lstrip("/"), "size": 0, "size_human": ""})
        else:
            # Could be a message line — skip
            pass
    return entries


def build_file_tree(entries: list[dict]) -> list[dict]:
    """Convert flat file list to nested tree structure."""
    root: list[dict] = []
    nodes: dict[str, dict] = {}

    for entry in entries:
        path = entry["path"].replace("\\", "/")
        parts = [p for p in path.split("/") if p]
        current = root
        current_path = ""

        for i, part in enumerate(parts):
            current_path = current_path + "/" + part if current_path else part
            if current_path not in nodes:
                is_file = i == len(parts) - 1
                node: dict = {
                    "name": part,
                    "path": current_path,
                    "is_file": is_file,
                    "children": [],
                    "size": entry["size"] if is_file else 0,
                    "size_human": entry["size_human"] if is_file else "",
                }
                nodes[current_path] = node
                current.append(node)
            current = nodes[current_path]["children"]

    return root


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    static_path = Path(__file__).parent / "static" / "index.html"
    if static_path.exists():
        return send_from_directory(str(static_path.parent), "index.html")
    return "<h1>index.html not found</h1>", 404


@app.route("/api/status")
def api_status():
    return jsonify({
        "version": VERSION,
        "binary": BINARY or "not found",
        "binary_ok": BINARY is not None,
        "temp_dir": str(TEMP_DIR),
    })


# ── SSE progress stream ───────────────────────────────────────────────────────

@app.route("/api/progress/<job_id>")
def api_progress(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404

    def generate():
        q = job["queue"]
        while True:
            try:
                msg = q.get(timeout=30)
                if msg is None:
                    # Job finished
                    with jobs_lock:
                        j = jobs.get(job_id, {})
                    result = j.get("result") or {}
                    status = j.get("status", "done")
                    yield sse_event({"type": "done", "status": status, "result": result})
                    break
                yield sse_event(msg)
            except queue.Empty:
                yield sse_event({"type": "ping"})

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Extract ───────────────────────────────────────────────────────────────────

@app.route("/api/extract", methods=["POST"])
def api_extract():
    if not BINARY:
        return jsonify({"error": "extract-xiso binary not found. Run ./install.sh first."}), 500

    if "iso" not in request.files:
        return jsonify({"error": "No ISO file uploaded"}), 400

    iso_file = request.files["iso"]
    iso_path = save_upload(iso_file, suffix=".iso")
    out_dir = TEMP_DIR / f"extract_{uuid.uuid4()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    job_id, _ = new_job()

    def worker():
        cmd = [BINARY, str(iso_path), "-d", str(out_dir)]
        rc, lines = run_command(cmd, job_id)
        # Gather file list from output dir
        extracted = []
        total_size = 0
        for f in out_dir.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(out_dir)).replace("\\", "/")
                sz = f.stat().st_size
                total_size += sz
                extracted.append({"path": rel, "size": sz, "size_human": human_size(sz)})

        if rc == 0:
            finish_job(job_id, {
                "success": True,
                "files": extracted,
                "tree": build_file_tree(extracted),
                "total_files": len(extracted),
                "total_size": human_size(total_size),
                "output_dir": str(out_dir),
            })
        else:
            finish_job(job_id, {
                "success": False,
                "error": "extract-xiso returned non-zero exit code",
                "files": extracted,
            }, error=True)

        # cleanup ISO upload
        iso_path.unlink(missing_ok=True)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── Create ────────────────────────────────────────────────────────────────────

@app.route("/api/create", methods=["POST"])
def api_create():
    if not BINARY:
        return jsonify({"error": "extract-xiso binary not found. Run ./install.sh first."}), 500

    src_dir: Optional[Path] = None

    if "folder_zip" in request.files:
        zip_file = request.files["folder_zip"]
        zip_path = save_upload(zip_file, suffix=".zip")
        extract_to = TEMP_DIR / f"create_src_{uuid.uuid4()}"
        extract_to.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(str(zip_path)) as zf:
                zf.extractall(str(extract_to))
        except Exception as exc:
            return jsonify({"error": f"Failed to unzip: {exc}"}), 400
        finally:
            zip_path.unlink(missing_ok=True)

        # If zip has single top-level dir, use it
        children = list(extract_to.iterdir())
        if len(children) == 1 and children[0].is_dir():
            src_dir = children[0]
        else:
            src_dir = extract_to

    elif "folder_path" in request.form:
        p = Path(request.form["folder_path"])
        if not p.exists() or not p.is_dir():
            return jsonify({"error": f"Path not found: {p}"}), 400
        src_dir = p
    else:
        return jsonify({"error": "Provide folder_zip file or folder_path form field"}), 400

    out_iso = TEMP_DIR / f"{secure_filename(src_dir.name or 'output')}.iso"
    job_id, _ = new_job()

    def worker():
        cmd = [BINARY, "-c", str(src_dir), str(out_iso)]
        rc, lines = run_command(cmd, job_id)
        if rc == 0 and out_iso.exists():
            sz = out_iso.stat().st_size
            finish_job(job_id, {
                "success": True,
                "iso_name": out_iso.name,
                "iso_size": human_size(sz),
                "download_url": f"/api/download/{out_iso.name}",
            })
        else:
            finish_job(job_id, {
                "success": False,
                "error": "create failed",
            }, error=True)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── List ──────────────────────────────────────────────────────────────────────

@app.route("/api/list", methods=["POST"])
def api_list():
    if not BINARY:
        return jsonify({"error": "extract-xiso binary not found. Run ./install.sh first."}), 500

    if "iso" not in request.files:
        return jsonify({"error": "No ISO file uploaded"}), 400

    iso_file = request.files["iso"]
    iso_path = save_upload(iso_file, suffix=".iso")
    job_id, _ = new_job()

    def worker():
        cmd = [BINARY, "-l", str(iso_path)]
        rc, lines = run_command(cmd, job_id)
        entries = parse_list_output(lines)
        total_size = sum(e["size"] for e in entries)
        if rc == 0:
            finish_job(job_id, {
                "success": True,
                "files": entries,
                "tree": build_file_tree(entries),
                "total_files": len(entries),
                "total_size": human_size(total_size),
            })
        else:
            finish_job(job_id, {
                "success": False,
                "error": "list failed",
                "files": entries,
                "tree": build_file_tree(entries),
                "total_files": len(entries),
                "total_size": human_size(total_size),
            }, error=True)
        iso_path.unlink(missing_ok=True)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── Rewrite ───────────────────────────────────────────────────────────────────

@app.route("/api/rewrite", methods=["POST"])
def api_rewrite():
    if not BINARY:
        return jsonify({"error": "extract-xiso binary not found. Run ./install.sh first."}), 500

    if "iso" not in request.files:
        return jsonify({"error": "No ISO file uploaded"}), 400

    iso_file = request.files["iso"]
    iso_path = save_upload(iso_file, suffix=".iso")
    out_dir = TEMP_DIR / f"rewrite_{uuid.uuid4()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    delete_original = request.form.get("delete_original", "false").lower() == "true"
    job_id, _ = new_job()

    def worker():
        cmd = [BINARY, "-r", str(iso_path), "-d", str(out_dir)]
        if delete_original:
            cmd.append("-D")
        rc, lines = run_command(cmd, job_id)

        # Find rewritten ISO in out_dir
        rewritten = list(out_dir.glob("*.iso"))
        if rc == 0 and rewritten:
            iso_out = rewritten[0]
            sz = iso_out.stat().st_size
            finish_job(job_id, {
                "success": True,
                "iso_name": iso_out.name,
                "iso_size": human_size(sz),
                "download_url": f"/api/download/{iso_out.name}",
            })
        elif rc == 0:
            # Rewrite may have modified in-place
            if iso_path.exists():
                sz = iso_path.stat().st_size
                finish_job(job_id, {
                    "success": True,
                    "iso_name": iso_path.name,
                    "iso_size": human_size(sz),
                    "download_url": f"/api/download/{iso_path.name}",
                })
            else:
                finish_job(job_id, {"success": True, "message": "Rewrite complete"})
        else:
            finish_job(job_id, {"success": False, "error": "rewrite failed"}, error=True)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── Download ──────────────────────────────────────────────────────────────────

@app.route("/api/download/<filename>")
def api_download(filename: str):
    safe = secure_filename(filename)
    # Search temp dir (and subdirs one level deep)
    candidates = list(TEMP_DIR.glob(f"*/{safe}")) + [TEMP_DIR / safe]
    for c in candidates:
        if c.exists() and c.is_file():
            return send_file(str(c), as_attachment=True, download_name=safe)
    return jsonify({"error": "file not found"}), 404


# ── Main ──────────────────────────────────────────────────────────────────────

def open_browser() -> None:
    import webbrowser
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    if BINARY:
        print(f"[ok] Binary: {BINARY}")
    else:
        print("[warn] extract-xiso binary not found — run ./install.sh to build it")
    print(f"[ok] Temp dir: {TEMP_DIR}")
    print(f"\n  Starting extract-xiso WebUI at http://localhost:{PORT}\n")

    threading.Thread(target=open_browser, daemon=True).start()

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
