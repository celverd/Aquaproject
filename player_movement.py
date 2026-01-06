from dataclasses import dataclass
import math

# =========================
# MOVEMENT TUNING (PX, SEC)
# =========================
# Keep values near the top so designers can tune quickly without hunting logic.
ACCEL = 900.0
DRAG = 2.6
MAX_SPEED = 220.0
SINK_ACCEL = 120.0

JUMP_SPEED = 220.0
JUMP_HOLD_ACCEL = 420.0
JUMP_HOLD_TIME = 0.18
JUMP_CUT_MULT = 0.55
COYOTE_TIME = 0.12
JUMP_BUFFER_TIME = 0.12

DASH_SPEED = 420.0
DASH_TIME = 0.18
DASH_COOLDOWN = 0.3

WALL_SLIDE_SPEED = 24.0
WALL_KICK_TIME = 0.18
WALL_KICK_LOCKOUT = 0.25
WALL_KICK_SPEED_X = 260.0
WALL_KICK_SPEED_Y = 180.0


@dataclass
class MovementInput:
    x: float
    y: float
    jump_pressed: bool
    jump_held: bool
    jump_released: bool
    dash_pressed: bool


class PlayerMovement:
    """Movement-only component. Rendering and collision stay elsewhere."""

    def __init__(self) -> None:
        # Velocity (px/sec)
        self.vx = 0.0
        self.vy = 0.0

        # Contacts
        self.on_ground = False
        self.wall_left = False
        self.wall_right = False

        # Facing
        self.facing = 1

        # Wall crouch / kick
        self.is_wall_crouch = False
        self.stick_side = 0
        self.wall_kick_timer = 0.0
        self.wall_kick_lockout = 0.0

        # Dash
        self.is_dashing = False
        self.dash_timer = 0.0
        self.dash_cd = 0.0
        self.dash_dx = 0.0
        self.dash_dy = 0.0

        # Jump helpers
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0
        self.jump_hold_timer = 0.0

    def _start_jump(self) -> None:
        # Jump is an upward impulse that can be sustained briefly when held.
        self.vy = -JUMP_SPEED
        self.jump_hold_timer = JUMP_HOLD_TIME
        self.jump_buffer_timer = 0.0
        self.coyote_timer = 0.0

    def update(self, inputs: MovementInput, dt: float, solids, resolve_axis) -> None:
        # Timers
        if self.dash_cd > 0.0:
            self.dash_cd = max(0.0, self.dash_cd - dt)
        if self.wall_kick_timer > 0.0:
            self.wall_kick_timer = max(0.0, self.wall_kick_timer - dt)
        if self.wall_kick_lockout > 0.0:
            self.wall_kick_lockout = max(0.0, self.wall_kick_lockout - dt)

        if self.on_ground:
            self.coyote_timer = COYOTE_TIME
        else:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)

        if inputs.jump_pressed:
            self.jump_buffer_timer = JUMP_BUFFER_TIME
        else:
            self.jump_buffer_timer = max(0.0, self.jump_buffer_timer - dt)

        if abs(inputs.x) > 0.01:
            self.facing = 1 if inputs.x > 0 else -1

        # Start dash
        if inputs.dash_pressed and (not self.is_dashing) and self.dash_cd <= 0.0 and (not self.is_wall_crouch):
            self.is_dashing = True
            self.dash_timer = DASH_TIME
            self.dash_cd = DASH_COOLDOWN

            dash_dx = 0.0
            dash_dy = 0.0
            if inputs.x < 0:
                dash_dx = -1.0
            elif inputs.x > 0:
                dash_dx = 1.0
            if inputs.y < 0:
                dash_dy = -1.0
            elif inputs.y > 0:
                dash_dy = 1.0

            if dash_dx != 0.0 and dash_dy != 0.0:
                dash_dx *= 0.707
                dash_dy *= 0.707

            if dash_dx == 0.0 and dash_dy == 0.0:
                dash_dx = float(self.facing)

            self.dash_dx = dash_dx * DASH_SPEED
            self.dash_dy = dash_dy * DASH_SPEED
            self.vx = self.dash_dx
            self.vy = self.dash_dy

        # Wall kick (jump while clinging)
        if self.is_wall_crouch and inputs.jump_pressed and self.wall_kick_lockout <= 0.0:
            self.is_wall_crouch = False
            self.wall_kick_timer = WALL_KICK_TIME
            self.wall_kick_lockout = WALL_KICK_LOCKOUT
            kick_dir = -self.stick_side if self.stick_side != 0 else -self.facing
            self.vx = kick_dir * WALL_KICK_SPEED_X
            self.vy = -WALL_KICK_SPEED_Y
            self.stick_side = 0

        # Jump start (buffer + coyote)
        if self.jump_buffer_timer > 0.0 and self.coyote_timer > 0.0 and (not self.is_wall_crouch):
            self._start_jump()

        # Movement update
        if self.is_dashing:
            move_x = self.dash_dx * dt
            move_y = self.dash_dy * dt
            self.dash_timer -= dt
            if self.dash_timer <= 0.0:
                self.is_dashing = False
        elif self.is_wall_crouch:
            move_x = 0.0
            self.vx = 0.0
            if inputs.y < 0:
                self.vy = -WALL_SLIDE_SPEED
            elif inputs.y > 0:
                self.vy = WALL_SLIDE_SPEED
            else:
                self.vy = WALL_SLIDE_SPEED * 0.4
            move_y = self.vy * dt
        else:
            self.vx += inputs.x * ACCEL * dt
            self.vy += inputs.y * ACCEL * dt
            if not self.on_ground:
                self.vy += SINK_ACCEL * dt
            else:
                # Keep grounded motion crisp without a gravity spike.
                self.vy = min(self.vy, 0.0)

            if self.jump_hold_timer > 0.0 and inputs.jump_held:
                self.vy -= JUMP_HOLD_ACCEL * dt
                self.jump_hold_timer = max(0.0, self.jump_hold_timer - dt)
            elif inputs.jump_released and self.vy < 0.0:
                # Cutting upward velocity early makes short taps feel snappy.
                self.vy *= JUMP_CUT_MULT

            self.vx -= DRAG * self.vx * dt
            self.vy -= DRAG * self.vy * dt

            speed = math.hypot(self.vx, self.vy)
            if speed > MAX_SPEED:
                scale = MAX_SPEED / speed
                self.vx *= scale
                self.vy *= scale

            move_x = self.vx * dt
            move_y = self.vy * dt

        # Collide (prevents phasing through walls)
        resolve_axis(solids, self, move_x, move_y)

        # Auto-stick to walls if airborne + touching wall
        if (not self.on_ground) and (not self.is_dashing) and (not self.is_wall_crouch) and self.wall_kick_lockout <= 0.0:
            if self.wall_left or self.wall_right:
                self.is_wall_crouch = True
                self.stick_side = -1 if self.wall_left else 1
                self.facing = -self.stick_side
                self.vx = 0.0
                self.vy = 0.0

        if self.is_wall_crouch and (not self.wall_left) and (not self.wall_right):
            self.is_wall_crouch = False
            self.stick_side = 0

        # Buffered jump after landing (safe extension point for surface jump pads).
        if self.on_ground and self.jump_buffer_timer > 0.0:
            self._start_jump()


# Example integration:
# movement = PlayerMovement()
# inputs = MovementInput(x=0.0, y=0.0, jump_pressed=False, jump_held=False, jump_released=False, dash_pressed=False)
# movement.update(inputs, dt, solids, resolve_axis)
