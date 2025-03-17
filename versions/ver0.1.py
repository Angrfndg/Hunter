import pygame
import random
import math
import numpy as np
import os
import json
import threading

# Initialize Pygame
pygame.init()

# Debug print function
def debug_print(message):
    """Print debug messages if DEBUG is enabled"""
    # Uncomment the line below to enable debug prints
    print(message)

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
WORLD_WIDTH = 9000  # Increased from 3000 to 9000
WORLD_HEIGHT = 9000  # Increased from 3000 to 9000
MEDKIT_SPAWN_CHANCE = 0.5  # Increased from 0.1 to 0.5 (50% chance)

# Display flags for better performance
DISPLAY_FLAGS = pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.SCALED

# Grid and Pathfinding Constants
GRID_SIZE = 50  # Keep at 50 for better performance
PATHFINDING_UPDATE_RATE = 2000  # Keep at 2000ms
PATH_SMOOTHING_DISTANCE = 20  # Keep at 20 for smoother movement
MAX_PATH_LENGTH = 20  # Maximum number of points in a path
MAX_PATH_CACHE_SIZE = 1000  # Maximum number of cached paths
PATH_CACHE = {}  # Cache for paths

# Coordinate Grid Constants
COORD_GRID_SIZE = 1000  # Size of each grid cell (9x9 grid)
COORD_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
COORD_NUMBERS = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

# Spawn squares for enemies defined using coordinate grid
SPAWN_SQUARES = ['i9', 'e3', 'e6', 'c4', 'h3', 'e5', 'i1', 'i7', 'd2', 'f7', 'f3', 'f4', 'f5', 'f6']

# Add new constants for optimization
CACHE_CLEANUP_INTERVAL = 10000  # Clean path cache every 10 seconds
MAX_ACTIVE_PATHS = 50  # Maximum number of active paths to store
PATH_REUSE_DISTANCE = 100  # Distance within which to reuse existing paths

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)
BRIGHT_YELLOW = (255, 255, 50)  # Brighter yellow for projectiles

# Game States
MENU = 0
MENU_TUTORIAL = 1  # Tutorial accessed from main menu
PLAYING = 2
GAME_OVER = 3
PAUSED = 4
INGAME_TUTORIAL = 5  # Tutorial accessed during gameplay

# Weapon Types
WEAPONS = {
    "pistol": {"damage": 1, "fire_rate": 0.5, "ammo": float('inf'), "color": BRIGHT_YELLOW},  # 0.5 shots per second (slower)
    "smg": {"damage": 1, "fire_rate": 10, "ammo": 300, "color": BRIGHT_YELLOW},             # 10 shots per second
    "assault_rifle": {"damage": 2, "fire_rate": 5, "ammo": 200, "color": BRIGHT_YELLOW},    # 5 shots per second
    "shotgun": {"damage": 1, "fire_rate": 1, "ammo": 50, "color": BRIGHT_YELLOW},           # 1 shot per second
    "rocket_launcher": {"damage": 100, "fire_rate": 0.5, "ammo": 20, "color": BRIGHT_YELLOW} # 1 shot every 2 seconds
}

# Enemy Types
ENEMY_TYPES = {
    "standard": {"health": 1, "damage": 0.33, "color": RED, "symbol": "●", "collision_rate": 1.0},  # 1 hit per second
    "shooter": {"health": 1, "damage": 1, "color": BLUE, "symbol": "▲", "collision_rate": 1.0},
    "assault": {"health": 1, "damage": 6.67, "color": ORANGE, "symbol": "★", "collision_rate": 1.0},
    "officer": {"health": 10, "damage": 1, "color": PURPLE, "symbol": "◆", "collision_rate": 1.0}
}

# Status Effects
STATUS_EFFECTS = {
    "idle": {"duration": 5000, "warning_duration": 15000},  # 15s warning, 5s to despawn
    "attacking": {"duration": -1},  # -1 means indefinite until cancelled
    "stunned": {"duration": 2000},
    "burning": {"duration": 5000, "damage": 1},
    "frozen": {"duration": 3000, "move_speed_multiplier": 0.5}
}

class Weapon:
    def __init__(self, weapon_type):
        self.type = weapon_type
        self.damage = WEAPONS[weapon_type]["damage"]
        self.fire_rate = WEAPONS[weapon_type]["fire_rate"]
        self.ammo = WEAPONS[weapon_type]["ammo"]
        self.color = WEAPONS[weapon_type]["color"]
        self.last_shot = 0
        # Convert shots per second to milliseconds between shots
        self.shot_delay = int(1000.0 * (1.0 / self.fire_rate)) if self.fire_rate > 0 else float('inf')

    def can_shoot(self, current_time):
        return current_time - self.last_shot >= self.shot_delay and self.ammo > 0

    def shoot(self, current_time):
        if self.can_shoot(current_time):
            self.last_shot = current_time
            if self.ammo != float('inf'):
                self.ammo -= 1
            return True
        return False

class Player(pygame.sprite.Sprite):
    def __init__(self, game):
        super().__init__()
        # Create a human-like icon with alpha channel
        self.image = pygame.Surface((30, 30), pygame.SRCALPHA)
        
        # Draw head (circle)
        pygame.draw.circle(self.image, CYAN, (15, 10), 8)
        
        # Draw body (rectangle)
        pygame.draw.rect(self.image, CYAN, (12, 18, 6, 12))
        
        # Draw legs (two rectangles)
        pygame.draw.rect(self.image, CYAN, (10, 30, 4, 8))
        pygame.draw.rect(self.image, CYAN, (16, 30, 4, 8))
        
        # Draw arms (two rectangles)
        pygame.draw.rect(self.image, CYAN, (8, 20, 4, 8))
        pygame.draw.rect(self.image, CYAN, (18, 20, 4, 8))
        
        self.rect = self.image.get_rect()
        # Find valid spawn position
        x, y = game.map.find_valid_spawn_position(30, 30)
        self.rect.center = (x + 15, y + 15)
        
        # Movement and combat properties
        self.speed = 8
        self.health = 100
        self.stored_medkits = 0
        self.max_medkits = 5
        self.collision_rate = 1.0
        self.last_collision = 0
        self.collision_cooldown = int(1000 / self.collision_rate)
        self.last_medkit_use = 0
        self.medkit_cooldown = 1000  # 1 second cooldown between medkit uses
        
        # Weapon system
        self.weapons = {
            "pistol": Weapon("pistol"),
            "smg": Weapon("smg"),
            "assault_rifle": Weapon("assault_rifle"),
            "shotgun": Weapon("shotgun"),
            "rocket_launcher": Weapon("rocket_launcher")
        }
        self.current_weapon = "pistol"
        
        # Cache for movement calculations
        self._dx = 0
        self._dy = 0
        self._old_x = 0
        self._old_y = 0

    def use_medkit(self):
        current_time = pygame.time.get_ticks()
        if (self.stored_medkits > 0 and 
            current_time - self.last_medkit_use >= self.medkit_cooldown and 
            self.health < 100):
            self.health = min(100, self.health + 50)  # Heal 50 HP, but don't exceed 100
            self.stored_medkits -= 1
            self.last_medkit_use = current_time
        
    def update(self, game):
        # Store old position for collision detection
        self._old_x = self.rect.x
        self._old_y = self.rect.y
        
        # Get keyboard input
        keys = pygame.key.get_pressed()
        self._dx = 0
        self._dy = 0
        
        # Use regular key codes for WASD keys
        if keys[pygame.K_a]:  # Left
            self._dx = -self.speed
        if keys[pygame.K_d]:  # Right
            self._dx = self.speed
        if keys[pygame.K_w]:  # Up
            self._dy = -self.speed
        if keys[pygame.K_s]:  # Down
            self._dy = self.speed
            
        # Try moving horizontally first
        if self._dx != 0:
            self.rect.x += self._dx
            if game.map.check_collision(self):
                self.rect.x = self._old_x
                # Try sliding vertically if there's vertical movement
                if self._dy != 0:
                    self.rect.y += self._dy
                    if game.map.check_collision(self):
                        self.rect.y = self._old_y
        
        # Try moving vertically if we haven't already
        if self._dy != 0 and (self._dx == 0 or self.rect.y == self._old_y):
            self.rect.y += self._dy
            if game.map.check_collision(self):
                self.rect.y = self._old_y
                # Try sliding horizontally if there's horizontal movement
                if self._dx != 0:
                    self.rect.x += self._dx
                    if game.map.check_collision(self):
                        self.rect.x = self._old_x

        # Keep player within world bounds
        self.rect.clamp_ip(pygame.Rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT))

class BulletPool:
    """Object pool for bullets to reduce memory allocation/deallocation overhead"""
    def __init__(self, initial_size=100):
        self.available_bullets = []
        self.active_bullets = set()
        
        # Pre-allocate bullet objects
        for _ in range(initial_size):
            bullet = Bullet(0, 0, 0, 0, "pistol", 0)
            bullet.active = False
            self.available_bullets.append(bullet)
    
    def get_bullet(self, start_x, start_y, target_x, target_y, weapon_type, damage):
        """Get a bullet from the pool or create a new one if needed"""
        if self.available_bullets:
            bullet = self.available_bullets.pop()
        else:
            # Create a new bullet if pool is empty
            bullet = Bullet(0, 0, 0, 0, "pistol", 0)
            
        # Reset/Initialize bullet
        bullet.rect.x = start_x
        bullet.rect.y = start_y
        bullet.start_x = start_x
        bullet.start_y = start_y
        bullet.target_x = target_x
        bullet.target_y = target_y
        bullet.weapon_type = weapon_type
        bullet.damage = damage
        bullet.active = True
        bullet.has_hit = False
        bullet.age = 0
        
        # Calculate direction vector once
        dx = target_x - start_x
        dy = target_y - start_y
        dist = max(1, math.sqrt(dx * dx + dy * dy))  # Avoid division by zero
        bullet.dx = (dx / dist) * bullet.speed
        bullet.dy = (dy / dist) * bullet.speed
        
        # Update image based on weapon type
        bullet.update_image()
        
        # Add to active bullets
        self.active_bullets.add(bullet)
        return bullet
    
    def return_bullet(self, bullet):
        """Return a bullet to the pool"""
        if bullet in self.active_bullets:
            self.active_bullets.remove(bullet)
        
        bullet.active = False
        self.available_bullets.append(bullet)

