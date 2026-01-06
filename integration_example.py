import pygame
from enemies import EnemyManager, DummyPatrolEnemy, ChaserEnemy

# Example usage in your setup/init
enemy_manager = EnemyManager()

enemy_manager.add(DummyPatrolEnemy(pos=(120, 200), left_bound=80, right_bound=240))
enemy_manager.add(DummyPatrolEnemy(pos=(320, 180), left_bound=280, right_bound=420, use_circle=True, radius=14))
enemy_manager.add(ChaserEnemy(pos=(520, 160)))

# Example in your main loop (dt in seconds)
# dt = clock.tick(60) / 1000.0
# world should provide player_pos or player.rect.center
# projectiles should be a list of projectile objects
# camera_offset is a Vector2 or (x, y) tuple

# enemy_manager.update(dt, world, projectiles)
# enemy_manager.draw(screen, camera_offset)
