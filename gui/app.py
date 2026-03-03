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
    if not missing:
        return
    # Try pip install only if pip is available
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        _bail_missing_deps(missing, pip_available=False)
        return
    print(f"[setup] Installing: {', '.join(missing)}")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout or "pip install failed")
        _bail_missing_deps(missing, pip_available=True)

def _bail_missing_deps(missing: list[str], pip_available: bool) -> None:
    req = Path(__file__).resolve().parent / "requirements.txt"
    print("\n[ERROR] Missing Python dependencies:", ", ".join(missing))
    print("\nInstall them manually:")
    if req.exists():
        print(f"  pip install -r {req}")
    else:
        print("  pip install flask flask-cors werkzeug")
    if not pip_available:
        print("\nIf pip is not installed (e.g. Ubuntu/WSL):")
        print("  sudo apt-get update && sudo apt-get install -y python3-pip")
        print("  pip install -r gui/requirements.txt")
    print()
    sys.exit(1)

_ensure_deps()

from flask import Flask, request, jsonify, Response, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ── Constants ─────────────────────────────────────────────────────────────────
VERSION = "2.8.1"
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
        repo_root / "build" / "Release" / "extract-xiso.exe",
        repo_root / "build" / "Debug" / "extract-xiso.exe",
        repo_root / "extract-xiso",
        repo_root / "extract-xiso.exe",
        Path("build") / "extract-xiso",
        Path("build") / "extract-xiso.exe",
        Path("extract-xiso"),
    ]
    for c in candidates:
        if c.exists() and os.access(str(c), os.X_OK):
            return str(c)

    found = shutil.which("extract-xiso")
    if found:
        return found

    return None


def find_xdvdfs() -> Optional[str]:
    """Find the xdvdfs binary."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    candidates = [
        repo_root / "bin" / "xdvdfs",
        repo_root / "bin" / "xdvdfs.exe",
        Path.home() / ".cargo" / "bin" / "xdvdfs",
        Path.home() / ".cargo" / "bin" / "xdvdfs.exe",
    ]
    for c in candidates:
        if c.exists() and os.access(str(c), os.X_OK):
            return str(c)

    found = shutil.which("xdvdfs")
    if found:
        return found

    return None


def find_xgdtool() -> Optional[str]:
    """Find the XGDTool binary."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    candidates = [
        repo_root / "bin" / "XGDTool",
        repo_root / "bin" / "XGDTool.exe",
        repo_root / "bin" / "xgdtool",
    ]
    for c in candidates:
        if c.exists() and os.access(str(c), os.X_OK):
            return str(c)

    found = shutil.which("XGDTool") or shutil.which("xgdtool")
    if found:
        return found

    return None


BINARY = find_binary()
XDVDFS_BIN = find_xdvdfs()
XGDTOOL_BIN = find_xgdtool()


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


# ── XBE media patch ───────────────────────────────────────────────────────────

def patch_xbe(filepath: str) -> tuple[int, int]:
    """Apply media patch to an XBE file. Returns (old_flags, new_flags)."""
    with open(filepath, 'r+b') as f:
        magic = f.read(4)
        if magic != b'XBEH':
            raise ValueError("Not a valid XBE file (missing XBEH magic)")
        # Media type flags live at offset 0x118 in the XBE certificate
        f.seek(0x118)
        media_flags = int.from_bytes(f.read(4), 'little')
        new_flags = media_flags | 0x08
        f.seek(0x118)
        f.write(new_flags.to_bytes(4, 'little'))
    return media_flags, new_flags


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

    skip_sysupdate = request.form.get("skip_sysupdate", "false").lower() == "true"
    job_id, _ = new_job()

    def worker():
        cmd = [BINARY, str(iso_path), "-d", str(out_dir)]
        if skip_sysupdate:
            cmd.append("-s")
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

    output_name = request.form.get("output_name", "").strip()
    if not output_name:
        output_name = f"{src_dir.name or 'output'}.iso"
    elif not output_name.lower().endswith(".iso"):
        output_name = f"{output_name}.iso"
    out_iso = TEMP_DIR / secure_filename(output_name)
    no_patch = request.form.get("no_patch", "false").lower() == "true"
    job_id, _ = new_job()

    def worker():
        cmd = [BINARY, "-c", str(src_dir), str(out_iso)]
        if no_patch:
            cmd.insert(1, "-m")
        rc, lines = run_command(cmd, job_id)
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
    skip_sysupdate = request.form.get("skip_sysupdate", "false").lower() == "true"
    job_id, _ = new_job()

    def worker():
        cmd = [BINARY, "-r", str(iso_path), "-d", str(out_dir)]
        if delete_original:
            cmd.append("-D")
        if skip_sysupdate:
            cmd.append("-s")
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