class Bullet(pygame.sprite.Sprite):
    def __init__(self, start_x, start_y, target_x, target_y, weapon_type="pistol", damage=10):
        super().__init__()
        self.image = pygame.Surface((5, 5))
        self.image.fill((255, 255, 0))
        self.rect = self.image.get_rect()
        self.rect.x = start_x
        self.rect.y = start_y
        self.start_x = start_x
        self.start_y = start_y
        self.target_x = target_x
        self.target_y = target_y
        self.weapon_type = weapon_type
        self.damage = damage
        self.speed = 15
        self.has_hit = False
        self.active = True
        self.age = 0
        self.max_age = 5000  # 5 seconds max lifetime to prevent runaway bullets
        
        # Pre-calculate direction for better performance
        dx = target_x - start_x
        dy = target_y - start_y
        dist = max(1, math.sqrt(dx * dx + dy * dy))  # Avoid division by zero
        self.dx = (dx / dist) * self.speed
        self.dy = (dy / dist) * self.speed
        
        # Update image based on weapon type
        self.update_image()
    
    def update_image(self):
        """Update bullet appearance based on weapon type"""
        if self.weapon_type == "pistol":
            self.image = pygame.Surface((5, 5))
            self.image.fill((255, 255, 0))
        elif self.weapon_type == "shotgun":
            self.image = pygame.Surface((4, 4))
            self.image.fill((255, 165, 0))
        elif self.weapon_type == "smg":
            self.image = pygame.Surface((3, 3))
            self.image.fill((0, 255, 255))
        elif self.weapon_type == "rifle":
            self.image = pygame.Surface((4, 4))
            self.image.fill((255, 0, 0))
        elif self.weapon_type == "rocket":
            self.image = pygame.Surface((8, 8))
            self.image.fill((255, 0, 0))
        
        self.rect = self.image.get_rect()
        self.rect.x = self.rect.x
        self.rect.y = self.rect.y
    
    def update(self):
        """Update bullet position and check lifetime"""
        if not self.active:
            return
            
        self.rect.x += self.dx
        self.rect.y += self.dy
        
        self.age += 1
        
        # Deactivate if bullet exceeds max age
        if self.age > self.max_age:
            self.active = False

class Explosion(pygame.sprite.Sprite):
    def __init__(self, x, y, radius, damage):
        super().__init__()
        # Create a surface large enough for both inner and outer explosion
        self.image = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        
        # Draw outer explosion (50 pixels)
        pygame.draw.circle(self.image, (255, 165, 0, 100), (radius * 2, radius * 2), 50)
        # Draw inner explosion (25 pixels)
        pygame.draw.circle(self.image, (255, 165, 0, 180), (radius * 2, radius * 2), 25)
        
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        self.radius = radius
        self.damage = damage
        self.lifetime = 30  # frames
        self.age = 0

    def update(self):
        self.age += 1
        if self.age >= self.lifetime:
            self.kill()

class AmmoPickup(pygame.sprite.Sprite):
    def __init__(self, x, y, weapon_type):
        super().__init__()
        self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
        self.weapon_type = weapon_type
        
        # Draw ammo box
        pygame.draw.rect(self.image, YELLOW, (0, 0, 20, 20))
        pygame.draw.rect(self.image, BLACK, (0, 0, 20, 20), 2)  # Border
        
        # Add weapon-specific icon
        if weapon_type == "smg":
            # Draw SMG icon (bullet spray)
            for i in range(3):
                pygame.draw.circle(self.image, BLACK, (10 + i*3, 10 - i*3), 2)
        elif weapon_type == "assault_rifle":
            # Draw rifle icon (larger bullets)
            pygame.draw.rect(self.image, BLACK, (7, 5, 6, 10))
        elif weapon_type == "shotgun":
            # Draw shotgun icon (spread pattern)
            for i in range(3):
                pygame.draw.circle(self.image, BLACK, (10, 10), 2)
                pygame.draw.circle(self.image, BLACK, (7, 7), 2)
                pygame.draw.circle(self.image, BLACK, (13, 13), 2)
        elif weapon_type == "rocket_launcher":
            # Draw rocket icon
            pygame.draw.rect(self.image, BLACK, (7, 5, 6, 12))
            pygame.draw.polygon(self.image, BLACK, [(7, 5), (13, 5), (10, 2)])
        
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        
        # Ammo amount per pickup
        self.ammo_amounts = {
            "smg": 50,
            "assault_rifle": 30,
            "shotgun": 10,
            "rocket_launcher": 3
        }
        self.ammo_amount = self.ammo_amounts.get(weapon_type, 0)

