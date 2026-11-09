import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from preview import preview_service

DATA_ROOT = Path(os.environ.get("DEMOGEN_DATA", "/data"))
CONFIGS_DIR = Path(os.environ.get("DEMOGEN_CONFIGS", "/configs"))
CAMERAS = ("front", "left_shoulder", "right_shoulder", "overhead", "wrist")
STREAMS = ("rgb", "depth", "mask")

TASKS_18 = [
    "put_item_in_drawer", "reach_and_drag", "turn_tap",
    "slide_block_to_color_target", "open_drawer", "put_groceries_in_cupboard",
    "place_shape_in_shape_sorter", "put_money_in_safe", "push_buttons",
    "close_jar", "stack_blocks", "place_cups", "place_wine_at_rack_location",
    "light_bulb_in", "sweep_to_dustpan_of_size", "insert_onto_square_peg",
    "meat_off_grill", "stack_cups",
]
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

app = FastAPI(title="RLBench DemoGen")

def _scripts() -> Path:
    env = os.environ.get("DEMOGEN_SCRIPTS")
    if env:
        return Path(env)
    for cand in (Path("/app/scripts"), Path(__file__).resolve().parents[1] / "scripts"):
        if (cand / "generate.py").is_file():
            return cand
    return Path("/app/scripts")

class GenerateConfig(BaseModel):
    tasks: list[str] = TASKS_18
    episodes: int = 25
    image_size: list[int] = [128, 128]
    workers: int = 1
    seed: int = 42
    demo_attempts: int = 10
    layout: str = "all_variations"
    overwrite: bool = False

class ExportConfig(BaseModel):
    tasks: list[str] = []
    cameras: list[str] = []
    image_size: list[int] = []
    state: str = "pose"
    action_space: str = "eef-pose"
    fps: int = 30
    val_ratio: float = 0.0
    name: str = "rlbench_demogen"

class PreviewRequest(BaseModel):
    task: str
    variation: int = -1
    seed: int = 42

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()
MAX_LOG = 4000

def _job_summary(job: dict) -> dict:
    return {
        "id": job["id"],
        "kind": job.get("kind", "generate"),
        "status": job["status"],
        "progress": job["progress"],
        "total": job["total"],
        "started": job["started"],
        "elapsed": round(time.time() - job["started"], 1),
        "config": job["config"],
        "error": job.get("error"),
    }

def _build_cmd(job):
    cfg = job["config"]
    if job.get("kind") == "export":
        args = [
            "python3", str(_scripts() / "convert_lerobot.py"),
            "--src", str(DATA_ROOT),
            "--out", str(DATA_ROOT / "lerobot"),
            "--name", cfg["name"],
            "--state", cfg["state"],
            "--action-space", cfg["action_space"],
            "--fps", str(cfg["fps"]),
            "--val-ratio", str(cfg["val_ratio"]),
        ]
        if cfg.get("tasks"):
            args += ["--tasks", ",".join(cfg["tasks"])]
        if cfg.get("cameras"):
            args += ["--cameras", ",".join(cfg["cameras"])]
        if cfg.get("image_size"):
            args += ["--image-size", str(cfg["image_size"][0]),
                     str(cfg["image_size"][1])]
        return args
    args = [
        "python3", str(_scripts() / "generate.py"),
        "--tasks", ",".join(cfg["tasks"]) if cfg["tasks"] else "all18",
        "--episodes", str(cfg["episodes"]),
        "--workers", str(cfg["workers"]),
        "--seed", str(cfg["seed"]),
        "--demo-attempts", str(cfg["demo_attempts"]),
        "--layout", cfg["layout"],
        "--image-size", str(cfg["image_size"][0]), str(cfg["image_size"][1]),
        "--output", str(DATA_ROOT),
    ]
    if cfg.get("overwrite"):
        args.append("--overwrite")
    return args

def _run_job(job_id: str):
    job = jobs[job_id]
    try:
        args = _build_cmd(job)
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True)
        job["proc"] = proc
        saved_re = re.compile(r": saved \(")
        found_re = re.compile(r"found (\d+) episodes")
        export_re = re.compile(r"exported (\d+)/(\d+)")
        fail_re = re.compile(r"GIVING UP|FAILED")
        for line in proc.stdout:
            line = line.rstrip()
            job["log"].append(line)
            if job.get("kind") == "export":
                m = found_re.search(line)
                if m:
                    job["total"] = int(m.group(1))
                m = export_re.search(line)
                if m:
                    job["progress"] = int(m.group(1))
            else:
                if saved_re.search(line):
                    job["progress"] += 1
            if fail_re.search(line):
                job["failures"] += 1
        proc.wait()
        if job["status"] == "running":
            job["status"] = "done" if proc.returncode == 0 else "failed"
        if proc.returncode != 0 and job["status"] == "failed":
            job["error"] = f"worker exited with code {proc.returncode}"
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = f"{type(exc).__name__}: {exc}"
        job["log"].append(f"job crashed: {exc}")

