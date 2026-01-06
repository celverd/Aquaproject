import pygame
from pygame.math import Vector2

# Tuning constants (feel + balance)
DEFAULT_MAX_SPEED = 160.0  # caps enemy top speed for controllable feel
DEFAULT_ACCEL = 320.0  # how quickly enemies reach target speed
DEFAULT_DRAG = 4.0  # underwater inertia; higher = snappier stop
DEFAULT_HEALTH = 3  # baseline durability
DEFAULT_DAMAGE_FLASH_TIME = 0.08  # seconds enemy flashes after hit
DEFAULT_KNOCKBACK_STRENGTH = 220.0  # impulse magnitude applied on damage
DEFAULT_GRAVITY = 0.0  # optional; set >0 for seabed/platform sections

DUMMY_PATROL_SPEED = 80.0  # cruising speed for patrol movement
DUMMY_PATROL_ACCEL = 240.0  # how fast patrols reach target speed
CHASER_MAX_SPEED = 120.0  # max speed for chaser tracking
CHASER_ACCEL = 260.0  # acceleration toward player
CHASER_DRAG = 5.0  # drag for smooth slowdown when player stops

COLOR_ENEMY = (70, 170, 255)
COLOR_ENEMY_HURT = (255, 120, 120)


class BaseEnemy:
    def __init__(
        self,
        pos,
        size=(24, 24),
        use_circle=False,
        radius=12,
        health=DEFAULT_HEALTH,
        max_speed=DEFAULT_MAX_SPEED,
        accel=DEFAULT_ACCEL,
        drag=DEFAULT_DRAG,
        gravity=DEFAULT_GRAVITY,
    ):
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.health = health
        self.alive = True

        self.max_speed = max_speed
        self.accel = accel
        self.drag = drag
        self.gravity = gravity

        self.use_circle = use_circle
        self.radius = radius
        self.size = Vector2(size)
        self.hitbox = pygame.Rect(0, 0, int(self.size.x), int(self.size.y))
        self._sync_hitbox()

        self.damage_flash_time = DEFAULT_DAMAGE_FLASH_TIME
        self._hurt_timer = 0.0

    def _sync_hitbox(self):
        if self.use_circle:
            self.hitbox.center = (int(self.pos.x), int(self.pos.y))
        else:
            self.hitbox.topleft = (int(self.pos.x), int(self.pos.y))

    def update(self, dt, world):
        self._apply_physics(dt)
        self._sync_hitbox()
        if self._hurt_timer > 0.0:
            self._hurt_timer = max(0.0, self._hurt_timer - dt)

    def _apply_physics(self, dt):
        if self.gravity:
            self.vel.y += self.gravity * dt

        if self.drag > 0.0:
            drag_factor = max(0.0, 1.0 - self.drag * dt)
            self.vel *= drag_factor

        if self.vel.length_squared() > self.max_speed * self.max_speed:
            self.vel.scale_to_length(self.max_speed)

        self.pos += self.vel * dt

    def draw(self, surface, camera_offset):
        offset = Vector2(camera_offset)
        color = COLOR_ENEMY_HURT if self._hurt_timer > 0.0 else COLOR_ENEMY
        if self.use_circle:
            center = (self.pos - offset).elementwise().round()
            pygame.draw.circle(surface, color, (int(center.x), int(center.y)), self.radius, 2)
        else:
            rect = self.hitbox.move(-offset.x, -offset.y)
            pygame.draw.rect(surface, color, rect, 2)

    def take_damage(self, amount, knockback_vec=None, source_pos=None):
        if not self.alive:
            return
        self.health -= amount
        self._hurt_timer = self.damage_flash_time

        if knockback_vec is None and source_pos is not None:
            direction = Vector2(self.pos) - Vector2(source_pos)
            if direction.length_squared() > 0:
                direction = direction.normalize()
                knockback_vec = direction * DEFAULT_KNOCKBACK_STRENGTH

        if knockback_vec is not None:
            self.apply_impulse(knockback_vec)

        if self.health <= 0:
            self.alive = False
            self.on_death()

    def apply_impulse(self, vec):
        self.vel += Vector2(vec)

    def on_death(self):
        pass

    # --- Collision helpers ---
    def check_collision_with_projectiles(self, projectiles):
        for proj in projectiles:
            if not getattr(proj, "alive", True):
                continue
            if _projectile_hits_enemy(proj, self):
                damage = getattr(proj, "damage", 1)
                source_pos = _projectile_pos(proj)
                self.take_damage(damage, source_pos=source_pos)
                if hasattr(proj, "alive"):
                    proj.alive = False


