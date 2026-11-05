import argparse
import hashlib
import importlib
import json
import multiprocessing as mp
import os
import pickle
import signal
import sys
import time
import traceback

import numpy as np
from PIL import Image

SCHEMA_VERSION = "1.1"
CAMERAS = ("front", "left_shoulder", "right_shoulder", "overhead", "wrist")

TASKS_18 = [
    "put_item_in_drawer",
    "reach_and_drag",
    "turn_tap",
    "slide_block_to_color_target",
    "open_drawer",
    "put_groceries_in_cupboard",
    "place_shape_in_shape_sorter",
    "put_money_in_safe",
    "push_buttons",
    "close_jar",
    "stack_blocks",
    "place_cups",
    "place_wine_at_rack_location",
    "light_bulb_in",
    "sweep_to_dustpan_of_size",
    "insert_onto_square_peg",
    "meat_off_grill",
    "stack_cups",
]

def _die(signum, frame):
    os._exit(143)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] [pid {os.getpid()}] {msg}", flush=True)

def task_class_from_name(name):
    mod = importlib.import_module(f"rlbench.tasks.{name}")
    cls_name = "".join(part.capitalize() for part in name.split("_"))
    return getattr(mod, cls_name)

def discover_all_tasks():
    import rlbench.tasks
    tasks_dir = os.path.dirname(rlbench.tasks.__file__)
    return sorted(
        f[:-3] for f in os.listdir(tasks_dir)
        if f.endswith(".py") and f != "__init__.py"
    )

def build_obs_config(image_size):
    from rlbench.observation_config import ObservationConfig
    cfg = ObservationConfig()
    cfg.set_all(True)
    for cam in CAMERAS:
        ccfg = getattr(cfg, f"{cam}_camera")
        ccfg.image_size = image_size
        ccfg.depth_in_meters = True
        ccfg.masks_as_one_channel = True
    cfg.camera_intrinsics = True
    cfg.camera_extrinsics = True
    return cfg

def episode_dir(output, task, layout, idx):
    var = "all_variations" if layout == "all_variations" else "variation_all"
    return os.path.join(output, task, var, "episodes", f"episode{idx}")

def episode_complete(ep_dir):
    meta_path = os.path.join(ep_dir, "meta.json")
    if not os.path.isfile(meta_path):
        return False
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        n = meta["num_steps"]
        for cam in CAMERAS:
            for sub in ("rgb", "depth", "mask"):
                d = os.path.join(ep_dir, f"{cam}_{sub}")
                if not os.path.isdir(d) or len(os.listdir(d)) < n:
                    return False
        with open(os.path.join(ep_dir, "low_dim_obs.pkl"), "rb") as f:
            steps = pickle.load(f)
        return len(steps) == n
    except Exception:
        return False

