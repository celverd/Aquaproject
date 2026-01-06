import math
import random

import pygame

# =========================
# TUNING CONSTANTS (feel)
# =========================
RECOIL_STRENGTH = 260.0  # px/sec impulse at start; higher = stronger kickback
RECOIL_DURATION = 0.08  # seconds; longer = more lingering push
RECOIL_DECAY_EXP = 2.0  # curve exponent; higher = snappier falloff

FIRE_COOLDOWN = 0.14  # seconds; higher = slower rate of fire
MUZZLE_FLASH_DURATION = 0.06  # seconds; short flash window for VFX/SFX hooks

CAMERA_KICK_INTENSITY = 2.5  # pixels; micro shake distance
CAMERA_KICK_DURATION = 0.08  # seconds; micro shake time

BUBBLE_INITIAL_SPEED = 420.0  # px/sec; initial punchy speed
BUBBLE_DRIFT_SPEED = 140.0  # px/sec; slow cruising speed
BUBBLE_SLOWDOWN_TIME = 0.22  # seconds; time to ease into drift
BUBBLE_BUOYANCY = 26.0  # px/sec^2 upward acceleration
BUBBLE_LIFETIME = 1.8  # seconds; total lifetime
BUBBLE_FADE_TIME = 0.25  # seconds; fade-out window at end of lifetime
BUBBLE_RADIUS = 6  # collision radius in pixels
BUBBLE_SPREAD_DEGREES = 2.5  # degrees; small random spread, set to 0 to disable

HIT_PAUSE_DURATION = 0.045  # seconds; very short hit freeze
HIT_KNOCKBACK = 140.0  # px/sec impulse applied to enemies


class BubbleProjectile:
    def __init__(self, pos, direction):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(direction).normalize() * BUBBLE_INITIAL_SPEED
        self.age = 0.0
        self.alive = True
        self.fade = 1.0
        self.radius = BUBBLE_RADIUS
        self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        self._update_rect()

    def _update_rect(self):
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def update(self, dt):
        self.age += dt

        if self.age >= BUBBLE_LIFETIME:
            self.alive = False
            return

        slowdown_t = min(self.age / BUBBLE_SLOWDOWN_TIME, 1.0)
        desired_speed = (
            (1.0 - slowdown_t) * BUBBLE_INITIAL_SPEED
            + slowdown_t * BUBBLE_DRIFT_SPEED
        )
        if self.vel.length_squared() > 0.0:
            self.vel = self.vel.normalize() * desired_speed

        self.vel.y -= BUBBLE_BUOYANCY * dt
        self.pos += self.vel * dt
        self._update_rect()

        if self.age >= BUBBLE_LIFETIME - BUBBLE_FADE_TIME:
            fade_t = (self.age - (BUBBLE_LIFETIME - BUBBLE_FADE_TIME)) / BUBBLE_FADE_TIME
            self.fade = max(0.0, 1.0 - min(fade_t, 1.0))

    def register_hit(self, target=None, hit_dir=None, on_hit=None):
        """
        Call this from your collision system when the bubble hits something.
        Returns the requested hit-pause duration (seconds).
        """
        if target is not None and hasattr(target, "apply_impulse") and hit_dir is not None:
            impulse = pygame.Vector2(hit_dir).normalize() * HIT_KNOCKBACK
            target.apply_impulse(impulse)

        if on_hit is not None:
            on_hit(self, target, HIT_PAUSE_DURATION)

        self.alive = False
        return HIT_PAUSE_DURATION


class BubbleGun:
    def __init__(self, on_fire=None, on_hit=None, camera_shake=None):
        self.on_fire = on_fire
        self.on_hit = on_hit
        self.camera_shake = camera_shake

        self.cooldown = FIRE_COOLDOWN
        self.cooldown_timer = 0.0

        self.recoil_strength = RECOIL_STRENGTH
        self.recoil_duration = RECOIL_DURATION
        self.recoil_decay_exp = RECOIL_DECAY_EXP
        self.recoil_timer = 0.0
        self.recoil_dir = pygame.Vector2(0, 0)
        self.recoil_impulse = pygame.Vector2(0, 0)

        self.muzzle_timer = 0.0

    @property
    def can_fire(self):
        return self.cooldown_timer <= 0.0

    @property
    def muzzle_flash_active(self):
        return self.muzzle_timer > 0.0

    def update(self, dt):
        if self.cooldown_timer > 0.0:
            self.cooldown_timer = max(0.0, self.cooldown_timer - dt)

        if self.muzzle_timer > 0.0:
            self.muzzle_timer = max(0.0, self.muzzle_timer - dt)

        self.recoil_impulse.update(0.0, 0.0)
        if self.recoil_timer > 0.0:
            self.recoil_timer = max(0.0, self.recoil_timer - dt)
            ratio = self.recoil_timer / max(self.recoil_duration, 1e-6)
            intensity = ratio**self.recoil_decay_exp
            self.recoil_impulse = self.recoil_dir * (self.recoil_strength * intensity * dt)

    def consume_recoil(self):
        impulse = self.recoil_impulse.copy()
        self.recoil_impulse.update(0.0, 0.0)
        return impulse

    def try_fire(self, origin, direction):
        if not self.can_fire:
            return None

        aim = pygame.Vector2(direction)
        if aim.length_squared() == 0.0:
            return None
        aim = aim.normalize()

        spread = BUBBLE_SPREAD_DEGREES
        if spread > 0.0:
            spread_radians = math.radians(random.uniform(-spread, spread))
            aim.rotate_ip_rad(spread_radians)

        projectile = BubbleProjectile(origin, aim)

        self.cooldown_timer = self.cooldown
        self.recoil_timer = self.recoil_duration
        self.recoil_dir = -aim
        self.muzzle_timer = MUZZLE_FLASH_DURATION

        if self.on_fire is not None:
            self.on_fire(origin, aim)

        if self.camera_shake is not None:
            self.camera_shake(CAMERA_KICK_INTENSITY, CAMERA_KICK_DURATION)

        return projectile