@app.post("/api/generate")
def start_generate(cfg: GenerateConfig):
    if not cfg.tasks:
        raise HTTPException(400, "任务列表为空")
    for t in cfg.tasks:
        if not NAME_RE.match(t):
            raise HTTPException(400, f"非法任务名: {t}")
    with jobs_lock:
        running = [j for j in jobs.values() if j["status"] == "running"]
        if running:
            raise HTTPException(409, "已有生成任务在运行，请等待完成")
        job_id = uuid.uuid4().hex[:8]
        job = {
            "id": job_id,
            "kind": "generate",
            "status": "running",
            "progress": 0,
            "failures": 0,
            "total": len(cfg.tasks) * cfg.episodes,
            "started": time.time(),
            "config": cfg.model_dump(),
            "log": deque(maxlen=MAX_LOG),
            "proc": None,
        }
        jobs[job_id] = job
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id}

@app.post("/api/export")
def start_export(cfg: ExportConfig):
    for t in cfg.tasks:
        if not NAME_RE.match(t):
            raise HTTPException(400, f"非法任务名: {t}")
    for c in cfg.cameras:
        if c not in CAMERAS:
            raise HTTPException(400, f"未知相机: {c}")
    if cfg.state not in ("pose", "full"):
        raise HTTPException(400, "state 须为 pose/full")
    if cfg.action_space not in ("eef-pose", "eef-delta", "joint"):
        raise HTTPException(400, "action_space 未知")
    with jobs_lock:
        running = [j for j in jobs.values() if j["status"] == "running"]
        if running:
            raise HTTPException(409, "已有任务在运行，请等待完成")
        job_id = uuid.uuid4().hex[:8]
        job = {
            "id": job_id,
            "kind": "export",
            "status": "running",
            "progress": 0,
            "failures": 0,
            "total": 0,
            "started": time.time(),
            "config": cfg.model_dump(),
            "log": deque(maxlen=MAX_LOG),
            "proc": None,
        }
        jobs[job_id] = job
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id}

@app.get("/api/jobs")
def list_jobs():
    with jobs_lock:
        return [_job_summary(j) for j in sorted(
            jobs.values(), key=lambda j: -j["started"])]

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, offset: int = 0):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    logs = list(job["log"])
    summary = _job_summary(job)
    summary["failures"] = job["failures"]
    summary["logs"] = logs[offset:]
    summary["log_offset"] = len(logs)
    return summary

@app.delete("/api/jobs/{job_id}")
def clear_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        if job["status"] == "running":
            raise HTTPException(409, "任务运行中，无法清除")
        jobs.pop(job_id, None)
    return {"ok": True}

@app.post("/api/jobs/{job_id}/stop")
def stop_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["status"] != "running":
        return {"ok": True, "status": job["status"]}
    job["status"] = "stopping"
    proc = job.get("proc")
    if proc and proc.poll() is None:
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, 15)
        except Exception:
            proc.terminate()
        time.sleep(2)
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, 9)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
    subprocess.run(["pkill", "-9", "-f", "coppeliaSim"], check=False)
    subprocess.run(["pkill", "-9", "-f", "generate.py"], check=False)
    subprocess.run(["pkill", "-9", "-f", "convert_lerobot.py"], check=False)
    job["status"] = "stopped"
    job["log"].append("任务已被用户中断")
    return {"ok": True, "status": "stopped"}

@app.get("/api/preview/status")
def preview_status():
    return {"status": preview_service.status, "error": preview_service.error}

@app.post("/api/preview")
def preview(req: PreviewRequest):
    if not NAME_RE.match(req.task):
        raise HTTPException(400, f"非法任务名: {req.task}")
    try:
        return preview_service.render(req.task, req.variation, req.seed)
    except Exception as exc:
        preview_service.error = f"{type(exc).__name__}: {exc}"
        raise HTTPException(
            500, f"预览渲染失败：{preview_service.error}（仿真器将自动重建，可重试）")

@app.post("/api/preview/recover")
def preview_recover():
    preview_service.recover()
    return {"status": preview_service.status}

def _episode_dirs(task: str):
    for var in ("all_variations", "variation_all"):
        root = DATA_ROOT / task / var / "episodes"
        if root.is_dir():
            for ep in sorted(root.iterdir(), key=lambda p: p.name):
                if ep.is_dir():
                    yield ep

