import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate as gen
from convert_lerobot import (ACTION_PRESETS, STATE_PRESETS, build_actions,
                             build_states, quat_inv, quat_mul, quat_to_rotvec)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def resolve_ckpt(path):
    p = Path(path)
    for cand in (p, p / "checkpoints" / "last" / "pretrained_model",
                 p / "pretrained_model"):
        if cand.is_dir() and (cand / "model.safetensors").is_file():
            return str(cand)
    sys.exit(f"checkpoint not found under: {path}")


def load_policy(ckpt, device):
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.policies.factory import get_policy_class
    from lerobot.processor.pipeline import DataProcessorPipeline
    cfg = PreTrainedConfig.from_pretrained(ckpt)
    policy = get_policy_class(cfg.type).from_pretrained(ckpt)
    policy.to(device).eval()
    pre = DataProcessorPipeline.from_pretrained(ckpt, "policy_preprocessor.json")
    post = DataProcessorPipeline.from_pretrained(ckpt, "policy_postprocessor.json")
    return policy, pre, post


def obs_to_step_dict(obs):
    return {
        "gripper_pose": np.asarray(obs.gripper_pose, np.float32),
        "gripper_open": float(obs.gripper_open),
        "gripper_joint_positions": np.asarray(obs.gripper_joint_positions, np.float32),
        "joint_positions": np.asarray(obs.joint_positions, np.float32),
        "joint_velocities": np.asarray(obs.joint_velocities, np.float32),
        "joint_forces": np.asarray(obs.joint_forces, np.float32),
    }


def rotvec_to_quat(rv):
    x, y, z = rv
    angle = float(np.linalg.norm(rv))
    if angle < 1e-8:
        return np.array([0.0, 0.0, 0.0, 1.0], np.float32)
    axis = np.array([x, y, z], np.float32) / angle
    s = float(np.sin(angle / 2.0))
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, float(np.cos(angle / 2.0))], np.float32)


def to_batch(obs, cams, size, state_preset, instruction, device):
    import torch
    from PIL import Image
    batch = {}
    for cam in cams:
        img = Image.fromarray(getattr(obs, f"{cam}_rgb"))
        if img.size != tuple(size):
            img = img.resize(tuple(size), Image.BILINEAR)
        arr = np.asarray(img, np.float32) / 255.0
        batch[f"observation.images.{cam}"] = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)
    state = build_states([obs_to_step_dict(obs)], state_preset)[0]
    batch["observation.state"] = torch.from_numpy(state).float().unsqueeze(0).to(device)
    batch["task"] = [instruction]
    return batch


def adapt_action(a, action_space, obs):
    if action_space == "joint":
        return a
    if action_space == "eef-pose":
        q = a[3:7]
        n = float(np.linalg.norm(q))
        q = q / n if n > 1e-6 else np.array([0.0, 0.0, 0.0, 1.0], np.float32)
        return np.concatenate([a[:3], q, a[7:8]]).astype(np.float32)
    cur_pose = np.asarray(obs.gripper_pose, np.float32)
    cur_open = float(obs.gripper_open)
    dpos = a[:3]
    dquat = rotvec_to_quat(a[3:6])
    pos = cur_pose[:3] + dpos
    quat = quat_mul(dquat, cur_pose[3:7])
    open_next = float(np.clip(cur_open + a[6], 0.0, 1.0))
    return np.concatenate([pos, quat, [open_next]]).astype(np.float32)


