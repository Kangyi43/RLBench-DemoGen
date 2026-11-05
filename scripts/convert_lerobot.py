import argparse
import json
import os
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

CAMERAS = ("front", "left_shoulder", "right_shoulder", "overhead", "wrist")
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
CHUNK_SIZE = 1000

STATE_PRESETS = {
    "pose": {
        "dim": 8,
        "names": ["x", "y", "z", "qx", "qy", "qz", "qw", "gripper_open"],
    },
    "full": {
        "dim": 17,
        "names": ["x", "y", "z", "qx", "qy", "qz", "qw", "gripper_open",
                  "gripper_left", "gripper_right",
                  "joint_1", "joint_2", "joint_3", "joint_4", "joint_5",
                  "joint_6", "joint_7"],
    },
}

ACTION_PRESETS = {
    "eef-pose": {
        "dim": 8,
        "names": ["x", "y", "z", "qx", "qy", "qz", "qw", "gripper_open"],
    },
    "eef-delta": {
        "dim": 7,
        "names": ["dx", "dy", "dz", "rx", "ry", "rz", "dgripper_open"],
    },
    "joint": {
        "dim": 8,
        "names": ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5",
                  "joint_6", "joint_7", "gripper_open"],
    },
}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def find_episodes(root, tasks_filter):
    for task in sorted(os.listdir(root)):
        if tasks_filter and task not in tasks_filter:
            continue
        if not NAME_RE.match(task):
            continue
        for var in ("all_variations", "variation_all"):
            ep_root = os.path.join(root, task, var, "episodes")
            if not os.path.isdir(ep_root):
                continue
            eps = [e for e in sorted(os.listdir(ep_root),
                                    key=lambda s: int(s.replace("episode", "")))
                   if os.path.isdir(os.path.join(ep_root, e))]
            for ep in eps:
                yield task, ep, os.path.join(ep_root, ep)


def load_episode(ep_dir):
    meta = json.load(open(os.path.join(ep_dir, "meta.json")))
    steps = pickle.load(open(os.path.join(ep_dir, "low_dim_obs.pkl"), "rb"))
    return meta, steps


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz], np.float32)


def quat_inv(q):
    x, y, z, w = q
    return np.array([-x, -y, -z, w], np.float32)


def quat_to_rotvec(q):
    x, y, z, w = q
    w = float(np.clip(w, -1.0, 1.0))
    norm = float(np.sqrt(x * x + y * y + z * z))
    if norm < 1e-8:
        return np.zeros(3, np.float32)
    angle = 2.0 * float(np.arctan2(norm, w))
    return (np.array([x, y, z], np.float32) / norm * angle).astype(np.float32)


def build_states(steps, preset):
    out = []
    for s in steps:
        if preset == "pose":
            v = np.concatenate([s["gripper_pose"],
                                [s["gripper_open"]]]).astype(np.float32)
        else:
            v = np.concatenate([s["gripper_pose"], [s["gripper_open"]],
                                s["gripper_joint_positions"],
                                s["joint_positions"]]).astype(np.float32)
        out.append(v)
    return np.stack(out)


def build_actions(steps, preset):
    poses = np.stack([s["gripper_pose"] for s in steps])
    opens = np.array([s["gripper_open"] for s in steps], np.float32)
    joints = np.stack([s["joint_positions"] for s in steps])
    n = len(steps)
    nxt = np.arange(1, n + 1).clip(max=n - 1)
    if preset == "eef-pose":
        acts = np.concatenate([poses[nxt], opens[nxt, None]], axis=1)
    elif preset == "joint":
        acts = np.concatenate([joints[nxt], opens[nxt, None]], axis=1)
    else:
        dpos = (poses[nxt, :3] - poses[:, :3]).astype(np.float32)
        drot = []
        for i in range(n):
            qc = poses[i, 3:7]
            qn = poses[nxt[i], 3:7]
            if float(np.dot(qc, qn)) < 0:
                qn = -qn
            dq = quat_mul(qn, quat_inv(qc))
            drot.append(quat_to_rotvec(dq))
        dopen = (opens[nxt] - opens)[:, None]
        acts = np.concatenate([dpos, np.stack(drot), dopen], axis=1)
    return acts.astype(np.float32)