class ExplosiveBarrel(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((30, 30), pygame.SRCALPHA)
        # Draw barrel
        pygame.draw.rect(self.image, (139, 69, 19), (0, 0, 30, 30))  # Brown base
        pygame.draw.rect(self.image, RED, (5, 5, 20, 20))  # Red warning symbol
        pygame.draw.rect(self.image, (139, 69, 19), (0, 0, 30, 30), 2)  # Border
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.health = 1  # One hit to explode

class Enemy(pygame.sprite.Sprite):
    def __init__(self, game, x, y, enemy_type="standard"):
        super().__init__()
        self.type = enemy_type
        self.health = ENEMY_TYPES[enemy_type]["health"]
        self.damage = ENEMY_TYPES[enemy_type]["damage"]
        self.color = ENEMY_TYPES[enemy_type]["color"]
        self.collision_rate = ENEMY_TYPES[enemy_type]["collision_rate"]
        self.last_collision = 0
        self.collision_cooldown = int(1000 / self.collision_rate)  # Convert rate to milliseconds
        
        # Create surface with colored square
        self.image = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.rect(self.image, self.color, (0, 0, 30, 30))
        
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.speed = 3 if enemy_type != "standard" else 4  # Standard enemies are faster
        self.last_shot = 0
        self.last_attack = 0
        self.shot_delay = 1000
        self.attack_delay = 1000  # 1 second between melee attacks
        self.max_fire_range = 300  # For shooter type
        self.melee_range = 50  # Standard melee range
        self.screen_buffer = 50
        
        # Status system
        self.active_statuses = {}  # {status_name: {"start_time": time, "duration": duration}}
        self.base_speed = self.speed
        self.last_position = (x, y)
        self.last_position_check = pygame.time.get_ticks()
        self.position_check_interval = 500
        
        # Path tracking attributes
        self.path = []
        self.target_cell = None
        self.last_path_update = pygame.time.get_ticks()
        self.path_update_interval = 2000  # ms
        self.visible_path_update_interval = 500  # ms for on-screen enemies
        self.last_player_pos = (0, 0)  # Store last player position when path was calculated
        self.path_recalc_distance = 100  # Distance in pixels player must move to trigger recalc
        
        self.stuck_threshold = 500
        self.stuck_count = 0
        self.max_stuck_attempts = 3
        self.last_valid_position = (x, y)
        self.time_since_progress = 0
        self.path_finding_delay = random.randint(0, 1000)
        self.damaged_by_explosion = False
        self.collision_count = 0  # Add back collision tracking
        self.max_collisions = 5
        
        # Add despawn timer
        self.stuck_time = 0
        self.despawn_threshold = 5000
        self.path_reuse_threshold = 200
        self.last_path_pos = None

    def apply_status(self, status_name):
        current_time = pygame.time.get_ticks()
        if status_name in STATUS_EFFECTS:
            # Don't apply idle if already attacking
            if status_name == "idle" and self.has_status("attacking"):
                return
            
            # Remove conflicting statuses
            if status_name == "attacking":
                self.remove_status("idle")
            
            self.active_statuses[status_name] = {
                "start_time": current_time,
                "duration": STATUS_EFFECTS[status_name]["duration"]
            }
            
            # Apply status effects
            if status_name == "frozen":
                self.speed = self.base_speed * STATUS_EFFECTS[status_name]["move_speed_multiplier"]

    def remove_status(self, status_name):
        if status_name in self.active_statuses:
            del self.active_statuses[status_name]
            # Reset effects
            if status_name == "frozen":
                self.speed = self.base_speed

    def has_status(self, status_name):
        return status_name in self.active_statuses

    def update_statuses(self):
        current_time = pygame.time.get_ticks()
        statuses_to_remove = []
        
        for status_name, status_data in self.active_statuses.items():
            if status_data["duration"] > 0:  # Skip indefinite statuses
                elapsed = current_time - status_data["start_time"]
                if status_name == "idle":
                    warning_duration = STATUS_EFFECTS["idle"]["warning_duration"]
                    if elapsed >= warning_duration:  # After warning duration, remove idle status
                        statuses_to_remove.append(status_name)
                        self.kill()  # Remove the enemy after idle timeout
                elif elapsed >= status_data["duration"]:
                    statuses_to_remove.append(status_name)
                elif status_name == "burning":
                    # Apply burning damage every second
                    if elapsed % 1000 < 50:  # Check within 50ms window
                        self.health -= STATUS_EFFECTS["burning"]["damage"]
        
        for status in statuses_to_remove:
            self.remove_status(status)

    def update(self, player, game, camera_x=0, camera_y=0):
        current_time = pygame.time.get_ticks()
        self.update_statuses()
        
        # Calculate distance to player
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        dist_to_player = math.sqrt(dx * dx + dy * dy)
        
        # Check if enemy is visible on screen
        screen_x = self.rect.x - camera_x
        screen_y = self.rect.y - camera_y
        is_near_screen = (-500 <= screen_x <= SCREEN_WIDTH + 500 and
                         -500 <= screen_y <= SCREEN_HEIGHT + 500)
        
        # Check if position has changed
        current_pos = (self.rect.x, self.rect.y)
        if current_time - self.last_position_check > self.position_check_interval:
            if current_pos == self.last_position and not self.has_status("attacking"):
                if not self.has_status("idle"):
                    self.apply_status("idle")
            else:
                if self.has_status("idle"):
                    self.remove_status("idle")
                self.last_position = current_pos
            self.last_position_check = current_time

        # Handle shooting behavior for shooter type
        if self.type == "shooter" and is_near_screen:
            if dist_to_player <= self.max_fire_range and current_time - self.last_shot >= self.shot_delay:
                if not game.map.check_line_of_sight(self.rect.centerx, self.rect.centery,
                                                  player.rect.centerx, player.rect.centery):
                    self.apply_status("attacking")
                    self.last_shot = current_time
                    return True
        
        # Handle melee attacks for non-shooter types
        elif dist_to_player <= self.melee_range and self.type != "standard":
            if current_time - self.last_attack >= self.attack_delay:
                self.apply_status("attacking")
                self.last_attack = current_time
                if self.type == "assault":
                    player.health -= 15
                elif self.type == "officer":
                    player.health -= 5
                else:
                    player.health -= self.damage * 0.2
            return False
        
        # Update path and movement only if near screen or enough time has passed
        if not self.has_status("frozen"):
            should_update_path = (
                self.path is None or
                current_time - self.last_path_update > self.visible_path_update_interval
            )
            
            # Check if we can reuse the current path
            if self.path and self.last_path_pos:
                player_moved = math.sqrt(
                    (player.rect.centerx - self.last_path_pos[0]) ** 2 +
                    (player.rect.centery - self.last_path_pos[1]) ** 2
                ) > self.path_reuse_threshold
                should_update_path = should_update_path and player_moved
            
            if should_update_path:
                self.path = game.map.find_path(
                    self.rect.centerx, self.rect.centery,
                    player.rect.centerx, player.rect.centery
                )
                self.path_index = 0
                self.last_path_update = current_time
                self.last_path_pos = (player.rect.centerx, player.rect.centery)
            
            # Move along path if available
            if self.path and self.path_index < len(self.path):
                target_x, target_y = self.path[self.path_index]
                dx = target_x - self.rect.centerx
                dy = target_y - self.rect.centery
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist < PATH_SMOOTHING_DISTANCE:
                    self.path_index += 1
                elif dist != 0:
                    move_x = (dx / dist) * self.speed
                    move_y = (dy / dist) * self.speed
                    
                    # Store old position for collision detection
                    old_x = self.rect.x
                    old_y = self.rect.y
                    
                    # Try moving horizontally first
                    self.rect.x += move_x
                    if game.map.check_collision(self):
                        self.rect.x = old_x
                        # Try moving vertically
                        self.rect.y += move_y
                        if game.map.check_collision(self):
                            self.rect.y = old_y
                    else:
                        # If horizontal movement succeeded, try vertical
                        self.rect.y += move_y
                        if game.map.check_collision(self):
                            self.rect.y = old_y
        
        # Keep enemy within world bounds
        self.rect.clamp_ip(pygame.Rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT))
        return False

    def explode(self, game):
        if self.type == "assault":
            game.create_explosion(self.rect.centerx, self.rect.centery, self.damage)  # Use base damage (6.67)
            return True
        return False

    def find_alternative_path(self, player, game):
        # Try multiple angles for alternative paths
        angles = [45, -45, 90, -90, 135, -135]
        distance = 400  # Increased distance for alternative paths
        
        for angle in angles:
            rad = math.radians(angle)
            offset_x = math.cos(rad) * distance
            offset_y = math.sin(rad) * distance
            
            target_x = player.rect.centerx + offset_x
            target_y = player.rect.centery + offset_y
            
            # Ensure target is within world bounds
            target_x = max(0, min(WORLD_WIDTH, target_x))
            target_y = max(0, min(WORLD_HEIGHT, target_y))
            
            new_path = game.map.find_path(
                self.rect.centerx, self.rect.centery,
                target_x, target_y
            )
            
            # Check if path is valid and different from current
            if new_path and (not self.path or new_path != self.path):
                self.path = new_path
                self.path_index = 0
                return True
        return False

    def recalculate_path(self):
        """Separate path calculation into its own method for clarity"""
        if not self.game.player:
            return
            
        # Convert positions to grid coordinates
        start_grid_x = max(0, min(self.game.grid_width - 1, int(self.rect.centerx / TILE_SIZE)))
        start_grid_y = max(0, min(self.game.grid_height - 1, int(self.rect.centery / TILE_SIZE)))
        player_grid_x = max(0, min(self.game.grid_width - 1, int(self.game.player.rect.centerx / TILE_SIZE)))
        player_grid_y = max(0, min(self.game.grid_height - 1, int(self.game.player.rect.centery / TILE_SIZE)))
        
        # Find path to player using A* algorithm
        self.path = self.game.astar.find_path(
            (start_grid_x, start_grid_y),
            (player_grid_x, player_grid_y)
        )
        
        # If path exists, remove the starting position
        if self.path and len(self.path) > 1:
            self.path = self.path[1:]  # Skip the first position (current position)