# ── Tools availability ────────────────────────────────────────────────────────

@app.route("/api/tools")
def api_tools():
    return jsonify({
        "extract_xiso": BINARY is not None,
        "xdvdfs": XDVDFS_BIN is not None,
        "xgdtool": XGDTOOL_BIN is not None,
    })


# ── XGDTool format list ───────────────────────────────────────────────────────

@app.route("/api/xgdtool/formats")
def api_xgdtool_formats():
    return jsonify({
        "formats": [
            {"id": "xiso",    "name": "XISO",    "emoji": "🎮", "desc": "Standard Xbox ISO — works everywhere"},
            {"id": "cci",     "name": "CCI",     "emoji": "💿", "desc": "Compressed, great for OG Xbox"},
            {"id": "cso",     "name": "CSO",     "emoji": "💨", "desc": "Smallest size, for Project Stellar"},
            {"id": "god",     "name": "GoD",     "emoji": "🗂",  "desc": "Games on Demand format"},
            {"id": "zar",     "name": "ZAR",     "emoji": "📦", "desc": "Archive format"},
            {"id": "extract", "name": "Extract", "emoji": "📁", "desc": "Extract files from disc"},
        ]
    })


# ── Format conversion (XGDTool) ───────────────────────────────────────────────

@app.route("/api/convert", methods=["POST"])
def api_convert():
    if not XGDTOOL_BIN:
        return jsonify({"error": "XGDTool not found. Run ./install.sh first."}), 500

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    valid_formats = {"xiso", "cci", "cso", "god", "zar", "extract"}
    output_format = request.form.get("output_format", "xiso")
    if output_format not in valid_formats:
        return jsonify({"error": f"Invalid output format: {output_format}"}), 400

    scrub   = request.form.get("scrub", "none")
    target  = request.form.get("target", "").strip()

    img_path = save_upload(request.files["file"])
    out_dir  = TEMP_DIR / f"convert_{uuid.uuid4()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    job_id, _ = new_job()

    def worker():
        try:
            cmd = [XGDTOOL_BIN, f"--{output_format}"]
            if scrub == "partial":
                cmd.append("--scrub")
            elif scrub == "full":
                cmd.append("--reauthor")
            if target:
                cmd.extend(["--target", target])
            cmd.extend([str(img_path), str(out_dir)])

            rc, _ = run_command(cmd, job_id)
            out_files = [f for f in out_dir.rglob("*") if f.is_file()]

            if rc == 0 and out_files:
                if len(out_files) == 1:
                    out_file = out_files[0]
                    sz = out_file.stat().st_size
                    finish_job(job_id, {
                        "success": True,
                        "download_url": f"/api/download/{out_file.name}",
                        "filename": out_file.name,
                        "size": human_size(sz),
                    })
                else:
                    # Multiple files — zip them
                    zip_name = f"convert_{uuid.uuid4()}.zip"
                    zip_path = TEMP_DIR / zip_name
                    with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
                        for f in out_files:
                            zf.write(str(f), f.relative_to(out_dir))
                    sz = zip_path.stat().st_size
                    finish_job(job_id, {
                        "success": True,
                        "download_url": f"/api/download/{zip_name}",
                        "filename": zip_name,
                        "size": human_size(sz),
                    })
            else:
                finish_job(job_id, {"success": False, "error": "XGDTool conversion failed"}, error=True)
        finally:
            img_path.unlink(missing_ok=True)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── File injection ────────────────────────────────────────────────────────────