@app.get("/api/datasets")
def list_datasets():
    out = []
    if not DATA_ROOT.is_dir():
        return out
    for task_dir in sorted(DATA_ROOT.iterdir()):
        if not task_dir.is_dir() or not NAME_RE.match(task_dir.name):
            continue
        episodes = []
        for ep in _episode_dirs(task_dir.name):
            meta_path = ep / "meta.json"
            meta = {}
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text())
                except Exception:
                    meta = {}
            episodes.append({
                "name": ep.name,
                "complete": bool(meta),
                "num_steps": meta.get("num_steps"),
                "variation": meta.get("variation_number"),
                "instructions": meta.get("language_instructions", []),
            })
        if episodes:
            out.append({
                "task": task_dir.name,
                "episodes": episodes,
                "complete": sum(e["complete"] for e in episodes),
            })
    return out

@app.get("/api/datasets/{task}/{episode}")
def episode_meta(task: str, episode: str):
    ep = _safe_episode(task, episode)
    meta_path = ep / "meta.json"
    if not meta_path.is_file():
        raise HTTPException(404, "meta.json 不存在")
    return json.loads(meta_path.read_text())

@app.get("/api/datasets/{task}/{episode}/frame")
def episode_frame(task: str, episode: str, cam: str = "front",
                  stream: str = "rgb", step: int = 0):
    if cam not in CAMERAS or stream not in STREAMS:
        raise HTTPException(400, "未知相机/流")
    ep = _safe_episode(task, episode)
    path = ep / f"{cam}_{stream}" / f"{step}.png"
    if not path.is_file():
        raise HTTPException(404, f"帧不存在: {path.name}")
    if stream == "rgb":
        return FileResponse(path, media_type="image/png")
    return Response(content=_stylize(path, stream), media_type="image/jpeg")

def _safe_episode(task: str, episode: str) -> Path:
    if not (NAME_RE.match(task) and NAME_RE.match(episode)):
        raise HTTPException(400, "非法路径")
    for ep in _episode_dirs(task):
        if ep.name == episode:
            return ep
    raise HTTPException(404, "episode 不存在")

_DEPTH_STOPS = np.array([
    [0.00, 12, 8, 40], [0.25, 82, 18, 120], [0.5, 188, 55, 84],
    [0.75, 249, 140, 36], [1.0, 252, 235, 172]], dtype=np.float64)

def _stylize(path: Path, stream: str) -> bytes:
    from PIL import Image
    arr = np.asarray(Image.open(path))
    if stream == "depth":
        depth = arr.astype(np.float64) / 1000.0
        t = np.clip(depth / max(depth.max(), 1e-6), 0, 1)
        xs = _DEPTH_STOPS[:, 0]
        out = np.stack([
            np.interp(t, xs, _DEPTH_STOPS[:, i + 1]) for i in range(3)],
            axis=-1).astype(np.uint8)
    else:
        lab = arr.astype(np.int64)
        out = np.zeros(lab.shape + (3,), np.uint8)
        for i in np.unique(lab):
            if i == 0:
                continue
            hue = (i * 47) % 255
            color = np.array([(hue * 53) % 200 + 55,
                              (hue * 29) % 200 + 55,
                              (hue * 97) % 200 + 55])
            out[lab == i] = color
    import io as _io
    buf = _io.BytesIO()
    Image.fromarray(out).save(buf, format="JPEG", quality=88)
    return buf.getvalue()

@app.get("/api/tasks")
def list_tasks():
    return {"tasks": TASKS_18, "data_root": str(DATA_ROOT)}

@app.post("/api/verify")
def run_verify():
    proc = subprocess.run(
        ["python3", str(_scripts() / "verify.py"), str(DATA_ROOT), "--json",
         "/tmp/demogen_verify.json"],
        capture_output=True, text=True, timeout=600)
    report = {}
    try:
        report = json.loads(Path("/tmp/demogen_verify.json").read_text())
    except Exception:
        report = {"summary": {"total": 0, "ok": 0, "failed": 0},
                  "error": proc.stdout[-2000:] or proc.stderr[-2000:]}
    report["exit_code"] = proc.returncode
    return report

@app.post("/api/config/save")
def save_config(req: dict):
    import yaml
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_\-]", "_", str(req.get("name", "config")))
    path = CONFIGS_DIR / f"{name}.yaml"
    path.write_text(yaml.safe_dump(req.get("config", {}), allow_unicode=True,
                                   sort_keys=False))
    return {"saved": str(path)}

STATIC = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
