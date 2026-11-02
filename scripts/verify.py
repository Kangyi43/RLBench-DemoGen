import argparse
import json
import os
import pickle
import sys

from PIL import Image

CAMERAS = ("front", "left_shoulder", "right_shoulder", "overhead", "wrist")
REQUIRED_META = ("schema_version", "task", "episode_index", "variation_number",
                 "num_steps", "cameras", "depth_encoding")

def find_episodes(root, task_filter=None):
    for task in sorted(os.listdir(root)):
        if task_filter and task != task_filter:
            continue
        for var in ("all_variations", "variation_all"):
            ep_root = os.path.join(root, task, var, "episodes")
            if not os.path.isdir(ep_root):
                continue
            for ep in sorted(os.listdir(ep_root)):
                ep_dir = os.path.join(ep_root, ep)
                if os.path.isdir(ep_dir):
                    yield task, ep, ep_dir

def check_episode(ep_dir):
    problems = []
    meta_path = os.path.join(ep_dir, "meta.json")
    if not os.path.isfile(meta_path):
        return ["meta.json missing"]
    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except Exception as exc:
        return [f"meta.json unreadable: {exc}"]
    for key in REQUIRED_META:
        if key not in meta:
            problems.append(f"meta.json missing key '{key}'")
    if problems:
        return problems

    n = meta["num_steps"]
    for cam in CAMERAS:
        for sub, ext in (("rgb", "png"), ("depth", "png"), ("mask", "png")):
            d = os.path.join(ep_dir, f"{cam}_{sub}")
            if not os.path.isdir(d):
                problems.append(f"{cam}_{sub}/ missing")
                continue
            frames = sorted(f for f in os.listdir(d) if f.endswith(f".{ext}"))
            if len(frames) != n:
                problems.append(f"{cam}_{sub}/ has {len(frames)} frames, "
                                f"expected {n}")
                continue
            for frame in (frames[0], frames[-1]):
                try:
                    Image.open(os.path.join(d, frame)).verify()
                except Exception as exc:
                    problems.append(f"{cam}_{sub}/{frame} invalid: {exc}")

    pkl_path = os.path.join(ep_dir, "low_dim_obs.pkl")
    if not os.path.isfile(pkl_path):
        problems.append("low_dim_obs.pkl missing")
    else:
        try:
            with open(pkl_path, "rb") as f:
                steps = pickle.load(f)
            if len(steps) != n:
                problems.append(f"low_dim_obs.pkl has {len(steps)} steps, "
                                f"expected {n}")
        except Exception as exc:
            problems.append(f"low_dim_obs.pkl unreadable: {exc}")
    return problems

def main():
    ap = argparse.ArgumentParser(description="RLBench DemoGen dataset verifier")
    ap.add_argument("root", help="dataset root (e.g. /data)")
    ap.add_argument("--task", default=None, help="only check this task")
    ap.add_argument("--json", default=None, help="write JSON report here")
    args = ap.parse_args()

    report = {}
    total = failed = 0
    for task, ep, ep_dir in find_episodes(args.root, args.task):
        problems = check_episode(ep_dir)
        total += 1
        key = f"{task}/{ep}"
        if problems:
            failed += 1
            report[key] = problems
            print(f"FAIL {key}")
            for p in problems:
                print(f"     - {p}")
        else:
            report[key] = []
            print(f"ok   {key}")

    summary = {"total": total, "ok": total - failed, "failed": failed}
    print(f"\nsummary: {summary}")
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"summary": summary, "episodes": report}, f, indent=2)
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