@app.route("/api/inject", methods=["POST"])
def api_inject():
    if not BINARY:
        return jsonify({"error": "extract-xiso not found. Run ./install.sh first."}), 500

    if "iso" not in request.files:
        return jsonify({"error": "No ISO file uploaded"}), 400
    if "replacement" not in request.files:
        return jsonify({"error": "No replacement file uploaded"}), 400

    target_path = request.form.get("target_path", "").strip()
    if not target_path:
        return jsonify({"error": "target_path is required"}), 400

    iso_orig_name = secure_filename(request.files["iso"].filename or "output.iso")
    iso_path  = save_upload(request.files["iso"],  suffix=".iso")
    repl_path = save_upload(request.files["replacement"])

    job_id, _ = new_job()

    def worker():
        extract_dir: Optional[Path] = None
        try:
            q = jobs[job_id]["queue"]
            extract_dir = TEMP_DIR / f"inject_{uuid.uuid4()}"
            extract_dir.mkdir(parents=True, exist_ok=True)

            q.put({"type": "log", "text": "Step 1/3: Extracting ISO..."})
            rc, _ = run_command([BINARY, str(iso_path), "-d", str(extract_dir)], job_id)
            if rc != 0:
                finish_job(job_id, {"success": False, "error": "Extraction failed"}, error=True)
                return

            q.put({"type": "log", "text": f"Step 2/3: Injecting {target_path}..."})
            target_full = extract_dir / target_path.lstrip("/").replace("/", os.sep)
            target_full.parent.mkdir(parents=True, exist_ok=True)
            orig_size = target_full.stat().st_size if target_full.exists() else 0
            shutil.copy2(str(repl_path), str(target_full))
            new_size = target_full.stat().st_size
            q.put({"type": "log", "text": f"  Size: {human_size(orig_size)} → {human_size(new_size)}"})

            q.put({"type": "log", "text": "Step 3/3: Repacking ISO..."})
            out_iso_name = f"injected_{iso_orig_name}"
            out_iso = TEMP_DIR / out_iso_name
            rc2, _ = run_command([BINARY, "-c", str(extract_dir), str(out_iso)], job_id)

            if rc2 == 0 and out_iso.exists():
                sz = out_iso.stat().st_size
                finish_job(job_id, {
                    "success": True,
                    "download_url": f"/api/download/{out_iso.name}",
                    "filename": out_iso.name,
                    "size": human_size(sz),
                    "orig_size": human_size(orig_size),
                    "new_size": human_size(new_size),
                })
            else:
                finish_job(job_id, {"success": False, "error": "Repack failed"}, error=True)
        finally:
            iso_path.unlink(missing_ok=True)
            repl_path.unlink(missing_ok=True)
            if extract_dir and extract_dir.exists():
                shutil.rmtree(str(extract_dir), ignore_errors=True)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── Build custom ISO (xdvdfs) ─────────────────────────────────────────────────

@app.route("/api/build-custom", methods=["POST"])
def api_build_custom():
    if not XDVDFS_BIN:
        return jsonify({"error": "xdvdfs not found. Run ./install.sh first."}), 500

    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    uploaded_files = request.files.getlist("files")
    try:
        target_paths = json.loads(request.form.get("filenames", "[]"))
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid filenames JSON"}), 400

    if len(uploaded_files) != len(target_paths):
        return jsonify({"error": "Number of files and filenames must match"}), 400

    xbe_patch = request.form.get("xbe_patch", "false").lower() == "true"

    # Save all uploads to temp files before threading
    saved: list[tuple[Path, str]] = []
    for uf, tp in zip(uploaded_files, target_paths):
        sp = save_upload(uf)
        saved.append((sp, tp))

    job_id, _ = new_job()

    def worker():
        src_dir: Optional[Path] = None
        try:
            q = jobs[job_id]["queue"]
            src_dir = TEMP_DIR / f"build_{uuid.uuid4()}"
            src_dir.mkdir(parents=True, exist_ok=True)

            q.put({"type": "log", "text": "Step 1/3: Arranging uploaded files..."})
            for sp, tp in saved:
                dest = src_dir / tp.lstrip("/").replace("/", os.sep)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(sp), str(dest))
                q.put({"type": "log", "text": f"  → {tp}"})

            if xbe_patch:
                q.put({"type": "log", "text": "Step 2/3: Applying XBE media patches..."})
                for xbe_fp in src_dir.rglob("*.xbe"):
                    try:
                        old_f, new_f = patch_xbe(str(xbe_fp))
                        q.put({"type": "log", "text": f"  Patched: {xbe_fp.name} (0x{old_f:08X} → 0x{new_f:08X})"})
                    except ValueError as e:
                        q.put({"type": "log", "text": f"  Skip: {xbe_fp.name} ({e})"})
            else:
                q.put({"type": "log", "text": "Step 2/3: Skipping XBE patch"})

            q.put({"type": "log", "text": "Step 3/3: Packing ISO with xdvdfs..."})
            out_iso = TEMP_DIR / f"custom_{uuid.uuid4()}.iso"
            rc, _ = run_command([XDVDFS_BIN, "pack", str(src_dir), str(out_iso)], job_id)

            if rc == 0 and out_iso.exists():
                sz = out_iso.stat().st_size
                finish_job(job_id, {
                    "success": True,
                    "download_url": f"/api/download/{out_iso.name}",
                    "filename": out_iso.name,
                    "size": human_size(sz),
                })
            else:
                finish_job(job_id, {"success": False, "error": "xdvdfs pack failed"}, error=True)
        finally:
            if src_dir and src_dir.exists():
                shutil.rmtree(str(src_dir), ignore_errors=True)
            for sp, _ in saved:
                sp.unlink(missing_ok=True)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── xdvdfs tree list ──────────────────────────────────────────────────────────

