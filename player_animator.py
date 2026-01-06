import os
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pygame

# =========================
# Tunable thresholds (seconds, pixels/sec)
# =========================
SWIM_SPEED_THRESHOLD = 30.0
JUMP_VY_THRESHOLD = -40.0
FALL_VY_THRESHOLD = 40.0
SHOOT_DURATION = 0.18
HURT_DURATION = 0.35
DASH_DURATION = 0.18


Frame = pygame.Surface


@dataclass
class AnimationClip:
    name: str
    frames_right: List[Frame]
    fps: float
    looping: bool
    offset: Tuple[int, int] = (0, 0)
    on_enter: Optional[Callable[[], None]] = None
    on_exit: Optional[Callable[[], None]] = None
    frames_left: Optional[List[Frame]] = None

    def __post_init__(self) -> None:
        if not self.frames_right:
            raise ValueError(f"AnimationClip '{self.name}' has no frames")
        if self.fps <= 0:
            raise ValueError(f"AnimationClip '{self.name}' has invalid fps={self.fps}")
        if self.frames_left is None:
            self.frames_left = [pygame.transform.flip(frame, True, False) for frame in self.frames_right]
        self.frame_duration = 1.0 / self.fps
        self.reset()

    def reset(self) -> None:
        self.elapsed = 0.0
        self.index = 0
        self.finished = False

    def update(self, dt: float) -> None:
        if self.finished and not self.looping:
            return
        self.elapsed += dt
        while self.elapsed >= self.frame_duration:
            self.elapsed -= self.frame_duration
            if self.index < len(self.frames_right) - 1:
                self.index += 1
            elif self.looping:
                self.index = 0
            else:
                self.finished = True
                break

    def get_frame(self, facing_dir: int) -> Frame:
        if facing_dir < 0 and self.frames_left:
            return self.frames_left[self.index]
        return self.frames_right[self.index]


class PlayerAnimator:
    def __init__(self, clips: Dict[str, AnimationClip], fallback_state: str = "idle") -> None:
        self.clips = clips
        self.fallback_state = fallback_state
        self.state = fallback_state
        self.clip = self.clips[self.state]
        self._shoot_was_active = False

    def _switch_state(self, new_state: str) -> None:
        if new_state == self.state:
            return
        if self.clip.on_exit:
            self.clip.on_exit()
        self.state = new_state
        self.clip = self.clips[self.state]
        self.clip.reset()
        if self.clip.on_enter:
            self.clip.on_enter()

    def _get_attr(self, snapshot, name: str, default):
        if isinstance(snapshot, dict):
            return snapshot.get(name, default)
        return getattr(snapshot, name, default)

    def _choose_locomotion_state(self, snapshot) -> str:
        vx = float(self._get_attr(snapshot, "vx", 0.0))
        vy = float(self._get_attr(snapshot, "vy", 0.0))
        on_ground = bool(self._get_attr(snapshot, "on_ground", False))

        if vy <= JUMP_VY_THRESHOLD:
            return "jump"
        if vy >= FALL_VY_THRESHOLD:
            return "fall"

        if on_ground:
            if abs(vx) >= SWIM_SPEED_THRESHOLD:
                return "swim"
            return "idle"

        if abs(vx) >= SWIM_SPEED_THRESHOLD or abs(vy) >= SWIM_SPEED_THRESHOLD:
            return "swim"
        return "idle"

    def update(self, dt: float, snapshot) -> Tuple[Frame, Tuple[int, int], str]:
        is_hurt = bool(self._get_attr(snapshot, "is_hurt", False))
        is_dashing = bool(self._get_attr(snapshot, "is_dashing", False))
        is_shooting = bool(self._get_attr(snapshot, "is_shooting", False))
        facing_dir = int(self._get_attr(snapshot, "facing_dir", 1))
        shoot_triggered = is_shooting and not self._shoot_was_active

        # Priority: hurt > dash > shoot > locomotion
        if is_hurt:
            next_state = "hurt"
        elif is_dashing:
            next_state = "dash"
        elif self.state == "shoot" and not self.clip.finished:
            next_state = "shoot"
        elif shoot_triggered:
            next_state = "shoot"
        else:
            next_state = self._choose_locomotion_state(snapshot)

        self._switch_state(next_state)
        self.clip.update(dt)

        if self.state == "shoot" and self.clip.finished:
            fallback = self._choose_locomotion_state(snapshot)
            self._switch_state(fallback)

        self._shoot_was_active = is_shooting

        frame = self.clip.get_frame(facing_dir)
        return frame, self.clip.offset, self.state


DEFAULT_MANIFEST = {
    "idle": {
        "paths": ["Assets/scuba.png"],
        "size": (64, 64),
        "fps": 6.0,
        "loop": True,
        "offset": (0, 0),
    },
    "swim": {
        "paths": ["Assets/swim2.png"],
        "size": (64, 64),
        "fps": 10.0,
        "loop": True,
        "offset": (0, 0),
    },
    "jump": {
        "paths": ["Assets/swim2.png"],
        "size": (64, 64),
        "fps": 8.0,
        "loop": True,
        "offset": (0, 0),
    },
    "fall": {
        "paths": ["Assets/swim2.png"],
        "size": (64, 64),
        "fps": 8.0,
        "loop": True,
        "offset": (0, 0),
    },
    "shoot": {
        "paths": ["Assets/scuba.png"],
        "size": (64, 64),
        "fps": 12.0,
        "loop": False,
        "offset": (0, 0),
    },
    "dash": {
        "paths": ["Assets/Dash.png"],
        "size": (96, 96),
        "fps": 12.0,
        "loop": True,
        "offset": (16, 16),
    },
    "hurt": {
        "paths": ["Assets/scuba.png"],
        "size": (64, 64),
        "fps": 8.0,
        "loop": False,
        "offset": (0, 0),
    },
}


def _load_frame(path: str, size: Optional[Tuple[int, int]]) -> Frame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing animation frame: {path}")
    image = pygame.image.load(path).convert_alpha()
    if size is not None:
        image = pygame.transform.scale(image, size)
    return image


def load_clips_from_manifest(manifest: Dict[str, dict], base_dir: str) -> Dict[str, AnimationClip]:
    clips: Dict[str, AnimationClip] = {}
    for state, data in manifest.items():
        paths = data["paths"]
        size = data.get("size")
        fps = float(data.get("fps", 8.0))
        loop = bool(data.get("loop", True))
        offset = tuple(data.get("offset", (0, 0)))

        frames_right = [_load_frame(os.path.join(base_dir, path), size) for path in paths]
        clips[state] = AnimationClip(
            name=state,
            frames_right=frames_right,
            fps=fps,
            looping=loop,
            offset=(int(offset[0]), int(offset[1])),
        )
    return clips


def build_default_player_animator(asset_root: str) -> PlayerAnimator:
    clips = load_clips_from_manifest(DEFAULT_MANIFEST, asset_root)
    return PlayerAnimator(clips=clips, fallback_state="idle")