def _projectile_pos(proj):
    if hasattr(proj, "pos"):
        return Vector2(proj.pos)
    if hasattr(proj, "rect"):
        rect = proj.rect() if callable(proj.rect) else proj.rect
        return Vector2(rect.center)
    return Vector2(0, 0)


def _projectile_radius(proj):
    if hasattr(proj, "radius"):
        return proj.radius
    return None


def _projectile_rect(proj):
    if hasattr(proj, "rect"):
        return proj.rect() if callable(proj.rect) else proj.rect
    if hasattr(proj, "pos") and hasattr(proj, "size"):
        pos = Vector2(proj.pos)
        size = Vector2(proj.size)
        return pygame.Rect(int(pos.x), int(pos.y), int(size.x), int(size.y))
    return None


def _projectile_hits_enemy(proj, enemy):
    proj_radius = _projectile_radius(proj)
    if proj_radius is not None:
        proj_center = _projectile_pos(proj)
        if enemy.use_circle:
            distance = proj_center.distance_to(enemy.pos)
            return distance <= (proj_radius + enemy.radius)
        rect = enemy.hitbox
        return rect.collidepoint(proj_center.x, proj_center.y)

    proj_rect = _projectile_rect(proj)
    if proj_rect is None:
        return False

    if enemy.use_circle:
        closest_x = max(proj_rect.left, min(enemy.pos.x, proj_rect.right))
        closest_y = max(proj_rect.top, min(enemy.pos.y, proj_rect.bottom))
        distance = Vector2(closest_x, closest_y).distance_to(enemy.pos)
        return distance <= enemy.radius
    return enemy.hitbox.colliderect(proj_rect)


class DummyPatrolEnemy(BaseEnemy):
    def __init__(self, pos, left_bound, right_bound, **kwargs):
        super().__init__(pos, **kwargs)
        self.left_bound = left_bound
        self.right_bound = right_bound
        self.patrol_speed = DUMMY_PATROL_SPEED
        self.patrol_accel = DUMMY_PATROL_ACCEL
        self.direction = 1

    def update(self, dt, world):
        if self.pos.x <= self.left_bound:
            self.direction = 1
        elif self.pos.x >= self.right_bound:
            self.direction = -1

        target_vx = self.direction * self.patrol_speed
        dv = target_vx - self.vel.x
        max_delta = self.patrol_accel * dt
        dv = max(-max_delta, min(max_delta, dv))
        self.vel.x += dv

        super().update(dt, world)


class ChaserEnemy(BaseEnemy):
    def __init__(self, pos, **kwargs):
        kwargs.setdefault("max_speed", CHASER_MAX_SPEED)
        kwargs.setdefault("accel", CHASER_ACCEL)
        kwargs.setdefault("drag", CHASER_DRAG)
        super().__init__(pos, **kwargs)

    def update(self, dt, world):
        target = _world_player_pos(world)
        if target is not None:
            direction = Vector2(target) - self.pos
            if direction.length_squared() > 0:
                desired = direction.normalize() * self.accel
                self.vel += desired * dt

        super().update(dt, world)


def _world_player_pos(world):
    if world is None:
        return None
    if hasattr(world, "player_pos"):
        return Vector2(world.player_pos)
    if hasattr(world, "player") and hasattr(world.player, "rect"):
        return Vector2(world.player.rect.center)
    if hasattr(world, "player") and hasattr(world.player, "pos"):
        return Vector2(world.player.pos)
    return None


class EnemyManager:
    def __init__(self):
        self.enemies = []

    def add(self, enemy):
        self.enemies.append(enemy)

    def update(self, dt, world, projectiles=None):
        projectiles = projectiles or []
        for enemy in self.enemies:
            enemy.update(dt, world)
            if enemy.alive:
                enemy.check_collision_with_projectiles(projectiles)
        self.cleanup_dead()

    def draw(self, surface, camera_offset=(0, 0)):
        for enemy in self.enemies:
            enemy.draw(surface, camera_offset)

    def cleanup_dead(self):
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]