def write_video(path, frames, fps, size):
    import av
    w, h = size
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=fps)
    stream.width = w
    stream.height = h
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "18"}
    for f in frames:
        img = Image.fromarray(f)
        if img.size != (w, h):
            img = img.resize((w, h), Image.BILINEAR)
        frame = av.VideoFrame.from_ndarray(np.asarray(img), format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def read_frames(ep_dir, cam, num_steps, size):
    d = os.path.join(ep_dir, f"{cam}_rgb")
    frames = []
    for i in range(num_steps):
        img = Image.open(os.path.join(d, f"{i}.png")).convert("RGB")
        if img.size != tuple(size):
            img = img.resize(tuple(size), Image.BILINEAR)
        frames.append(np.asarray(img))
    return frames


def main():
    ap = argparse.ArgumentParser(description="RLBench DemoGen -> LeRobot v2.1 exporter")
    ap.add_argument("--src", default="/data", help="native dataset root")
    ap.add_argument("--out", default="/data/lerobot", help="output dataset dir")
    ap.add_argument("--name", default="rlbench_demogen", help="dataset name")
    ap.add_argument("--tasks", default="", help="comma list, empty = all")
    ap.add_argument("--cameras", default=",".join(CAMERAS),
                    help="comma list of cameras to export as video")
    ap.add_argument("--image-size", type=int, nargs=2, default=None,
                    metavar=("W", "H"), help="resize frames (default keep source)")
    ap.add_argument("--state", choices=sorted(STATE_PRESETS), default="pose")
    ap.add_argument("--action-space", choices=sorted(ACTION_PRESETS),
                    default="eef-pose")
    ap.add_argument("--fps", type=int, default=30, help="nominal fps")
    ap.add_argument("--val-ratio", type=float, default=0.0,
                    help="fraction of episodes for test split")
    args = ap.parse_args()

    cams = [c.strip() for c in args.cameras.split(",") if c.strip()]
    for c in cams:
        if c not in CAMERAS:
            sys.exit(f"unknown camera: {c}")
    tasks_filter = {t.strip() for t in args.tasks.split(",") if t.strip()}

    episodes = []
    for task, ep, ep_dir in find_episodes(args.src, tasks_filter):
        meta, steps = load_episode(ep_dir)
        if not steps:
            log(f"skip empty: {task}/{ep}")
            continue
        episodes.append((task, ep, ep_dir, meta, steps))
    if not episodes:
        sys.exit("no episodes found")
    log(f"found {len(episodes)} episodes")

    out = Path(args.out)
    (out / "meta").mkdir(parents=True, exist_ok=True)

    task_strings = []
    task_index_of = {}
    records = []
    stat_acc = {k: {"min": None, "max": None, "sum": None,
                    "sq": None, "count": 0}
                for k in ("observation.state", "action", "timestamp")}

    def acc_update(key, arr):
        a = stat_acc[key]
        arr = np.asarray(arr, np.float64)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        mn = arr.min(axis=0)
        mx = arr.max(axis=0)
        s = arr.sum(axis=0)
        sq = (arr ** 2).sum(axis=0)
        a["min"] = mn if a["min"] is None else np.minimum(a["min"], mn)
        a["max"] = mx if a["max"] is None else np.maximum(a["max"], mx)
        a["sum"] = s if a["sum"] is None else a["sum"] + s
        a["sq"] = sq if a["sq"] is None else a["sq"] + sq
        a["count"] += arr.shape[0]

    import pandas as pd

    global_idx = 0
    total_videos = 0
    for k, (task, ep, ep_dir, meta, steps) in enumerate(episodes):
        n = len(steps)
        ep_chunk = k // CHUNK_SIZE
        name6 = f"{k:06d}"
        data_rel = f"data/chunk-{ep_chunk:03d}/episode_{name6}.parquet"

        instruction = (meta.get("language_instructions") or [task])[0]
        if instruction not in task_index_of:
            task_index_of[instruction] = len(task_strings)
            task_strings.append(instruction)
        tidx = task_index_of[instruction]

        states = build_states(steps, args.state)
        actions = build_actions(steps, args.action_space)
        ts = (np.arange(n, dtype=np.float32) / float(args.fps))
        df = pd.DataFrame({
            "timestamp": ts.astype(np.float32),
            "frame_index": np.arange(n, dtype=np.int64),
            "episode_index": np.full(n, k, dtype=np.int64),
            "index": np.arange(global_idx, global_idx + n, dtype=np.int64),
            "task_index": np.full(n, tidx, dtype=np.int64),
            "observation.state": [r for r in states],
            "action": [r for r in actions],
        })
        data_path = out / data_rel
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(data_path, index=False)

        acc_update("observation.state", states)
        acc_update("action", actions)
        acc_update("timestamp", ts)

        video_keys = {}
        size = args.image_size or list(meta.get("image_size", [128, 128]))
        for cam in cams:
            vkey = f"observation.images.{cam}"
            vrel = f"videos/chunk-{ep_chunk:03d}/{vkey}/episode_{name6}.mp4"
            vpath = out / vrel
            vpath.parent.mkdir(parents=True, exist_ok=True)
            write_video(vpath, read_frames(ep_dir, cam, n, size),
                        args.fps, tuple(size))
            video_keys[vkey] = vrel
            total_videos += 1

        rec = {"episode_index": k, "tasks": [instruction], "length": n,
               data_rel: data_rel}
        rec.update(video_keys)
        records.append(rec)
        global_idx += n
        if (k + 1) % 10 == 0 or k == len(episodes) - 1:
            log(f"exported {k + 1}/{len(episodes)}")

    n_eps = len(episodes)
    n_val = int(round(n_eps * args.val_ratio))
    n_train = n_eps - n_val
    splits = {"train": f"0:{n_train}"}
    if n_val > 0:
        splits["test"] = f"{n_train}:{n_eps}"

    size = args.image_size or list(episodes[0][3].get("image_size", [128, 128]))
    features = {}
    for cam in cams:
        vkey = f"observation.images.{cam}"
        features[vkey] = {
            "dtype": "video",
            "shape": [size[1], size[0], 3],
            "names": ["height", "width", "channels"],
            "info": {"video.height": size[1], "video.width": size[0],
                     "video.channels": 3, "video.codec": "h264",
                     "video.pix_fmt": "yuv420p", "video.is_depth_map": False,
                     "has_audio": False},
        }
    features["observation.state"] = {
        "dtype": "float32",
        "shape": [STATE_PRESETS[args.state]["dim"]],
        "names": STATE_PRESETS[args.state]["names"],
    }
    features["action"] = {
        "dtype": "float32",
        "shape": [ACTION_PRESETS[args.action_space]["dim"]],
        "names": ACTION_PRESETS[args.action_space]["names"],
    }
    for key, dtype in (("timestamp", "float32"), ("frame_index", "int64"),
                       ("episode_index", "int64"), ("index", "int64"),
                       ("task_index", "int64")):
        features[key] = {"dtype": dtype, "shape": [1], "names": [None]}

    info = {
        "codebase_version": "v2.1",
        "name": args.name,
        "robot_type": "panda",
        "total_episodes": n_eps,
        "total_frames": global_idx,
        "total_tasks": len(task_strings),
        "total_videos": total_videos,
        "total_chunks": (n_eps + CHUNK_SIZE - 1) // CHUNK_SIZE,
        "chunks_size": CHUNK_SIZE,
        "fps": args.fps,
        "splits": splits,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": features,
    }
    (out / "meta" / "info.json").write_text(json.dumps(info, indent=2))

    with open(out / "meta" / "tasks.jsonl", "w") as f:
        for i, t in enumerate(task_strings):
            f.write(json.dumps({"task_index": i, "task": t},
                               ensure_ascii=False) + "\n")
    with open(out / "meta" / "episodes.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats = {}
    for key, a in stat_acc.items():
        if a["count"] == 0:
            continue
        count = float(a["count"])
        mean = a["sum"] / count
        var = np.maximum(a["sq"] / count - mean ** 2, 0.0)
        stats[key] = {
            "min": a["min"].tolist(),
            "max": a["max"].tolist(),
            "mean": mean.tolist(),
            "std": np.sqrt(var).tolist(),
            "count": [int(a["count"])],
        }
    (out / "meta" / "stats.json").write_text(json.dumps(stats, indent=2))

    log(f"done: {n_eps} episodes, {global_idx} frames, "
        f"{len(task_strings)} tasks -> {out}")


if __name__ == "__main__":
    main()