class Medkit(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
        # Draw a cross symbol
        pygame.draw.rect(self.image, GREEN, (8, 0, 4, 20))  # Vertical line
        pygame.draw.rect(self.image, GREEN, (0, 8, 20, 4))  # Horizontal line
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        # Medkit heals 50 HP when used by the player

class Tree(pygame.sprite.Sprite):
    def __init__(self, x, y, size):
        super().__init__()
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Draw tree trunk (brown)
        trunk_width = size // 3
        trunk_height = size // 2
        trunk_x = (size - trunk_width) // 2
        pygame.draw.rect(self.image, (139, 69, 19), 
                        (trunk_x, size - trunk_height, trunk_width, trunk_height))
        
        # Draw tree crown (dark green circle)
        crown_radius = size // 2
        pygame.draw.circle(self.image, (0, 100, 0), 
                         (size // 2, size // 2), crown_radius)
        
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

class Building(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(GRAY)
        # Add some visual detail
        pygame.draw.rect(self.image, DARK_GRAY, (0, 0, width, 5))  # Top border
        pygame.draw.rect(self.image, DARK_GRAY, (0, height-5, width, 5))  # Bottom border
        pygame.draw.rect(self.image, DARK_GRAY, (0, 0, 5, height))  # Left border
        pygame.draw.rect(self.image, DARK_GRAY, (width-5, 0, 5, height))  # Right border
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.width = width
        self.height = height

class Street(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(DARK_GRAY)
        # Add street lines
        if width > height:  # Horizontal street
            for i in range(0, width, 50):
                pygame.draw.rect(self.image, WHITE, (i, height//2 - 2, 30, 4))
        else:  # Vertical street
            for i in range(0, height, 50):
                pygame.draw.rect(self.image, WHITE, (width//2 - 2, i, 4, 30))
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.width = width
        self.height = height

class Map:
    def __init__(self, load_saved=True):
        self.trees = pygame.sprite.Group()
        self.grid_width = WORLD_WIDTH // GRID_SIZE
        self.grid_height = WORLD_HEIGHT // GRID_SIZE
        self.grid = [[0 for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        self.spawn_points = []
        # Create a surface for pre-rendered trees
        self.tree_surface = pygame.Surface((WORLD_WIDTH, WORLD_HEIGHT), pygame.SRCALPHA)
        
        # Initialize spawn points from predefined squares
        self.initialize_spawn_points()
        
        if load_saved and os.path.exists("map_data.json"):
            self.load_map()
        else:
            self.generate_forest()
            self.save_map()
        
        self.update_grid()
        self.last_cache_cleanup = 0
        self.path_usage_count = {}

    def initialize_spawn_points(self):
        """Initialize spawn points from predefined SPAWN_SQUARES"""
        self.spawn_points = []
        
        for coord in SPAWN_SQUARES:
            if len(coord) == 2:
                letter, number = coord[0].upper(), coord[1]
                # Convert letter and number to grid indices
                if letter in COORD_LETTERS and number in COORD_NUMBERS:
                    letter_idx = COORD_LETTERS.index(letter)
                    number_idx = COORD_NUMBERS.index(number)
                    
                    # Calculate center position of the grid cell
                    x = letter_idx * COORD_GRID_SIZE + COORD_GRID_SIZE // 2
                    y = number_idx * COORD_GRID_SIZE + COORD_GRID_SIZE // 2
                    
                    # Make sure the point is within world bounds
                    x = max(0, min(WORLD_WIDTH - 30, x))
                    y = max(0, min(WORLD_HEIGHT - 30, y))
                    
                    # Find a valid spawn position near this point
                    valid_x, valid_y = self.find_valid_spawn_position(30, 30, center_point=(x, y))
                    self.spawn_points.append((valid_x, valid_y))
    
    def get_closest_spawn_points(self, player_x, player_y, count=3):
        """
        Get the closest spawn points to the player, ensuring they come from different directions
        """
        if not self.spawn_points:
            return []  # Return empty list if no spawn points defined
        
        # Calculate distances and directions from player to each spawn point
        spawn_info = []
        for i, (x, y) in enumerate(self.spawn_points):
            dx = x - player_x
            dy = y - player_y
            distance = math.sqrt(dx * dx + dy * dy)
            # Calculate angle from player to spawn point (in radians)
            angle = math.atan2(dy, dx)
            spawn_info.append({
                'index': i,
                'pos': (x, y),
                'distance': distance,
                'angle': angle,
                'direction': self.get_direction(angle)
            })
        
        # Sort by distance
        spawn_info.sort(key=lambda x: x['distance'])
        
        # Select points from different directions if possible
        selected = []
        used_directions = set()
        
        # First, try to get points from different directions
        for info in spawn_info:
            if len(selected) >= count:
                break
                
            if info['direction'] not in used_directions:
                selected.append(info)
                used_directions.add(info['direction'])
        
        # If we still need more points, add the closest remaining ones
        remaining = [info for info in spawn_info if info not in selected]
        remaining.sort(key=lambda x: x['distance'])
        
        while len(selected) < count and remaining:
            selected.append(remaining.pop(0))
        
        return [info['pos'] for info in selected]
    
    def get_direction(self, angle):
        """Convert angle in radians to cardinal direction (N, NE, E, SE, S, SW, W, NW)"""
        # Normalize angle to [0, 2π)
        angle = angle % (2 * math.pi)
        
        if angle < math.pi/8 or angle >= 15*math.pi/8:
            return 'E'
        elif angle < 3*math.pi/8:
            return 'SE'
        elif angle < 5*math.pi/8:
            return 'S'
        elif angle < 7*math.pi/8:
            return 'SW'
        elif angle < 9*math.pi/8:
            return 'W'
        elif angle < 11*math.pi/8:
            return 'NW'
        elif angle < 13*math.pi/8:
            return 'N'
        else:
            return 'NE'

    def save_map(self):
        """Save tree positions and properties to a JSON file"""
        tree_data = []
        for tree in self.trees:
            tree_data.append({
                'x': tree.rect.x,
                'y': tree.rect.y,
                'size': tree.rect.width  # Since trees are square, width = height = size
            })
        
        with open("map_data.json", 'w') as f:
            json.dump(tree_data, f)
        
        # Save the visual map as well
        self.generate_map_image()

    def load_map(self):
        """Load tree positions and properties from JSON file"""
        try:
            with open("map_data.json", 'r') as f:
                tree_data = json.load(f)
            
            # Clear existing trees
            self.trees.empty()
            self.tree_surface.fill((0, 0, 0, 0))  # Clear the surface
            
            # Recreate trees from saved data
            for data in tree_data:
                tree = Tree(data['x'], data['y'], data['size'])
                self.trees.add(tree)
                # Pre-render tree on the tree surface
                self.tree_surface.blit(tree.image, tree.rect)
            
            return True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading map: {e}")
            return False

    def generate_forest(self):
        # Clear existing trees
        self.trees.empty()
        
        # Reduce number of trees and clusters
        num_trees = 400  # Reduced from 800
        min_tree_size = 40
        max_tree_size = 80
        num_clusters = 15  # Reduced from 30
        cluster_radius = 500
        
        for _ in range(num_clusters):
            center_x = random.randint(0, WORLD_WIDTH)
            center_y = random.randint(0, WORLD_HEIGHT)
            
            trees_in_cluster = random.randint(15, 25)  # Reduced from 20-35
            for _ in range(trees_in_cluster):
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(0, cluster_radius)
                x = center_x + math.cos(angle) * distance
                y = center_y + math.sin(angle) * distance
                
                x = max(0, min(WORLD_WIDTH - max_tree_size, x))
                y = max(0, min(WORLD_HEIGHT - max_tree_size, y))
                
                size = random.randint(min_tree_size, max_tree_size)
                tree = Tree(x, y, size)
                
                if not pygame.sprite.spritecollideany(tree, self.trees):
                    self.trees.add(tree)
                    # Pre-render tree on the tree surface
                    self.tree_surface.blit(tree.image, tree.rect)
        
        # Add some scattered individual trees
        remaining_trees = num_trees - len(self.trees)
        attempts = 0
        while len(self.trees) < num_trees and attempts < 1000:
            size = random.randint(min_tree_size, max_tree_size)
            x = random.randint(0, WORLD_WIDTH - size)
            y = random.randint(0, WORLD_HEIGHT - size)
            
            tree = Tree(x, y, size)
            if not pygame.sprite.spritecollideany(tree, self.trees):
                self.trees.add(tree)
                # Pre-render tree on the tree surface
                self.tree_surface.blit(tree.image, tree.rect)
            attempts += 1

    def update_grid(self):
        # Reset grid
        self.grid = [[0 for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        # Mark trees in grid
        for tree in self.trees:
            start_x = max(0, tree.rect.left // GRID_SIZE)
            end_x = min(self.grid_width - 1, tree.rect.right // GRID_SIZE)
            start_y = max(0, tree.rect.top // GRID_SIZE)
            end_y = min(self.grid_height - 1, tree.rect.bottom // GRID_SIZE)
            
            for x in range(start_x, end_x + 1):
                for y in range(start_y, end_y + 1):
                    self.grid[y][x] = 1

    def world_to_grid(self, x, y):
        return (x // GRID_SIZE, y // GRID_SIZE)

    def grid_to_world(self, x, y):
        return (x * GRID_SIZE + GRID_SIZE // 2, y * GRID_SIZE + GRID_SIZE // 2)

    def get_neighbors(self, x, y):
        neighbors = []
        # Add diagonal directions in addition to cardinal directions
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0), 
                       (1, 1), (1, -1), (-1, 1), (-1, -1)]:
            new_x, new_y = x + dx, y + dy
            if (0 <= new_x < self.grid_width and 
                0 <= new_y < self.grid_height and 
                self.grid[new_y][new_x] == 0):
                # Check if both adjacent cells are free for diagonal movement
                if dx != 0 and dy != 0:
                    if (self.grid[y][new_x] == 0 and 
                        self.grid[new_y][x] == 0):
                        neighbors.append((new_x, new_y))
                else:
                    neighbors.append((new_x, new_y))
        return neighbors

    def cleanup_path_cache(self, current_time):
        if current_time - self.last_cache_cleanup > CACHE_CLEANUP_INTERVAL:
            # Remove least used paths if cache is too large
            if len(PATH_CACHE) > MAX_PATH_CACHE_SIZE:
                sorted_paths = sorted(self.path_usage_count.items(), key=lambda x: x[1])
                paths_to_remove = sorted_paths[:len(PATH_CACHE) - MAX_ACTIVE_PATHS]
                for path_key, _ in paths_to_remove:
                    if path_key in PATH_CACHE:
                        del PATH_CACHE[path_key]
                        del self.path_usage_count[path_key]
            self.last_cache_cleanup = current_time

    def find_path(self, start_x, start_y, end_x, end_y):
        current_time = pygame.time.get_ticks()
        self.cleanup_path_cache(current_time)

        # Convert world coordinates to grid coordinates
        start_grid = self.world_to_grid(start_x, start_y)
        end_grid = self.world_to_grid(end_x, end_y)
        
        # Define cache key at the beginning
        cache_key = (start_grid, end_grid)
        
        # Check for nearby cached paths first
        for existing_key in PATH_CACHE:
            cached_start, cached_end = existing_key
            if (abs(cached_start[0] - start_grid[0]) + abs(cached_start[1] - start_grid[1]) < 2 and
                abs(cached_end[0] - end_grid[0]) + abs(cached_end[1] - end_grid[1]) < 2):
                self.path_usage_count[existing_key] = self.path_usage_count.get(existing_key, 0) + 1
                return PATH_CACHE[existing_key]

        # Rest of the existing pathfinding code
        # Initialize open and closed sets
        open_set = {start_grid}
        closed_set = set()
        came_from = {}
        g_score = {start_grid: 0}
        f_score = {start_grid: self.heuristic(start_grid, end_grid)}
        
        while open_set:
            current = min(open_set, key=lambda x: f_score.get(x, float('inf')))
            
            if current == end_grid:
                path = self.reconstruct_path(came_from, current)
                # Cache the path
                PATH_CACHE[cache_key] = path
                return path
            
            open_set.remove(current)
            closed_set.add(current)
            
            for neighbor in self.get_neighbors(*current):
                if neighbor in closed_set:
                    continue
                
                tentative_g_score = g_score[current] + 1
                
                if neighbor not in open_set:
                    open_set.add(neighbor)
                elif tentative_g_score >= g_score.get(neighbor, float('inf')):
                    continue
                
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + self.heuristic(neighbor, end_grid)
        
        # If no path found, try direct movement
        direct_path = [(start_x, start_y), (end_x, end_y)]
        PATH_CACHE[cache_key] = direct_path
        return direct_path

    def heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def reconstruct_path(self, came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return [self.grid_to_world(x, y) for x, y in path]

    def find_valid_spawn_position(self, width, height, min_distance=None, center_point=None):
        for _ in range(100):
            x = random.randint(0, WORLD_WIDTH - width)
            y = random.randint(0, WORLD_HEIGHT - height)
            
            if center_point and min_distance:
                dx = x - center_point[0]
                dy = y - center_point[1]
                if math.sqrt(dx * dx + dy * dy) < min_distance:
                    continue
            
            if self.is_valid_spawn_position(x, y, width, height):
                return x, y
        
        # Fallback to center if no valid position found
        return WORLD_WIDTH // 2, WORLD_HEIGHT // 2

    def is_valid_spawn_position(self, x, y, width, height):
        temp_sprite = pygame.sprite.Sprite()
        temp_sprite.rect = pygame.Rect(x, y, width, height)
        return not pygame.sprite.spritecollideany(temp_sprite, self.trees)

    def check_collision(self, sprite):
        return pygame.sprite.spritecollideany(sprite, self.trees)

    def draw_coordinate_grid(self, screen, camera_x, camera_y):
        # Draw vertical grid lines and letter labels
        for i, letter in enumerate(COORD_LETTERS):
            x = i * COORD_GRID_SIZE
            screen_x = x - camera_x
            
            if -2 <= screen_x <= SCREEN_WIDTH:
                pygame.draw.line(screen, BLACK, (screen_x, 0), (screen_x, SCREEN_HEIGHT), 2)
                # Draw letter at top
                self.draw_text(screen, letter, 24, BLACK, screen_x + 10, 10)
        
        # Draw horizontal grid lines and number labels
        for i, number in enumerate(COORD_NUMBERS):
            y = i * COORD_GRID_SIZE
            screen_y = y - camera_y
            
            if -2 <= screen_y <= SCREEN_HEIGHT:
                pygame.draw.line(screen, BLACK, (0, screen_y), (SCREEN_WIDTH, screen_y), 2)
                # Draw number at left
                self.draw_text(screen, number, 24, BLACK, 10, screen_y + 10)

    def draw_text(self, screen, text, size, color, x, y):
        font = pygame.font.Font(None, size)
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        text_rect.topleft = (x, y)
        screen.blit(text_surface, text_rect)

    def generate_map_image(self):
        print("Generating map image...")
        # Create a surface for the full map
        map_surface = pygame.Surface((WORLD_WIDTH, WORLD_HEIGHT))
        
        # Draw grass background
        grass_color = (34, 139, 34)  # Forest green
        map_surface.fill(grass_color)
        
        # Draw trees
        for tree in self.trees:
            map_surface.blit(tree.image, tree.rect)
        
        # Draw coordinate grid
        for i, letter in enumerate(COORD_LETTERS):
            x = i * COORD_GRID_SIZE
            pygame.draw.line(map_surface, BLACK, (x, 0), (x, WORLD_HEIGHT), 2)
            self.draw_text(map_surface, letter, 48, BLACK, x + 10, 10)
        
        for i, number in enumerate(COORD_NUMBERS):
            y = i * COORD_GRID_SIZE
            pygame.draw.line(map_surface, BLACK, (0, y), (WORLD_WIDTH, y), 2)
            self.draw_text(map_surface, number, 48, BLACK, 10, y + 10)
        
        # Save the map image
        pygame.image.save(map_surface, "game_map.jpg")
        print("Map image saved successfully.")

    def draw(self, screen, camera_x, camera_y):
        # Draw grass background
        grass_color = (34, 139, 34)  # Forest green
        screen.fill(grass_color)
        
        # Draw coordinate grid
        self.draw_coordinate_grid(screen, camera_x, camera_y)
        
        # Draw the visible portion of the pre-rendered tree surface
        visible_rect = pygame.Rect(camera_x, camera_y, SCREEN_WIDTH, SCREEN_HEIGHT)
        screen.blit(self.tree_surface, (0, 0), visible_rect)

    def check_line_of_sight(self, start_x, start_y, end_x, end_y):
        # Create a temporary sprite to check for collisions along the line
        temp_sprite = pygame.sprite.Sprite()
        temp_sprite.rect = pygame.Rect(0, 0, 4, 4)  # Small collision box
        
        # Calculate direction vector
        dx = end_x - start_x
        dy = end_y - start_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        if distance == 0:
            return True
            
        # Normalize direction
        dx = dx / distance
        dy = dy / distance
        
        # Check points along the line
        steps = int(distance / 20)  # Check every 20 pixels
        for i in range(steps):
            x = start_x + dx * i * 20
            y = start_y + dy * i * 20
            temp_sprite.rect.center = (x, y)
            
            if self.check_collision(temp_sprite):
                return True  # Line of sight is blocked
                
        return False  # Clear line of sight

class SpatialGrid:
    """A spatial partitioning system for efficient collision detection"""
    def __init__(self, world_width, world_height, cell_size=200):
        self.cell_size = cell_size
        self.grid_width = int(world_width / cell_size) + 1
        self.grid_height = int(world_height / cell_size) + 1
        self.grid = {}  # Dictionary to store objects in each cell
        
    def clear(self):
        """Clear all cells in the grid"""
        self.grid = {}
        
    def _get_cell_coords(self, x, y):
        """Convert world coordinates to grid cell coordinates"""
        grid_x = max(0, min(self.grid_width - 1, int(x / self.cell_size)))
        grid_y = max(0, min(self.grid_height - 1, int(y / self.cell_size)))
        return (grid_x, grid_y)
    
    def insert(self, game_object):
        """Insert an object into the grid based on its position"""
        cell = self._get_cell_coords(game_object.rect.centerx, game_object.rect.centery)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append(game_object)
    
    def get_nearby_cells(self, x, y):
        """Get objects from the current cell and adjacent cells"""
        center_cell = self._get_cell_coords(x, y)
        nearby_objects = []
        
        # Check center cell and 8 surrounding cells
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                cell = (center_cell[0] + dx, center_cell[1] + dy)
                if cell in self.grid:
                    nearby_objects.extend(self.grid[cell])
        
        return nearby_objects
        
    def update_object(self, game_object):
        """Update an object's position in the grid"""
        # This would be called when objects move significantly
        # For efficiency, we typically just rebuild the entire grid each frame
        pass

class GameState:
    """Base class for all game states"""
    def __init__(self, game):
        self.game = game
    
    def enter(self):
        """Called when entering this state"""
        pass
    
    def exit(self):
        """Called when exiting this state"""
        pass
    
    def update(self):
        """Update game logic for this state"""
        pass
    
    def draw(self, screen):
        """Draw the game in this state"""
        pass
    
    def handle_event(self, event):
        """Handle events in this state"""
        pass

class MenuState(GameState):
    def enter(self):
        # Reset menu selection
        self.game.menu_selection = 0
        
    def draw(self, screen):
        # Clear screen with WHITE background
        screen.fill(WHITE)
        
        # Draw menu title
        title_font = pygame.font.Font(None, 60)
        title_text = title_font.render("HUNTER", True, YELLOW)
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 100))
        
        # Draw menu options
        menu_options = ["Play", "Tutorial", "Quit"]
        font = pygame.font.Font(None, 40)
        for i, option in enumerate(menu_options):
            color = RED if i == self.game.menu_selection else BLACK
            text = font.render(option, True, color)
            screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 250 + i * 60))
    
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.game.menu_selection = (self.game.menu_selection - 1) % 3
                print(f"Menu selection: {self.game.menu_selection}")  # Debug print
            elif event.key == pygame.K_DOWN:
                self.game.menu_selection = (self.game.menu_selection + 1) % 3
                print(f"Menu selection: {self.game.menu_selection}")  # Debug print
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                print(f"Enter/Space pressed, selection: {self.game.menu_selection}")  # Debug print
                if self.game.menu_selection == 0:  # Play
                    print("Starting game...")  # Debug print
                    self.game.set_state(self.game.playing_state)
                elif self.game.menu_selection == 1:  # Tutorial
                    print("Opening tutorial...")  # Debug print
                    self.game.set_state(self.game.tutorial_state)
                elif self.game.menu_selection == 2:  # Quit
                    print("Quitting game...")  # Debug print
                    self.game.running = False

class PlayingState(GameState):
    def enter(self):
        print("Entering PlayingState")  # Debug print
        # Initialize game or reset game state when entering this state
        self.game.start_game()
        
    def update(self):
        # Update game world, player, enemies, etc.
        self.game.update_game_world()
    
    def draw(self, screen):
        # Draw game world
        self.game.draw_game_world(screen)
    
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                print("Pausing game")  # Debug print
                self.game.set_state(self.game.paused_state)
            # Handle other game input events
            self.game.handle_game_input(event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
            # Handle shooting
            self.game.try_shoot()

class PausedState(GameState):
    def draw(self, screen):
        # Draw game world (dimmed)
        self.game.draw_game_world(screen)
        
        # Draw semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        screen.blit(overlay, (0, 0))
        
        # Draw pause menu
        font = pygame.font.Font(None, 50)
        text = font.render("PAUSED", True, (255, 255, 255))
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 200))
        
        options = ["Resume", "Tutorial", "Quit to Menu"]
        option_font = pygame.font.Font(None, 40)
        for i, option in enumerate(options):
            color = (255, 0, 0) if i == self.game.pause_selection else (255, 255, 255)
            option_text = option_font.render(option, True, color)
            screen.blit(option_text, (SCREEN_WIDTH // 2 - option_text.get_width() // 2, 300 + i * 60))
    
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.game.set_state(self.game.playing_state)
            elif event.key == pygame.K_UP:
                self.game.pause_selection = (self.game.pause_selection - 1) % 3
            elif event.key == pygame.K_DOWN:
                self.game.pause_selection = (self.game.pause_selection + 1) % 3
            elif event.key == pygame.K_RETURN:
                if self.game.pause_selection == 0:  # Resume
                    self.game.set_state(self.game.playing_state)
                elif self.game.pause_selection == 1:  # Tutorial
                    self.game.set_state(self.game.tutorial_state)
                elif self.game.pause_selection == 2:  # Quit to Menu
                    self.game.set_state(self.game.menu_state)

class GameOverState(GameState):
    def draw(self, screen):
        # Draw game over screen
        screen.fill((0, 0, 0))
        
        font = pygame.font.Font(None, 60)
        text = font.render("GAME OVER", True, (255, 0, 0))
        screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 200))
        
        score_font = pygame.font.Font(None, 40)
        score_text = score_font.render(f"Score: {self.game.score}", True, (255, 255, 255))
        screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, 300))
        
        prompt_font = pygame.font.Font(None, 30)
        prompt_text = prompt_font.render("Press ENTER to return to menu", True, (255, 255, 255))
        screen.blit(prompt_text, (SCREEN_WIDTH // 2 - prompt_text.get_width() // 2, 400))
    
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.game.set_state(self.game.menu_state)

class TutorialState(GameState):
    def draw(self, screen):
        # Draw tutorial screen
        screen.fill((0, 0, 0))
        
        title_font = pygame.font.Font(None, 50)
        title_text = title_font.render("TUTORIAL", True, (255, 255, 255))
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 50))
        
        # Instructions
        instructions = [
            "Move: WASD keys",
            "Aim: Mouse",
            "Shoot: Left Mouse Button",
            "Switch Weapon: Mouse Wheel or 1-5 keys",
            "Use Medkit: M key",
            "Pause: ESC key",
            "",
            "Survive as long as possible!",
            "Collect ammo and medkits to stay alive.",
            "Defeat enemies to earn points."
        ]
        
        font = pygame.font.Font(None, 30)
        for i, instruction in enumerate(instructions):
            text = font.render(instruction, True, (255, 255, 255))
            screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 120 + i * 40))
        
        prompt_font = pygame.font.Font(None, 25)
        prompt_text = prompt_font.render("Press ESC to return", True, (255, 255, 255))
        screen.blit(prompt_text, (SCREEN_WIDTH // 2 - prompt_text.get_width() // 2, 550))
    
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            # Return to previous state
            self.game.set_state(self.game.previous_state)

class WorldBoundary:
    """Manages world boundaries and prevents entities from going out of bounds"""
    def __init__(self, width, height, buffer=50):
        self.width = width
        self.height = height
        self.buffer = buffer  # Buffer zone around the world
        self.rect = pygame.Rect(-buffer, -buffer, width + 2*buffer, height + 2*buffer)
        
    def contains(self, entity):
        """Check if an entity is within the world boundaries"""
        if not hasattr(entity, 'rect'):
            return False
        return self.rect.contains(entity.rect)
        
    def clamp(self, entity):
        """Constrain an entity to remain within the world boundaries"""
        if not hasattr(entity, 'rect'):
            return
        entity.rect.clamp_ip(pygame.Rect(0, 0, self.width, self.height))
    
    def is_in_playable_area(self, x, y):
        """Check if a position is within the playable area"""
        return 0 <= x < self.width and 0 <= y < self.height

class SafeReference:
    """A wrapper for references that might be None to prevent NullPointerExceptions"""
    def __init__(self, obj=None):
        self.obj = obj
        
    def get(self):
        """Get the referenced object or None"""
        return self.obj
        
    def is_null(self):
        """Check if reference is null"""
        return self.obj is None
        
    def set(self, obj):
        """Set the referenced object"""
        self.obj = obj
        
    def clear(self):
        """Clear the reference"""
        self.obj = None
        
    def __bool__(self):
        """Allow direct boolean check: if safe_ref:"""
        return self.obj is not None

class Game:
    def __init__(self, screen_width=1536, screen_height=1020):
        # Initialize pygame display with hardware acceleration and double buffering
        self.screen = pygame.display.set_mode((screen_width, screen_height), DISPLAY_FLAGS)
        pygame.display.set_caption("Hunter")
        
        # Create a surface for the game world
        self.world_surface = pygame.Surface((WORLD_WIDTH, WORLD_HEIGHT), pygame.SRCALPHA)
        
        # Create surfaces for UI elements with alpha channel
        self.hud_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        self.weapon_surface = pygame.Surface((200, 100), pygame.SRCALPHA)
        self.medkit_surface = pygame.Surface((200, 30), pygame.SRCALPHA)
        
        # Initialize sprite groups with optimized settings
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.explosions = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.medkits = pygame.sprite.Group()
        self.ammo_pickups = pygame.sprite.Group()
        self.barrels = pygame.sprite.Group()
        
        # Game state variables
        self.running = True
        self.state = MENU
        self.wave = 1
        self.score = 0
        self.high_score = 0
        self.started = False
        
        # Initialize the map
        self.map = Map()
        
        # Player and camera
        self.player = None
        self.camera_x = 0
        self.camera_y = 0
        
        # World boundary management
        self.world_boundary = WorldBoundary(WORLD_WIDTH, WORLD_HEIGHT)
        
        # Cache for frequently used values
        self.screen_center = (screen_width // 2, screen_height // 2)
        self.screen_buffer = 50
        self.last_cleanup = 0
        self.cleanup_interval = 1000
        
        # Optimization settings
        self.sprite_quadrants = {}
        self.quadrant_size = 2000
        self.last_quadrant_update = 0
        self.quadrant_update_interval = 5000
        self.last_path_update = 0
        self.path_update_interval = 5000
        
        # Initialize spatial grid for collision detection
        self.spatial_grid = SpatialGrid(WORLD_WIDTH, WORLD_HEIGHT)
        
        # Initialize bullet pool
        self.bullet_pool = BulletPool(initial_size=200)
        
        # Weapon damages
        self.weapon_damages = {
            "pistol": 10,
            "smg": 8,
            "assault_rifle": 15,
            "shotgun": 7,
            "rocket": 50
        }
        
        # Safe references for critical objects
        self.player_ref = SafeReference()
        
        # Initialize game state management
        self.menu_selection = 0
        self.pause_selection = 0
        
        # Create all game states
        self.menu_state = MenuState(self)
        self.playing_state = PlayingState(self)
        self.paused_state = PausedState(self)
        self.game_over_state = GameOverState(self)
        self.tutorial_state = TutorialState(self)
        
        # Track current and previous states
        self.current_state = self.menu_state
        self.previous_state = self.menu_state
        
        # Initialize with menu state
        self.current_state.enter()
        
        # Setup clock
        self.clock = pygame.time.Clock()
    
    def set_state(self, new_state):
        """Change the current game state."""
        print(f"Changing state from {self.current_state.__class__.__name__} to {new_state.__class__.__name__}")
        if self.current_state:
            self.current_state.exit()
        self.previous_state = self.current_state
        self.current_state = new_state
        self.current_state.enter()
        
        # Update the game state constant for monitoring and other systems
        if isinstance(new_state, MenuState):
            self.state = MENU
        elif isinstance(new_state, PlayingState):
            self.state = PLAYING
        elif isinstance(new_state, PausedState):
            self.state = PAUSED
        elif isinstance(new_state, GameOverState):
            self.state = GAME_OVER
        elif isinstance(new_state, TutorialState):
            self.state = MENU_TUTORIAL
        print(f"Game state set to: {self.state}")
    
    def draw_text(self, text, size, color, x, y):
        """Render text on the screen at the specified position."""
        font = pygame.font.Font(None, size)
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        text_rect.topleft = (x, y)
        self.screen.blit(text_surface, text_rect)
    
    def start_game(self):
        """Initialize game state for a new game"""
        print("Starting the game...")  # Debug print
        
        # Clear all sprite groups
        self.all_sprites.empty()
        self.enemies.empty()
        self.bullets.empty()
        self.explosions.empty()
        self.medkits.empty()
        self.enemy_bullets.empty()
        self.ammo_pickups.empty()
        self.barrels.empty()
        
        # Create the player
        self.player = Player(self)
        self.player_ref.set(self.player)
        self.all_sprites.add(self.player)
        print(f"Player created at position: {self.player.rect.center}")  # Debug print
        
        # Reset game state
        self.state = PLAYING
        self.started = True
        self.score = 0
        self.wave = 1
        
        # Initialize camera position
        self.update_camera()
        print(f"Camera position: ({self.camera_x}, {self.camera_y})")  # Debug print
        
        # Spawn initial wave
        self.spawn_wave()
        print(f"Initial wave spawned, {len(self.enemies)} enemies created")  # Debug print
        
    def try_shoot(self):
        """Attempt to shoot with the current weapon"""
        if not self.player:
            return  # Null check to prevent errors
            
        current_weapon = self.player.weapons[self.player.current_weapon]
        current_time = pygame.time.get_ticks()
        
        # Check if weapon has ammo and cooldown has elapsed
        if current_weapon.can_shoot(current_time):
            mouse_x, mouse_y = pygame.mouse.get_pos()
            world_x = mouse_x + self.camera_x
            world_y = mouse_y + self.camera_y
            self.create_bullets(self.player.rect.centerx, self.player.rect.centery, world_x, world_y)

    def spawn_wave(self):
        # Clear existing barrels
        for barrel in self.barrels:
            barrel.kill()
            self.all_sprites.remove(barrel)
        self.barrels.empty()
        
        # Spawn new barrels
        for _ in range(100):
            valid_x, valid_y = self.map.find_valid_spawn_position(30, 30)
            barrel = ExplosiveBarrel(valid_x, valid_y)
            self.barrels.add(barrel)
            self.all_sprites.add(barrel)
        
        # Calculate number of enemies for this wave (1.5x increase each wave)
        base_enemies = 20 if self.wave == 1 else 10  # Double enemies in first wave
        wave_multiplier = 1.5 ** (self.wave - 1)  # Exponential increase
        num_enemies = int(base_enemies * wave_multiplier)
        
        # Ensure minimum number of enemies
        min_enemies = max(4, num_enemies)
        
        # Clear path cache when spawning new wave
        PATH_CACHE.clear()
        
        # Calculate number of special enemies (increases with wave)
        num_special = min(3, int(min_enemies * 0.3))  # 30% special enemies, max 3
        
        # Spawn enemies with delay between each spawn
        for i in range(min_enemies):
            if i < min_enemies - num_special:  # Regular enemies
                self.spawn_enemy("standard")
            else:  # Special enemies
                special_types = ["shooter", "assault", "officer"]
                enemy_type = special_types[i - (min_enemies - num_special)]
                self.spawn_enemy(enemy_type)
            pygame.time.wait(50)  # Reduced delay between spawns

    def spawn_enemy(self, enemy_type="standard"):
        """Spawn a new enemy at a strategic position based on player location"""
        # Use predefined spawn points if available
        if hasattr(self.map, 'spawn_points') and self.map.spawn_points:
            player = self.player
            player_x, player_y = player.rect.centerx, player.rect.centery
            
            # Get closest spawn points ensuring they come from different directions
            spawn_candidates = self.map.get_closest_spawn_points(player_x, player_y, count=3)
            
            if spawn_candidates:
                # Choose one of the spawn points randomly
                spawn_x, spawn_y = random.choice(spawn_candidates)
                
                # Create the enemy at the chosen spawn point with specified type
                enemy = Enemy(self, spawn_x, spawn_y, enemy_type)
                self.enemies.add(enemy)
                debug_print(f"{enemy_type} enemy spawned at predefined position ({spawn_x}, {spawn_y})")
                return
        
        # Fall back to original spawn logic if no predefined points are available
        screen_x, screen_y = self.camera.position.x, self.camera.position.y
        screen_width, screen_height = self.screen.get_width(), self.screen.get_height()
        
        # Add a buffer zone around the screen for spawning
        buffer = 300
        
        # Define the extended boundaries for spawning
        left = max(0, screen_x - buffer)
        top = max(0, screen_y - buffer)
        right = min(WORLD_WIDTH, screen_x + screen_width + buffer)
        bottom = min(WORLD_HEIGHT, screen_y + screen_height + buffer)
        
        # Randomly select a side to spawn from
        side = random.choice(['top', 'right', 'bottom', 'left'])
        
        if side == 'top':
            x = random.randint(left, right)
            y = max(0, top - random.randint(50, 150))
        elif side == 'right':
            x = min(WORLD_WIDTH, right + random.randint(50, 150))
            y = random.randint(top, bottom)
        elif side == 'bottom':
            x = random.randint(left, right)
            y = min(WORLD_HEIGHT, bottom + random.randint(50, 150))
        else:  # left
            x = max(0, left - random.randint(50, 150))
            y = random.randint(top, bottom)
        
        # Ensure the coordinates are within world bounds
        x = max(0, min(WORLD_WIDTH, x))
        y = max(0, min(WORLD_HEIGHT, y))
        
        # Find a valid spawn position
        spawn_x, spawn_y = self.map.find_valid_spawn_position(30, 30, center_point=(x, y))
        
        # Create a new enemy at the spawn position with specified type
        enemy = Enemy(self, spawn_x, spawn_y, enemy_type)
        self.enemies.add(enemy)
        self.all_sprites.add(enemy)
        debug_print(f"{enemy_type} enemy spawned at ({spawn_x}, {spawn_y})")

    def spawn_medkit(self, x, y):
        if random.random() < MEDKIT_SPAWN_CHANCE:
            medkit = Medkit(x, y)
            self.medkits.add(medkit)
            self.all_sprites.add(medkit)

    def spawn_pickup(self, x, y):
        # 50% chance to not spawn anything
        if random.random() < 0.5:
            return
            
        # If we do spawn something, 50-50 chance between medkit and ammo
        if random.random() < 0.5:  # 50% chance for medkit
            medkit = Medkit(x, y)
            self.medkits.add(medkit)
            self.all_sprites.add(medkit)
        else:  # 50% chance for ammo
            # Choose a random weapon type (excluding pistol which has infinite ammo)
            weapon_types = ["smg", "assault_rifle", "shotgun", "rocket_launcher"]
            weapon_type = random.choice(weapon_types)
            ammo = AmmoPickup(x, y, weapon_type)
            self.ammo_pickups.add(ammo)
            self.all_sprites.add(ammo)

    def update_camera(self):
        # Update camera to follow player while keeping world bounds
        self.camera_x = max(0, min(WORLD_WIDTH - SCREEN_WIDTH, 
            self.player.rect.centerx - SCREEN_WIDTH // 2))
        self.camera_y = max(0, min(WORLD_HEIGHT - SCREEN_HEIGHT, 
            self.player.rect.centery - SCREEN_HEIGHT // 2))

    def update_sprite_quadrants(self):
        # Only update quadrants for visible sprites
        visible_sprites = []
        for sprite in self.all_sprites:
            screen_x = sprite.rect.x - self.camera_x
            screen_y = sprite.rect.y - self.camera_y
            if (-self.quadrant_size <= screen_x <= SCREEN_WIDTH + self.quadrant_size and
                -self.quadrant_size <= screen_y <= SCREEN_HEIGHT + self.quadrant_size):
                visible_sprites.append(sprite)
        
        self.sprite_quadrants.clear()
        # Group visible sprites by quadrants
        for sprite in visible_sprites:
            quadrant_x = sprite.rect.centerx // self.quadrant_size
            quadrant_y = sprite.rect.centery // self.quadrant_size
            key = (quadrant_x, quadrant_y)
            
            if key not in self.sprite_quadrants:
                self.sprite_quadrants[key] = []
            self.sprite_quadrants[key].append(sprite)

    def get_nearby_sprites(self, sprite, radius):
        quadrant_x = sprite.rect.centerx // self.quadrant_size
        quadrant_y = sprite.rect.centery // self.quadrant_size
        nearby = []
        
        # Check surrounding quadrants
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                key = (quadrant_x + dx, quadrant_y + dy)
                if key in self.sprite_quadrants:
                    nearby.extend(self.sprite_quadrants[key])
        
        return nearby

    def update_game_world(self):
        # Update player position
        self.player.update(self)
        
        # Update enemies
        for enemy in self.enemies:
            enemy.update(self.player, self, self.camera_x, self.camera_y)
        
        # Update bullets
        for bullet in self.bullets:
            bullet.update()
        
        # Update explosions
        for explosion in self.explosions:
            explosion.update()
        
        # Update enemy bullets
        for bullet in self.enemy_bullets:
            bullet.update()
        
        # Update medkits
        for medkit in self.medkits:
            medkit.update()
        
        # Update ammo pickups
        for ammo in self.ammo_pickups:
            ammo.update()
        
        # Update barrels
        for barrel in self.barrels:
            barrel.update()
        
        # Update spatial grid
        self.spatial_grid.clear()
        for enemy in self.enemies:
            self.spatial_grid.insert(enemy)
        
        # Update bullets with spatial partitioning
        for bullet in self.bullets:
            # ... existing code for bullet updates ...
            
            # Get nearby enemies for collision check instead of checking all enemies
            nearby_enemies = self.spatial_grid.get_nearby_cells(bullet.rect.centerx, bullet.rect.centery)
            
            # Check for collisions with nearby enemies only
            for enemy in nearby_enemies:
                if bullet.rect.colliderect(enemy.rect):
                    # Handle the collision
                    if not bullet.has_hit:  # Prevent multiple hits with same bullet
                        damage = self.weapon_damages.get(bullet.weapon_type, 10)
                        enemy.take_damage(damage)
                        
                        # Create explosion for rocket launcher
                        if bullet.weapon_type == "rocket":
                            # Create explosion at bullet's position
                            self.create_explosion(bullet.rect.centerx, bullet.rect.centery, damage)
                        
                        bullet.has_hit = True
                        bullet.kill()
                        self.all_sprites.remove(bullet)
                        break  # One bullet hits only one enemy

        # Check for bullet collisions with enemies using optimized group collision
        hits = pygame.sprite.groupcollide(self.enemies, self.bullets, False, True)
        for enemy, bullets in hits.items():
            for bullet in bullets:
                self.all_sprites.remove(bullet)
                if bullet.weapon_type == "rocket_launcher":
                    self.create_explosion(bullet.rect.centerx, bullet.rect.centery, bullet.damage)
                else:
                    enemy.health -= bullet.damage

        # Check for bullet collisions with barrels
        barrel_hits = pygame.sprite.groupcollide(self.barrels, self.bullets, True, True)
        for barrel, bullets in barrel_hits.items():
            self.all_sprites.remove(barrel)
            for bullet in bullets:
                self.all_sprites.remove(bullet)
            self.create_explosion(barrel.rect.centerx, barrel.rect.centery, 100)

        # Check for enemy bullet collisions with barrels
        enemy_barrel_hits = pygame.sprite.groupcollide(self.barrels, self.enemy_bullets, True, True)
        for barrel, bullets in enemy_barrel_hits.items():
            self.all_sprites.remove(barrel)
            for bullet in bullets:
                self.all_sprites.remove(bullet)
            self.create_explosion(barrel.rect.centerx, barrel.rect.centery, 100)

        # Check for player collision with enemies using optimized collision detection
        hits = pygame.sprite.spritecollide(self.player, self.enemies, False)
        if hits:
            current_time = pygame.time.get_ticks()
            for enemy in hits:
                # Enemy collision damage with cooldown
                if current_time - enemy.last_collision >= enemy.collision_cooldown:
                    collision_damage = 30 if enemy.type == "officer" else 10
                    self.player.health -= collision_damage
                    enemy.last_collision = current_time
                
                # Player collision damage with cooldown
                if current_time - self.player.last_collision >= self.player.collision_cooldown:
                    enemy.health -= 5
                    self.player.last_collision = current_time
                
                if enemy.explode(self):
                    enemy.kill()
                    self.all_sprites.remove(enemy)
                    self.score += 20
                
                if self.player.health <= 0:
                    if self.score > self.high_score:
                        self.high_score = self.score
                    self.set_state(self.game_over_state)  # Use set_state for transitions
                    return  # Stop processing when player is dead

        # Remove dead enemies and check for wave completion
        dead_enemies = [enemy for enemy in self.enemies if enemy.health <= 0]
        for enemy in dead_enemies:
            self.spawn_pickup(enemy.rect.centerx, enemy.rect.centery)
            enemy.kill()
            self.all_sprites.remove(enemy)
            self.score += 10
        
        if len(self.enemies) == 0:
            self.wave += 1
            self.enemies_per_wave += 5
            self.spawn_wave()

        # Check for medkit collection using optimized sprite collision
        medkit_hits = pygame.sprite.spritecollide(self.player, self.medkits, False)
        for medkit in medkit_hits:
            if self.player.stored_medkits < self.player.max_medkits:
                self.player.stored_medkits += 1
                medkit.kill()
                self.all_sprites.remove(medkit)

        # Check for ammo pickup collection
        ammo_hits = pygame.sprite.spritecollide(self.player, self.ammo_pickups, True)
        for ammo in ammo_hits:
            self.all_sprites.remove(ammo)
            weapon = self.player.weapons[ammo.weapon_type]
            if weapon.ammo != float('inf'):
                weapon.ammo += ammo.ammo_amount

        # Update spatial grid for collision detection
        self.spatial_grid.clear()
        
        # Insert enemies into spatial grid
        for enemy in self.enemies:
            self.spatial_grid.insert(enemy)
        
        # Process bullets with spatial partitioning for collision detection
        for bullet in self.bullets:
            # ... existing code for bullet updates ...
            
            # Get nearby enemies for collision check instead of checking all enemies
            nearby_enemies = self.spatial_grid.get_nearby_cells(bullet.rect.centerx, bullet.rect.centery)
            
            # Check for collisions with nearby enemies only
            for enemy in nearby_enemies:
                if bullet.rect.colliderect(enemy.rect):
                    # Handle the collision
                    if not bullet.has_hit:  # Prevent multiple hits with same bullet
                        damage = self.weapon_damages.get(bullet.weapon_type, 10)
                        enemy.take_damage(damage)
                        
                        # Create explosion for rocket launcher
                        if bullet.weapon_type == "rocket":
                            # Create explosion at bullet's position
                            self.create_explosion(bullet.rect.centerx, bullet.rect.centery, damage)
                        
                        bullet.has_hit = True
                        bullet.kill()
                        self.all_sprites.remove(bullet)
                        break  # One bullet hits only one enemy

    def create_explosion(self, x, y, damage):
        # Create explosion effect with 50px outer radius
        explosion = Explosion(x, y, 25, damage)  # 25px inner radius, 50px outer
        self.explosions.add(explosion)
        self.all_sprites.add(explosion)
        
        # Reset explosion damage flags
        for enemy in self.enemies:
            enemy.damaged_by_explosion = False
        
        # Damage all enemies in explosion radius
        for enemy in self.enemies:
            if enemy.damaged_by_explosion:
                continue
                
            dx = enemy.rect.centerx - x
            dy = enemy.rect.centery - y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 25:  # Inner radius (25px)
                enemy.health -= 100  # Fixed inner radius damage
                enemy.damaged_by_explosion = True
            elif dist < 50:  # Outer radius (50px)
                enemy.health -= 50  # Fixed outer radius damage
                enemy.damaged_by_explosion = True

        # Damage player if in explosion radius
        dx = self.player.rect.centerx - x
        dy = self.player.rect.centery - y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 25:  # Inner radius
            self.player.health -= 100
        elif dist < 50:  # Outer radius
            self.player.health -= 50

        if self.player.health <= 0:
            if self.score > self.high_score:
                self.high_score = self.score
            self.set_state(self.game_over_state)  # Use set_state for transitions

    def create_bullets(self, start_x, start_y, target_x, target_y):
        current_time = pygame.time.get_ticks()
        weapon = self.player.weapons[self.player.current_weapon]
        
        if weapon.shoot(current_time):
            if self.player.current_weapon == "shotgun":
                # Create spread pattern for shotgun
                for angle in range(-30, 31, 15):  # 5 bullets in a 60-degree spread
                    rad = math.radians(angle)
                    # Calculate spread target
                    dx = target_x - start_x
                    dy = target_y - start_y
                    dist = math.sqrt(dx * dx + dy * dy)
                    spread_x = start_x + dx * math.cos(rad) - dy * math.sin(rad)
                    spread_y = start_y + dx * math.sin(rad) + dy * math.cos(rad)
                    
                    bullet = Bullet(start_x, start_y, spread_x, spread_y, 
                                  self.player.current_weapon, weapon.damage)
                    self.bullets.add(bullet)
                    self.all_sprites.add(bullet)
            elif self.player.current_weapon == "rocket_launcher":
                # Create explosive bullet for rocket launcher
                bullet = Bullet(start_x, start_y, target_x, target_y, 
                              self.player.current_weapon, weapon.damage)
                self.bullets.add(bullet)
                self.all_sprites.add(bullet)
            else:
                # Create single bullet for other weapons
                bullet = Bullet(start_x, start_y, target_x, target_y, 
                              self.player.current_weapon, weapon.damage)
                self.bullets.add(bullet)
                self.all_sprites.add(bullet)

    def draw_health_bar(self, surface, x, y, width, height):
        # Draw outline
        pygame.draw.rect(surface, BLACK, (x-2, y-2, width+4, height+4), 2)
        
        # Calculate health percentage
        health_percentage = self.player.health / 100.0
        health_width = int(width * health_percentage)
        
        # Draw red background (damage)
        pygame.draw.rect(surface, RED, (x, y, width, height))
        
        # Draw green health
        if health_width > 0:
            pygame.draw.rect(surface, GREEN, (x, y, health_width, height))

    def draw_minimap(self):
        # Create minimap surface with semi-transparent background
        minimap_size = 150  # Size of the minimap on screen
        minimap_scale = minimap_size / 2000  # Scale factor (2000 pixels of game world = minimap_size pixels on minimap)
        minimap_surface = pygame.Surface((minimap_size, minimap_size), pygame.SRCALPHA)
        pygame.draw.rect(minimap_surface, (0, 0, 0, 128), (0, 0, minimap_size, minimap_size))
        
        # Calculate minimap boundaries in world coordinates
        world_x = self.player.rect.centerx - 1000  # Center of 2000x2000 view
        world_y = self.player.rect.centery - 1000
        
        # Draw player (yellow dot)
        player_mini_x = (self.player.rect.centerx - world_x) * minimap_scale
        player_mini_y = (self.player.rect.centery - world_y) * minimap_scale
        pygame.draw.circle(minimap_surface, YELLOW, (int(player_mini_x), int(player_mini_y)), 3)
        
        # Draw enemies (red dots)
        for enemy in self.enemies:
            if (world_x - 100 <= enemy.rect.centerx <= world_x + 2100 and
                world_y - 100 <= enemy.rect.centery <= world_y + 2100):
                enemy_mini_x = (enemy.rect.centerx - world_x) * minimap_scale
                enemy_mini_y = (enemy.rect.centery - world_y) * minimap_scale
                pygame.draw.circle(minimap_surface, RED, (int(enemy_mini_x), int(enemy_mini_y)), 2)
        
        # Draw minimap border
        pygame.draw.rect(minimap_surface, WHITE, (0, 0, minimap_size, minimap_size), 1)
        
        # Position minimap in top-right corner with padding
        self.screen.blit(minimap_surface, (SCREEN_WIDTH - minimap_size - 10, 10))

    def draw_game_over(self):
        self.screen.fill(WHITE)
        self.draw_text("GAME OVER", 64, RED, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4)
        self.draw_text(f"Final Score: {self.score}", 48, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.draw_text("Press SPACE to play again", 36, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT * 3 // 4)
        self.draw_text("Press ESC to quit", 36, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT * 3 // 4 + 50)
        pygame.display.flip()

    def draw_game_world(self, screen):
        # Draw map with camera offset
        self.map.draw(screen, self.camera_x, self.camera_y)
        
        # Draw sprites with camera offset
        for sprite in self.all_sprites:
            screen_x = sprite.rect.x - self.camera_x
            screen_y = sprite.rect.y - self.camera_y
            screen.blit(sprite.image, (screen_x, screen_y))
        
        # Draw HUD elements
        self.draw_health_bar(screen, 10, 10, 200, 20)
        self.draw_text(f"Score: {self.score}", 36, WHITE, 60, 40)
        self.draw_text(f"Wave: {self.wave}", 36, WHITE, 50, 70)
        self.draw_text(f"High Score: {self.high_score}", 36, YELLOW, SCREEN_WIDTH - 100, 10)
        
        # Draw weapon info
        weapon = self.player.weapons[self.player.current_weapon]
        self.draw_text(f"Weapon: {self.player.current_weapon.replace('_', ' ').title()}", 24, WHITE, 100, SCREEN_HEIGHT - 30)
        if weapon.ammo != float('inf'):
            self.draw_text(f"Ammo: {weapon.ammo}", 24, WHITE, 100, SCREEN_HEIGHT - 60)
        
        # Draw medkit info
        self.draw_text(f"Medkits: {self.player.stored_medkits}/{self.player.max_medkits}", 24, GREEN, 100, SCREEN_HEIGHT - 90)
        
        # Draw minimap
        self.draw_minimap()

    def handle_game_input(self, event):
        if event.key == pygame.K_m:
            self.player.use_medkit()
        elif event.key == pygame.K_ESCAPE:
            self.set_state(self.paused_state)
        elif event.key == pygame.K_SPACE:
            if self.state == MENU_TUTORIAL:
                self.state = PLAYING
                self.init_game()
            elif self.state == GAME_OVER:
                self.state = PLAYING
                self.init_game()

    def handle_events(self):
        """Process input events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            else:
                self.handle_event(event)
                
    def run(self):
        """Main game loop"""
        while self.running:
            # Process events
            self.handle_events()
            
            # Update game state
            self.update()
            
            # Draw current state
            self.draw(self.screen)
            
            # Update display
            pygame.display.flip()
            
            # Cap the frame rate
            self.clock.tick(FPS)
            
        pygame.quit()

    def draw(self, screen):
        """Draw the game based on current state"""
        self.current_state.draw(screen)

    def handle_event(self, event):
        """Handle an event by delegating to the current state"""
        self.current_state.handle_event(event)

    def update(self):
        """Update the game based on current state"""
        self.current_state.update()

if __name__ == "__main__":
    # Check if we need to generate a new map
    if not os.path.exists("map_data.json") or not os.path.exists("game_map.jpg"):
        print("Generating new map...")
        game_map = Map(load_saved=False)  # Force new map generation
        print("Map saved as 'game_map.jpg' and 'map_data.json'")
    else:
        print("Using existing map...")
    
    # Start the game
    game = Game()
    
    # Set up game monitoring
    import game_monitor
    
    # Start the monitor in a separate thread
    monitor_thread = threading.Thread(target=game_monitor.monitor_game, args=(game,))
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Run the game
    game.run() 