def shrink_toward(cur_pose, tgt_pose, scale):
    pos = cur_pose[:3] + (tgt_pose[:3] - cur_pose[:3]) * scale
    return np.concatenate([pos, tgt_pose[3:7], tgt_pose[7:8]]).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description="RLBench DemoGen policy rollout evaluator")
    ap.add_argument("--ckpt", required=True, help="training output dir or pretrained_model dir")
    ap.add_argument("--task", required=True)
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--action-space", choices=sorted(ACTION_PRESETS), default="eef-pose")
    ap.add_argument("--state", choices=sorted(STATE_PRESETS), default="pose")
    ap.add_argument("--cameras", default="front")
    ap.add_argument("--image-size", type=int, nargs=2, default=[224, 224])
    ap.add_argument("--instruction", default="", help="language instruction (default: from data meta)")
    ap.add_argument("--max-steps", type=int, default=250)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--gif-dir", default="/data/rollouts")
    ap.add_argument("--report", default="/data/rollouts/report.json")
    ap.add_argument("--device", default="cuda" if __import__("torch").cuda.is_available() else "cpu")
    args = ap.parse_args()

    import random
    import torch
    from PIL import Image
    from rlbench.environment import Environment
    from rlbench.action_modes.action_mode import MoveArmThenGripper
    from rlbench.action_modes.arm_action_modes import EndEffectorPoseViaPlanning, JointPosition
    from rlbench.action_modes.gripper_action_modes import Discrete

    cams = [c.strip() for c in args.cameras.split(",") if c.strip()]
    ckpt = resolve_ckpt(args.ckpt)
    log(f"loading policy from {ckpt}")
    policy, pre, post = load_policy(ckpt, args.device)

    instruction = args.instruction
    if not instruction:
        for root in (os.environ.get("DEMOGEN_DATA", ""), "/data", "output"):
            if not root:
                continue
            for var in ("all_variations", "variation_all"):
                meta_path = Path(root) / args.task / var / "episodes" / "episode0" / "meta.json"
                if meta_path.is_file():
                    instruction = (json.load(open(meta_path)).get("language_instructions") or [""])[0]
                    break
            if instruction:
                break
        instruction = instruction or args.task

    arm_mode = JointPosition() if args.action_space == "joint" else EndEffectorPoseViaPlanning()
    env = Environment(MoveArmThenGripper(arm_mode, Discrete()),
                      obs_config=gen.build_obs_config(tuple(args.image_size)),
                      headless=True)
    env.launch()
    gif_dir = Path(args.gif_dir)
    gif_dir.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        task_env = env.get_task(gen.task_class_from_name(args.task))
        n_var = max(1, task_env.variation_count())
        for ep in range(args.episodes):
            for attempt in range(3):
                random.seed(args.seed * 1000 + ep * 10 + attempt)
                np.random.seed((args.seed * 1000 + ep * 10 + attempt) % (2 ** 32))
                task_env.set_variation(random.randrange(n_var))
                policy.reset()
                descriptions, obs = task_env.reset()
                frames = [obs.front_rgb.copy()]
                success = False
                steps = 0
                stuck = False
                for t in range(args.max_steps):
                    batch = to_batch(obs, cams, tuple(args.image_size), args.state, instruction, args.device)
                    with torch.no_grad():
                        a = policy.select_action(pre(batch))
                        a = post({"action": a})["action"].squeeze(0).float().cpu().numpy()
                    tgt = adapt_action(a, args.action_space, obs)
                    if args.action_space == "joint":
                        cur = np.concatenate([np.asarray(obs.joint_positions, np.float32),
                                              [float(obs.gripper_open)]]).astype(np.float32)
                    else:
                        cur = np.concatenate([np.asarray(obs.gripper_pose, np.float32),
                                              [float(obs.gripper_open)]]).astype(np.float32)
                    stepped = False
                    for scale in (1.0, 0.7, 0.45):
                        cand = tgt if scale == 1.0 else shrink_toward(cur, tgt, scale)
                        act = np.append(cand, 0.0).astype(np.float32)
                        try:
                            obs, reward, terminate = task_env.step(act)
                            stepped = True
                            break
                        except Exception as exc:
                            if scale == 0.45:
                                log(f"step {t}: {type(exc).__name__}: {exc}")
                    if not stepped:
                        stuck = True
                        break
                    frames.append(obs.front_rgb.copy())
                    steps = t + 1
                    if reward > 0.5:
                        success = True
                        break
                    if terminate:
                        break
                if stuck and attempt < 2:
                    log(f"episode {ep}: stuck at step {steps} (attempt {attempt + 1}/3), reseeding scene")
                    continue
                break
            gif_path = gif_dir / f"{args.task}_{'success' if success else 'fail'}_{ep}.gif"
            imgs = [Image.fromarray(f) for f in frames[::max(1, len(frames) // 120)]]
            imgs[0].save(gif_path, save_all=True, append_images=imgs[1:],
                         duration=100, loop=0)
            results.append({"episode": ep, "success": success, "steps": steps,
                            "gif": str(gif_path)})
            log(f"episode {ep}: {'success' if success else 'fail'} in {steps} steps -> {gif_path}")
    finally:
        env.shutdown()

    rate = sum(r["success"] for r in results) / max(1, len(results))
    report = {"task": args.task, "episodes": len(results), "success_rate": rate,
              "action_space": args.action_space, "state": args.state,
              "checkpoint": ckpt, "instruction": instruction,
              "results": results, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log(f"success rate: {rate:.0%} ({sum(r['success'] for r in results)}/{len(results)}) -> {args.report}")


if __name__ == "__main__":
    main()