def save_episode(demo, ep_dir, task_name, episode_idx, variation,
                 descriptions, seed, args):
    os.makedirs(ep_dir, exist_ok=True)
    num_steps = len(demo)
    first = demo[0]

    for cam in CAMERAS:
        for sub in ("rgb", "depth", "mask"):
            os.makedirs(os.path.join(ep_dir, f"{cam}_{sub}"), exist_ok=True)

    low_dim_steps = []
    for i, obs in enumerate(demo):
        for cam in CAMERAS:
            rgb = getattr(obs, f"{cam}_rgb")
            depth_m = getattr(obs, f"{cam}_depth")
            mask = getattr(obs, f"{cam}_mask")

            Image.fromarray(rgb.astype(np.uint8)).save(
                os.path.join(ep_dir, f"{cam}_rgb", f"{i}.png"))
            depth_mm = np.clip(depth_m * 1000.0, 0, 65535).astype(np.uint16)
            Image.fromarray(depth_mm).save(
                os.path.join(ep_dir, f"{cam}_depth", f"{i}.png"))
            Image.fromarray(mask.astype(np.uint16)).save(
                os.path.join(ep_dir, f"{cam}_mask", f"{i}.png"))

        low_dim_steps.append({
            "gripper_pose": np.asarray(getattr(obs, "gripper_pose", []), np.float32),
            "gripper_open": float(getattr(obs, "gripper_open", 0.0)),
            "gripper_joint_positions": np.asarray(
                getattr(obs, "gripper_joint_positions", []), np.float32),
            "joint_positions": np.asarray(
                getattr(obs, "joint_positions", []), np.float32),
            "joint_velocities": np.asarray(
                getattr(obs, "joint_velocities", []), np.float32),
            "joint_forces": np.asarray(
                getattr(obs, "joint_forces", []), np.float32),
            "task_low_dim_state": np.asarray(
                getattr(obs, "task_low_dim_state", []), np.float32),
        })

    with open(os.path.join(ep_dir, "low_dim_obs.pkl"), "wb") as f:
        pickle.dump(low_dim_steps, f)

    def _arr(x):
        return None if x is None else np.asarray(x).tolist()

    meta = {
        "schema_version": SCHEMA_VERSION,
        "task": task_name,
        "episode_index": episode_idx,
        "variation_number": int(variation),
        "language_instructions": list(descriptions),
        "seed": int(seed),
        "num_steps": num_steps,
        "image_size": list(args.image_size),
        "cameras": list(CAMERAS),
        "depth_encoding": "uint16_png_millimeters (divide by 1000 -> meters)",
        "mask_encoding": "uint16_png_instance_labels",
        "expert_success": True,
        "camera_intrinsics": {
            cam: _arr((first.misc or {}).get(f"{cam}_camera_intrinsics"))
            for cam in CAMERAS
        },
        "camera_extrinsics": {
            cam: _arr((first.misc or {}).get(f"{cam}_camera_extrinsics"))
            for cam in CAMERAS
        },
        "camera_clipping": {
            cam: {"near": (first.misc or {}).get(f"{cam}_camera_near"),
                  "far": (first.misc or {}).get(f"{cam}_camera_far")}
            for cam in CAMERAS
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "generator": "RLBench DemoGen",
        "provenance": {
            "rlbench_ref": os.environ.get("DEMOGEN_RLBENCH_REF", "unknown"),
            "pyrep_ref": os.environ.get("DEMOGEN_PYREP_REF", "unknown"),
        },
    }
    with open(os.path.join(ep_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

def process_task(task_name, args):
    import random
    from rlbench.environment import Environment
    from rlbench.action_modes.action_mode import MoveArmThenGripper
    from rlbench.action_modes.arm_action_modes import JointVelocity
    from rlbench.action_modes.gripper_action_modes import Discrete

    env = Environment(
        action_mode=MoveArmThenGripper(JointVelocity(), Discrete()),
        obs_config=build_obs_config(tuple(args.image_size)),
        headless=True,
    )
    env.launch()
    try:
        task = env.get_task(task_class_from_name(task_name))
        n_variations = max(1, task.variation_count())
        for ep_idx in range(args.episodes):
            ep_dir = episode_dir(args.output, task_name, args.layout, ep_idx)
            if episode_complete(ep_dir) and not args.overwrite:
                log(f"{task_name} episode{ep_idx}: complete, skipped (resume)")
                continue

            digest = hashlib.sha256(
                f"{args.seed}:{task_name}:{ep_idx}".encode()).hexdigest()
            seed = int(args.seed * 1000003 + int(digest[:8], 16)) % (2 ** 31)
            random.seed(seed)
            np.random.seed(seed % (2 ** 32))

            saved = False
            for attempt in range(1, args.demo_attempts + 1):
                try:
                    variation = random.randrange(n_variations)
                    task.set_variation(variation)
                    descriptions, _ = task.reset()
                    demos = task.get_demos(
                        amount=1, live_demos=True, max_attempts=args.demo_attempts)
                    save_episode(demos[0], ep_dir, task_name, ep_idx,
                                 variation, descriptions, seed, args)
                    log(f"{task_name} episode{ep_idx}: saved "
                        f"(variation={variation}, steps={len(demos[0])}, "
                        f"attempt={attempt})")
                    saved = True
                    break
                except Exception as exc:
                    log(f"{task_name} episode{ep_idx} attempt {attempt} failed: "
                        f"{type(exc).__name__}: {exc}")
                    if attempt == args.demo_attempts:
                        log(f"{task_name} episode{ep_idx}: GIVING UP after "
                            f"{args.demo_attempts} attempts")
            if not saved:
                raise RuntimeError(
                    f"{task_name} episode{ep_idx} not collected")
    finally:
        env.shutdown()

def worker(worker_id, task_names, args, failures):
    signal.signal(signal.SIGTERM, _die)
    signal.signal(signal.SIGINT, _die)
    log(f"worker {worker_id} starting with tasks: {task_names}")
    for task_name in task_names:
        try:
            process_task(task_name, args)
        except Exception:
            failures[task_name] = traceback.format_exc()
            log(f"worker {worker_id}: task {task_name} FAILED:\n"
                f"{failures[task_name]}")
    log(f"worker {worker_id} finished")

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="RLBench DemoGen dataset generator")
    p.add_argument("--tasks", default="all18",
                   help="comma-separated task names, 'all18' (default) or 'all'")
    p.add_argument("--episodes", type=int, default=25,
                   help="episodes per task (default 25)")
    p.add_argument("--image-size", type=int, nargs=2, default=[128, 128],
                   metavar=("W", "H"), help="camera image size (default 128 128)")
    p.add_argument("--output", default="/data", help="output directory")
    p.add_argument("--workers", type=int, default=1,
                   help="parallel workers, each owns one CoppeliaSim instance")
    p.add_argument("--seed", type=int, default=42, help="base random seed")
    p.add_argument("--demo-attempts", type=int, default=10,
                   help="max collection attempts per episode")
    p.add_argument("--layout", choices=["all_variations", "variation_n"],
                   default="all_variations", help="output directory layout")
    p.add_argument("--overwrite", action="store_true",
                   help="regenerate episodes that already exist")
    return p.parse_args(argv)

def resolve_tasks(spec):
    if spec == "all18":
        return list(TASKS_18)
    if spec == "all":
        return discover_all_tasks()
    return [t.strip() for t in spec.split(",") if t.strip()]

def main(argv=None):
    signal.signal(signal.SIGTERM, _die)
    args = parse_args(argv)
    task_names = resolve_tasks(args.tasks)

    benchmark_only = {"slide_block_to_color_target", "place_wine_at_rack_location",
                      "sweep_to_dustpan_of_size"}
    for t in task_names:
        try:
            task_class_from_name(t)
        except Exception as exc:
            hint = ""
            if t in benchmark_only:
                hint = ("\n提示: 该任务是 PerAct/SAM2Act 基准变体，官方 RLBench 没有。"
                        "运行 ./add-benchmark-tasks.sh 补全后重新 ./build.sh 即可。")
            sys.exit(f"error: unknown task '{t}' ({exc}){hint}")

    log(f"tasks={len(task_names)} episodes/task={args.episodes} "
        f"workers={args.workers} output={args.output}")
    os.makedirs(args.output, exist_ok=True)

    n_workers = max(1, min(args.workers, len(task_names)))
    ctx = mp.get_context("spawn")
    manager = ctx.Manager()
    failures = manager.dict()
    procs = []
    for wid in range(n_workers):
        chunk = task_names[wid::n_workers]
        proc = ctx.Process(target=worker, args=(wid, chunk, args, failures))
        proc.start()
        procs.append(proc)
    for proc in procs:
        proc.join()

    bad_exits = {wid: p.exitcode for wid, p in enumerate(procs) if p.exitcode != 0}
    if failures or bad_exits:
        log(f"DONE with problems: failed task(s)={sorted(failures)}, "
            f"worker exit codes={bad_exits}")
        for name, tb in failures.items():
            log(f"--- {name} ---\n{tb}")
        sys.exit(1)
    log("DONE: all tasks collected")

if __name__ == "__main__":
    main()