@app.route("/api/xdvdfs/list", methods=["POST"])
def api_xdvdfs_list():
    if not XDVDFS_BIN:
        return jsonify({"error": "xdvdfs not found. Run ./install.sh first."}), 500

    if "iso" not in request.files:
        return jsonify({"error": "No ISO file uploaded"}), 400

    iso_path = save_upload(request.files["iso"], suffix=".iso")
    job_id, _ = new_job()

    def worker():
        rc, lines = run_command([XDVDFS_BIN, "tree", str(iso_path)], job_id)
        entries = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('['):
                continue
            parts = line.split()
            if parts:
                path = parts[0].lstrip("/")
                size = 0
                if len(parts) > 1:
                    try:
                        size = int(parts[-1])
                    except ValueError:
                        pass
                entries.append({"path": path, "size": size, "size_human": human_size(size) if size else ""})

        total_size = sum(e["size"] for e in entries)
        result = {
            "success": rc == 0,
            "files": entries,
            "tree": build_file_tree(entries),
            "total_files": len(entries),
            "total_size": human_size(total_size),
        }
        if rc != 0:
            result["error"] = "xdvdfs tree failed"
        finish_job(job_id, result, error=(rc != 0))
        iso_path.unlink(missing_ok=True)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── Standalone XBE patcher ────────────────────────────────────────────────────

@app.route("/api/patch-xbe", methods=["POST"])
def api_patch_xbe():
    if "file" not in request.files:
        return jsonify({"error": "No .xbe file uploaded"}), 400

    xbe_orig_name = secure_filename(request.files["file"].filename or "default.xbe")
    xbe_path = save_upload(request.files["file"], suffix=".xbe")
    job_id, _ = new_job()

    def worker():
        try:
            q = jobs[job_id]["queue"]
            q.put({"type": "log", "text": f"Patching {xbe_orig_name}..."})
            old_flags, new_flags = patch_xbe(str(xbe_path))
            q.put({"type": "log", "text": f"  Media flags: 0x{old_flags:08X} → 0x{new_flags:08X}"})
            q.put({"type": "log", "text": "  Patch applied successfully!"})

            out_name = f"patched_{xbe_orig_name}"
            out_path = TEMP_DIR / out_name
            shutil.copy2(str(xbe_path), str(out_path))

            finish_job(job_id, {
                "success": True,
                "download_url": f"/api/download/{out_name}",
                "filename": out_name,
                "old_flags": f"0x{old_flags:08X}",
                "new_flags": f"0x{new_flags:08X}",
            })
        except (ValueError, OSError) as e:
            jobs[job_id]["queue"].put({"type": "log", "text": f"Error: {e}"})
            finish_job(job_id, {"success": False, "error": str(e)}, error=True)
        finally:
            xbe_path.unlink(missing_ok=True)

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
        print(f"[ok] extract-xiso: {BINARY}")
    else:
        print("[warn] extract-xiso not found — run ./install.sh to build it")
    if XDVDFS_BIN:
        print(f"[ok] xdvdfs: {XDVDFS_BIN}")
    else:
        print("[warn] xdvdfs not found — Format Converter and Custom ISO Builder unavailable")
    if XGDTOOL_BIN:
        print(f"[ok] XGDTool: {XGDTOOL_BIN}")
    else:
        print("[warn] XGDTool not found — Format Converter unavailable")
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
