import base64
import io
import os
import random
import sys
import threading
import time
from pathlib import Path

CAMERAS = ("front", "left_shoulder", "right_shoulder", "overhead", "wrist")
PREVIEW_SIZE = (320, 320)

def _scripts_dir() -> Path:
    env = os.environ.get("DEMOGEN_SCRIPTS")
    if env:
        return Path(env)
    for cand in (Path("/app/scripts"), Path(__file__).resolve().parents[1] / "scripts"):
        if (cand / "generate.py").is_file():
            return cand
    return Path("/app/scripts")

class PreviewService:
    def __init__(self):
        self._lock = threading.Lock()
        self._env = None
        self.status = "cold"
        self.error = None

    def _ensure_env(self):
        if self._env is not None:
            return
        self.status = "warming"
        scripts = _scripts_dir()
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import generate as gen
        from rlbench.environment import Environment
        from rlbench.action_modes.action_mode import MoveArmThenGripper
        from rlbench.action_modes.arm_action_modes import JointVelocity
        from rlbench.action_modes.gripper_action_modes import Discrete

        env = Environment(
            action_mode=MoveArmThenGripper(JointVelocity(), Discrete()),
            obs_config=gen.build_obs_config(PREVIEW_SIZE),
            headless=True,
        )
        env.launch()
        self._env = env
        self.status = "ready"
        self.error = None

    def _shutdown(self):
        if self._env is not None:
            try:
                self._env.shutdown()
            except Exception:
                pass
        self._env = None
        self.status = "cold"

    def render(self, task: str, variation: int = -1, seed: int = 42):
        with self._lock:
            self._ensure_env()
            scripts = _scripts_dir()
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            import generate as gen
            from PIL import Image

            task_env = self._env.get_task(gen.task_class_from_name(task))
            n_variations = max(1, task_env.variation_count())
            random.seed(seed)
            if variation < 0:
                variation = random.randrange(n_variations)
            variation = int(variation) % n_variations

            t0 = time.time()
            task_env.set_variation(variation)
            descriptions, obs = task_env.reset()
            views = {}
            for cam in CAMERAS:
                rgb = getattr(obs, f"{cam}_rgb")
                buf = io.BytesIO()
                Image.fromarray(rgb).save(buf, format="JPEG", quality=88)
                views[cam] = base64.b64encode(buf.getvalue()).decode()
            return {
                "views": views,
                "variation": variation,
                "variation_count": n_variations,
                "language_instructions": list(descriptions),
                "render_seconds": round(time.time() - t0, 2),
            }

    def recover(self):
        with self._lock:
            self._shutdown()
            self.status = "cold"

preview_service = PreviewService()
