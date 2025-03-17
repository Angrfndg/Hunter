import pygame
import random
import math
import numpy as np
import os
import json
import threading
import queue
import time
import uuid
import sys
import pickle
from collections import deque

# Game version
VERSION = "0.2 - Performance Optimized"

# Initialize Pygame
pygame.init()

# Debug print function
def debug_print(message):
    """Print debug messages if DEBUG is enabled"""
    # Uncomment the line below to enable debug prints
    print(message)

# Constants
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
WORLD_WIDTH = 9000  # Increased from 3000 to 9000
WORLD_HEIGHT = 9000  # Increased from 3000 to 9000
MEDKIT_SPAWN_CHANCE = 0.5  # Increased from 0.1 to 0.5 (50% chance)

# Grid and Pathfinding Constants
GRID_SIZE = 10  # Keep at 10 for better performance
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
GRAY = (128, 128, 128)  # For buildings and UI elements
DARK_GRAY = (64, 64, 64)  # For streets and UI elements

# Game States
MENU = 0
MENU_TUTORIAL = 1  # Tutorial accessed from main menu
PLAYING = 2
GAME_OVER = 3
PAUSED = 4  # New state for pause menu

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
    "standard": {"health": 1, "damage": 0.33, "color": RED, "symbol": "●", "collision_rate": 1.0, "speed": 4, "points": 10, "attack_range": 100, "attack_cooldown": 1000},
    "shooter": {"health": 1, "damage": 1, "color": BLUE, "symbol": "▲", "collision_rate": 1.0, "speed": 3, "points": 15, "attack_range": 400, "attack_cooldown": 1500},
    "assault": {"health": 1, "damage": 6.67, "color": ORANGE, "symbol": "★", "collision_rate": 1.0, "speed": 2, "points": 20, "attack_range": 100, "attack_cooldown": 800},
    "officer": {"health": 10, "damage": 1, "color": PURPLE, "symbol": "◆", "collision_rate": 1.0, "speed": 2, "points": 25, "attack_range": 200, "attack_cooldown": 1000},
    "tank": {"health": 20, "damage": 2, "color": ORANGE, "symbol": "★", "collision_rate": 1.0, "speed": 1, "points": 30, "attack_range": 150, "attack_cooldown": 2000},
    "exploder": {"health": 5, "damage": 5, "color": RED, "symbol": "●", "collision_rate": 1.0, "speed": 2, "points": 10, "attack_range": 100, "attack_cooldown": 0}
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
        # Load player image
        self.image = pygame.image.load("assets/Player_pistol.png").convert_alpha()
        self.rect = self.image.get_rect()
        
        # Initialize player attributes
        self.x = WORLD_WIDTH // 2
        self.y = WORLD_HEIGHT // 2
        self.rect.center = (self.x, self.y)
        self.speed = 8
        self.health = 100
        self.stored_medkits = 0  # Add medkit storage
        self.max_medkits = 5  # Maximum stored medkits
        self.collision_rate = 1.0  # 1 hit per second
        self.last_collision = 0
        self.collision_cooldown = int(1000 / self.collision_rate)  # Convert rate to milliseconds
        self.weapons = {
            "pistol": Weapon("pistol"),
            "smg": Weapon("smg"),
            "assault_rifle": Weapon("assault_rifle"),
            "shotgun": Weapon("shotgun"),
            "rocket_launcher": Weapon("rocket_launcher")
        }
        self.current_weapon = "pistol"

    def use_medkit(self):
        if self.stored_medkits > 0 and self.health < 100:
            self.stored_medkits -= 1
            self.health = min(100, self.health + 50)  # Heal 50 HP when using medkit, up to max health
            return True
        return False

    def update(self, game):
        # Store old position for collision detection
        old_x = self.rect.x
        old_y = self.rect.y
        
        # Get keyboard input
        keys = pygame.key.get_pressed()
        dx = 0
        dy = 0
        
        if keys[pygame.K_a]:  # Left
            dx = -self.speed
        if keys[pygame.K_d]:  # Right
            dx = self.speed
        if keys[pygame.K_w]:  # Up
            dy = -self.speed
        if keys[pygame.K_s]:  # Down
            dy = self.speed
            
        # Try moving horizontally first
        if dx != 0:
            self.rect.x += dx
            if game.map.check_collision(self):
                self.rect.x = old_x
                # Try sliding vertically if there's vertical movement
                if dy != 0:
                    self.rect.y += dy
                    if game.map.check_collision(self):
                        self.rect.y = old_y
        
        # Try moving vertically if we haven't already
        if dy != 0 and (dx == 0 or self.rect.y == old_y):
            self.rect.y += dy
            if game.map.check_collision(self):
                self.rect.y = old_y
                # Try sliding horizontally if there's horizontal movement
                if dx != 0:
                    self.rect.x += dx
                    if game.map.check_collision(self):
                        self.rect.x = old_x

        # Keep player within world bounds
        self.rect.clamp_ip(pygame.Rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT))

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, target_x, target_y, weapon_type, damage):
        super().__init__()
        # Create a bright yellow bullet with a glow effect
        self.image = pygame.Surface((8, 8), pygame.SRCALPHA)
        # Draw outer glow
        pygame.draw.circle(self.image, (255, 255, 50, 128), (4, 4), 4)
        # Draw inner bright core
        pygame.draw.circle(self.image, (255, 255, 50, 255), (4, 4), 2)
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        self.speed = 10
        self.damage = damage
        self.weapon_type = weapon_type
        self.target_x = target_x
        self.target_y = target_y
        
        # Calculate direction
        dx = target_x - x
        dy = target_y - y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist != 0:
            self.dx = (dx / dist) * self.speed
            self.dy = (dy / dist) * self.speed
        else:
            self.dx = 0
            self.dy = -self.speed

    def update(self):
        self.rect.x += self.dx
        self.rect.y += self.dy

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
        # Load barrel image from assets
        try:
            self.image = pygame.image.load("assets/Barrel.png").convert_alpha()
            # Use the barrel at its original 64x64 size (no scaling)
            # Only scale if it's not close to 64x64
            if abs(self.image.get_width() - 64) > 10 or abs(self.image.get_height() - 64) > 10:
                self.image = pygame.transform.scale(self.image, (64, 64))
        except pygame.error:
            # Fallback to drawing if image can't be loaded
            self.image = pygame.Surface((64, 64), pygame.SRCALPHA)
            pygame.draw.rect(self.image, (139, 69, 19), (0, 0, 64, 64))  # Brown base
            pygame.draw.rect(self.image, RED, (10, 10, 44, 44))  # Red warning symbol
            pygame.draw.rect(self.image, (139, 69, 19), (0, 0, 64, 64), 3)  # Border
            debug_print("Failed to load barrel image, using fallback.")
        
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.health = 1  # One hit to explode

class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, enemy_type="standard"):
        pygame.sprite.Sprite.__init__(self)
        self.entity_id = str(uuid.uuid4())  # Generate a unique ID for this enemy
        
        self.type = enemy_type
        self.health = ENEMY_TYPES[enemy_type]["health"]
        self.speed = ENEMY_TYPES[enemy_type]["speed"]
        self.damage = ENEMY_TYPES[enemy_type]["damage"]
        self.points = ENEMY_TYPES[enemy_type]["points"]
        
        # Load appropriate enemy image
        if enemy_type == "standard":
            self.image = pygame.image.load("assets/Enemy_standard.png").convert_alpha()
        elif enemy_type == "assault":
            self.image = pygame.image.load("assets/Enemy_assault.png").convert_alpha()
        elif enemy_type == "shooter":
            self.image = pygame.image.load("assets/Enemy_shooter.png").convert_alpha()
        elif enemy_type == "officer":
            self.image = pygame.image.load("assets/Enemy_officer.png").convert_alpha()
        elif enemy_type == "tank":
            # Fallback to drawing a shape if image doesn't exist
            self.image = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.rect(self.image, ORANGE, (0, 0, 40, 40))
            pygame.draw.rect(self.image, BLACK, (15, 0, 10, 20))  # Tank barrel
        elif enemy_type == "exploder":
            # Fallback to drawing a shape if image doesn't exist
            self.image = pygame.Surface((30, 30), pygame.SRCALPHA)
            pygame.draw.circle(self.image, RED, (15, 15), 15)
            pygame.draw.circle(self.image, (255, 200, 0), (15, 15), 10)  # Inner explosive circle
            
        # Set up animation frames
        self.animation_frames = []
        self.frame_index = 0
        self.last_frame_time = 0
        self.animation_cooldown = 100  # Time between animation frames
        
        # Create 4 frames by rotating the image
        for i in range(4):
            rotated = pygame.transform.rotate(self.image, i * 90)
            self.animation_frames.append(rotated)
            
        self.image = self.animation_frames[0]
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        
        # Combat attributes
        self.last_shot_time = 0
        self.attack_cooldown = ENEMY_TYPES[enemy_type]["attack_cooldown"]
        self.attack_range = ENEMY_TYPES[enemy_type]["attack_range"]  # Add attack range
        self.angle = 0  # Direction enemy is facing
        
        self.collision_rate = ENEMY_TYPES[enemy_type]["collision_rate"]
        self.last_collision = 0
        self.collision_cooldown = int(1000 / self.collision_rate)  # Convert rate to milliseconds
        
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
        
        # Pathfinding related variables
        self.path = None
        self.path_index = 0
        self.path_requested = False
        self.last_path_update = pygame.time.get_ticks()
        self.path_update_interval = 2000  # Normal update interval (2 seconds)
        self.visible_path_update_interval = 500  # More frequent updates for visible enemies
        self.check_path_interval = 5  # Check for path results every 5 frames when off-screen
        self.frame_counter = 0  # Counter for frame-based checks
        self.last_path_pos = None
        self.path_reuse_threshold = 200  # Distance player must move to trigger path update
        self.path_priority = 2  # Default priority (lower is higher priority)
        
        # Stuck detection
        self.last_check_pos = (x, y)
        self.last_check_time = pygame.time.get_ticks()
        self.stuck_count = 0
        
        # Status effects
        self.statuses = {}  # {status_name: (duration, start_time)}
        
        # Add despawn timer
        self.stuck_time = 0
        self.despawn_threshold = 5000
        self.path_reuse_threshold = 200
        self.last_path_pos = None
        
        # Add new variables for stuck detection
        self.last_check_pos = (x, y)
        self.last_check_time = pygame.time.get_ticks()
        self.stuck_count = 0
        
        # Add random movement variables (Phase 2)
        self.random_move_duration = 0
        self.random_move_direction = None
        self.random_move_active = False
        self.last_random_move = 0
        self.random_move_cooldown = 3000  # 3 seconds between random movement attempts
        
        # Add variable for path request management
        self.entity_id = id(self)  # Unique ID for this entity
        self.path_requested = False
        self.path_priority = 0

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

    def explode(self, game):
        """
        Handle explosion logic for enemies.
        Only assault enemies can explode, standard enemies don't explode.
        Returns True if enemy exploded, False otherwise.
        """
        # Only assault enemies can explode, standard enemies don't
        if self.type != "assault":
            return False
        
        # Create explosion at enemy position
        game.create_explosion(self.rect.centerx, self.rect.centery, self.damage * 2)
        # Kill the enemy (remove it from all sprite groups)
        self.kill()
        return True
    
    def try_random_movement(self, game):
        """Try to move in a random direction when stuck"""
        
        # Generate a random angle
        random_angle = random.uniform(0, 2 * math.pi)
        
        # Calculate direction vector
        dx = math.cos(random_angle)
        dy = math.sin(random_angle)
        
        # Calculate target position (100-300 pixels away)
        distance = random.randint(100, 300)
        target_x = self.rect.centerx + dx * distance
        target_y = self.rect.centery + dy * distance
        
        # Ensure target is within world bounds
        target_x = max(0, min(WORLD_WIDTH, target_x))
        target_y = max(0, min(WORLD_HEIGHT, target_y))
        
        # Request a high-priority path to this random location
        game.pathfinding_manager.request_path(
            self.entity_id,
            self.rect.centerx, self.rect.centery,
            target_x, target_y,
            priority=0,  # Highest priority
            is_visible=True  # Treat as visible to ensure it's processed quickly
        )
        self.path_requested = True
        
        # Reset stuck counter partially, but not completely
        # This allows it to try again if this random movement fails
        self.stuck_count = max(0, self.stuck_count - 1)
        
        # Log the action for debugging
        print(f"Enemy {str(self.entity_id)} attempted random movement to escape stuck state")
        
    def shoot(self, game):
        """Shoot a bullet at the player"""
        # Only shooter enemies can shoot
        if self.type != "shooter" and self.type != "officer":
            return
            
        # Create a bullet at the enemy's position
        bullet_speed = 8
        bullet_angle = math.radians(self.angle)
        bullet_dx = math.cos(bullet_angle) * bullet_speed
        bullet_dy = math.sin(bullet_angle) * bullet_speed
        
        # Spawn the bullet at the enemy's position
        bullet = Bullet(
            self.rect.centerx, 
            self.rect.centery,
            self.rect.centerx + bullet_dx * 100,  # Target point for direction
            self.rect.centery + bullet_dy * 100,
            "enemy",  # Enemy bullets
            self.damage
        )
        
        # Add bullet to game's enemy bullet group
        game.enemy_bullets.add(bullet)
        game.all_sprites.add(bullet)
        
        # Update last shot time
        self.last_shot_time = pygame.time.get_ticks()
    
    def update(self, player, game, camera_x=0, camera_y=0):
        current_time = pygame.time.get_ticks()
        
        # Update statuses
        self.update_statuses()
        
        # Calculate distance to player
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        distance_to_player = math.sqrt(dx * dx + dy * dy)
        
        # Check if enemy is visible on screen
        screen_x = self.rect.x - camera_x
        screen_y = self.rect.y - camera_y
        is_near_screen = (-500 <= screen_x <= SCREEN_WIDTH + 500 and
                         -500 <= screen_y <= SCREEN_HEIGHT + 500)
        
        # Store old position for collision detection
        old_x = self.rect.x
        old_y = self.rect.y
        
        # Handle shooting behavior for shooter type
        if self.type == "shooter" and is_near_screen:
            if distance_to_player <= self.max_fire_range and current_time - self.last_shot >= self.shot_delay:
                # Calculate angle to player
                self.angle = math.atan2(dy, dx)
                # Check line of sight
                if not game.map.check_line_of_sight(self.rect.centerx, self.rect.centery,
                                              player.rect.centerx, player.rect.centery):
                    self.shoot(game)
                    self.last_shot = current_time
        
        # Handle melee attacks for non-shooter types
        elif distance_to_player <= self.attack_range and self.type != "standard":
            if current_time - self.last_attack >= self.attack_delay:
                # Attack the player
                if self.type == "assault":
                    player.health -= 15
                elif self.type == "officer":
                    player.health -= 5
                else:
                    player.health -= self.damage
                self.last_attack = current_time
        
        # Update path and movement
        if not self.has_status("frozen"):
            should_update_path = (
                self.path is None or
                current_time - self.last_path_update > (self.visible_path_update_interval if is_near_screen else self.path_update_interval)
            )
            
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
        
        # Check for stuck state
        current_time = pygame.time.get_ticks()
        if current_time - self.last_check_time > 1000:  # Check every second
            current_pos = (self.rect.x, self.rect.y)
            if current_pos == self.last_check_pos:
                self.stuck_count += 1
                if self.stuck_count > 3:  # If stuck for 3+ seconds
                    self.try_random_movement(game)
            else:
                # Reset if we've moved
                self.stuck_count = 0
            
            self.last_check_pos = current_pos
            self.last_check_time = current_time

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

# Add new class for threaded pathfinding
class PathfindingManager(threading.Thread):
    def __init__(self, game_map):
        super().__init__(daemon=True)  # Make it a daemon thread so it exits when the main program exits
        self.map = game_map
        self.path_requests = queue.PriorityQueue()  # Priority queue for path requests
        self.path_results = {}  # Store path results: {entity_id: (path, timestamp)}
        self.running = True
        self.lock = threading.RLock()  # Use RLock for better performance with multiple acquisitions
        self.max_queue_size = 100  # Maximum number of requests to queue (Optimization 1)
        self.request_log = {}  # Track requested entity paths to avoid duplicates
        self.last_cleanup_time = pygame.time.get_ticks()
        self.cleanup_interval = 5000  # Cleanup every 5 seconds (Optimization 2)
        self.last_throttle_check = pygame.time.get_ticks()
        self.throttle_interval = 50  # Base throttle check interval (Optimization 5)
        self.adaptive_sleep = 0.001  # Starting sleep time, will adapt based on queue size
        
    def request_path(self, entity_id, start_x, start_y, end_x, end_y, priority=0, is_visible=False):
        """
        Request a path calculation. Lower priority values are processed first.
        Added is_visible parameter to prioritize visible enemies (Optimization 4)
        """
        # Adjust priority based on visibility (visible enemies get higher priority)
        if is_visible:
            priority = max(0, priority - 1)  # Boost priority for visible enemies
            
        request_key = (entity_id, (start_x, start_y), (end_x, end_y))
        
        with self.lock:
            # If this entity already has a pending request, replace it (Optimization 1)
            if entity_id in self.request_log:
                # We can't directly remove from the PriorityQueue, so we'll just track it and ignore later
                old_request = self.request_log[entity_id]
                # Mark for replacement (will be ignored when processed)
                self.request_log[entity_id] = None
            
            # Check if queue is getting too large (Optimization 1)
            queue_size = self.path_requests.qsize()
            if queue_size > self.max_queue_size:
                # If queue is full, we'll skip adding low priority requests
                if priority > 1 and not is_visible:
                    return
            
            # Add the request to the queue
            self.path_requests.put((priority, (entity_id, start_x, start_y, end_x, end_y, is_visible)))
            self.request_log[entity_id] = request_key
        
    def get_path(self, entity_id):
        """Get a calculated path result if available."""
        with self.lock:
            if entity_id in self.path_results:
                path, _ = self.path_results[entity_id]
                del self.path_results[entity_id]
                if entity_id in self.request_log:
                    del self.request_log[entity_id]
                return path
        return None
        
    def has_path_result(self, entity_id):
        """Check if a path result is available for the given entity."""
        with self.lock:
            return entity_id in self.path_results
    
    def clean_up_old_results(self, current_time):
        """Remove old path results that haven't been retrieved (Optimization 2)"""
        with self.lock:
            to_remove = []
            for entity_id, (path, timestamp) in self.path_results.items():
                # Remove results older than 10 seconds
                if current_time - timestamp > 10000:
                    to_remove.append(entity_id)
            
            for entity_id in to_remove:
                del self.path_results[entity_id]
                if entity_id in self.request_log:
                    del self.request_log[entity_id]
            
    def run(self):
        """Main thread function that processes path requests continuously."""
        while self.running:
            try:
                current_time = pygame.time.get_ticks()
                
                # Clean up old results periodically (Optimization 2)
                if current_time - self.last_cleanup_time > self.cleanup_interval:
                    self.clean_up_old_results(current_time)
                    self.last_cleanup_time = current_time
                
                # Adaptive throttling based on queue size (Optimization 5)
                if current_time - self.last_throttle_check > self.throttle_interval:
                    queue_size = self.path_requests.qsize()
                    
                    # Adjust sleep time based on queue size
                    if queue_size == 0:
                        self.adaptive_sleep = min(0.05, self.adaptive_sleep * 1.5)  # Increase sleep time when idle
                    elif queue_size > 10:
                        self.adaptive_sleep = max(0.001, self.adaptive_sleep * 0.5)  # Decrease sleep time when busy
                    
                    self.last_throttle_check = current_time
                
                # Get a path request with timeout
                priority, (entity_id, start_x, start_y, end_x, end_y, is_visible) = self.path_requests.get(timeout=self.adaptive_sleep)
                
                # Check if this request has been superseded by a newer one for the same entity
                with self.lock:
                    request_key = (entity_id, (start_x, start_y), (end_x, end_y))
                    if entity_id in self.request_log and self.request_log[entity_id] != request_key:
                        # This is an old request that's been replaced, skip it
                        continue
                
                # Calculate the path
                path = self.map.find_path(start_x, start_y, end_x, end_y)
                
                # Store the result with timestamp
                with self.lock:
                    self.path_results[entity_id] = (path, pygame.time.get_ticks())
                    
            except queue.Empty:
                # No path requests, just continue (will sleep due to timeout)
                pass
            except Exception as e:
                print(f"PathfindingManager error: {e}")
                
    def stop(self):
        """Stop the pathfinding thread."""
        self.running = False
        self.join(timeout=1.0)  # Wait for thread to finish with timeout

class Game:
    def __init__(self):
        # Game setup code
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Alien Shooter")
        self.clock = pygame.time.Clock()
        
        # Performance tracking
        self.performance_metrics = {
            "frame_time": 0,
            "update_time": 0,
            "render_time": 0,
            "collision_time": 0,
            "enemy_update_time": 0,
            "barrel_checks_time": 0
        }
        
        self.running = True
        self.state = MENU  # Changed initial state to MENU
        
        # Initialize sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.explosions = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.medkits = pygame.sprite.Group()
        self.ammo_pickups = pygame.sprite.Group()
        self.barrels = pygame.sprite.Group()  # Add barrels group
        
        # Cache for frequently used values
        self.screen_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.screen_buffer = 50
        self.last_cleanup = 0
        self.cleanup_interval = 1000  # Clean up every second
        
        self.map = Map()
        
        # Initialize pathfinding manager
        self.pathfinding_manager = PathfindingManager(self.map)
        self.pathfinding_manager.start()  # Start the pathfinding thread
        
        self.init_game()
        self.auto_fire = False
        self.camera_x = 0
        self.camera_y = 0
        self.sprite_quadrants = {}
        self.quadrant_size = 2000  # Increased quadrant size
        self.last_quadrant_update = 0
        self.quadrant_update_interval = 5000  # Reduced frequency of quadrant updates
        self.last_path_update = 0
        self.path_update_interval = 5000  # Increased path update interval
        
        # For returning to game after tutorial
        self.previous_state = MENU

    def cleanup_off_screen_sprites(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.last_cleanup > 1000:  # Reduced from 5000 to 1000ms
            # Clean up bullets that are off screen
            for bullet in list(self.bullets):  # Convert to list to avoid modification during iteration
                if not self.is_sprite_visible(bullet, buffer=500):  # Larger buffer for cleanup
                    bullet.kill()
            
            # Clean up enemy bullets
            for bullet in list(self.enemy_bullets):  # Convert to list to avoid modification during iteration
                if not self.is_sprite_visible(bullet, buffer=500):
                    bullet.kill()
            
            # Clean up expired explosions
            for explosion in list(self.explosions):  # Convert to list to avoid modification during iteration
                if explosion.age >= explosion.lifetime:
                    explosion.kill()
            
            self.last_cleanup = current_time

    def init_game(self):
        self.wave = 1
        self.score = 0
        self.enemies_per_wave = 10
        self.high_score = 0
        self.camera_x = 0
        self.camera_y = 0

        # Clear all sprite groups
        self.all_sprites.empty()
        self.enemies.empty()
        self.bullets.empty()
        self.explosions.empty()
        self.medkits.empty()
        self.enemy_bullets.empty()
        self.ammo_pickups.empty()
        self.barrels.empty()  # Clear barrels
        
        # Create player
        self.player = Player(self)
        self.all_sprites.add(self.player)
        
        # Initialize camera position
        self.update_camera()

        # Spawn initial wave
        self.spawn_wave()

    def draw_text(self, text, size, color, x, y):
        font = pygame.font.Font(None, size)
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        text_rect.midtop = (x, y)
        self.screen.blit(text_surface, text_rect)

    def draw_menu(self):
        self.screen.fill(WHITE)
        self.draw_text("HUNTER", 64, YELLOW, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4)
        self.draw_text("Press SPACE to see tutorial", 36, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.draw_text("Press ESC to quit", 36, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT * 3 // 4)
        pygame.display.flip()
        
    def draw_tutorial(self):
        # Draw tutorial screen
        self.screen.fill(BLACK)
        
        # Title
        self.draw_text("TUTORIAL", 64, YELLOW, SCREEN_WIDTH // 2, 50)
        
        # Controls section
        self.draw_text("CONTROLS:", 36, WHITE, SCREEN_WIDTH // 2, 120)
        controls = [
            "Move: WASD keys",
            "Aim: Mouse cursor",
            "Shoot: Left mouse button",
            "Use Medkit: M key (max 5 stored)",
            "Pause Game: ESC key"
        ]
        y_pos = 160
        for ctrl in controls:
            self.draw_text(ctrl, 24, WHITE, SCREEN_WIDTH // 2, y_pos)
            y_pos += 30
            
        # Weapons section
        self.draw_text("WEAPONS (1-5 keys to switch):", 36, WHITE, SCREEN_WIDTH // 2, y_pos + 20)
        weapons = [
            "1: Pistol - Infinite ammo, low damage, slow fire rate",
            "2: SMG - Fast fire rate, low damage per bullet",
            "3: Assault Rifle - Medium fire rate, higher damage",
            "4: Shotgun - Spread pattern, effective at close range",
            "5: Rocket Launcher - Explosive damage, very limited ammo"
        ]
        y_pos += 60
        for weapon in weapons:
            self.draw_text(weapon, 20, WHITE, SCREEN_WIDTH // 2, y_pos)
            y_pos += 25
            
        # Enemies section
        self.draw_text("ENEMIES:", 36, WHITE, SCREEN_WIDTH // 2, y_pos + 20)
        enemies = [
            "Standard (Red): Basic enemy, moves toward player",
            "Shooter (Blue): Fires projectiles at player",
            "Assault (Orange): Explodes on death, high melee damage",
            "Officer (Purple): High health, medium damage"
        ]
        y_pos += 60
        for enemy in enemies:
            self.draw_text(enemy, 20, WHITE, SCREEN_WIDTH // 2, y_pos)
            y_pos += 25
            
        # Game objective
        self.draw_text("OBJECTIVE:", 36, WHITE, SCREEN_WIDTH // 2, y_pos + 20)
        self.draw_text("Survive waves of enemies. Each wave gets harder.", 24, WHITE, SCREEN_WIDTH // 2, y_pos + 60)
        self.draw_text("Collect medkits and ammo to stay alive longer.", 24, WHITE, SCREEN_WIDTH // 2, y_pos + 90)
        
        # Navigation prompt
        self.draw_text("Press SPACE to start the game", 30, YELLOW, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50)
        
        pygame.display.flip()

    def draw_pause_menu(self):
        # Create a semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill(WHITE)
        overlay.set_alpha(128)  # 128 is 50% transparent
        self.screen.blit(overlay, (0, 0))
        
        # Draw pause menu text
        self.draw_text("PAUSED", 64, YELLOW, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3)
        self.draw_text("Press SPACE to continue", 36, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.draw_text("Press T for tutorial", 36, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50)
        self.draw_text("Press ESC to quit", 36, BLACK, SCREEN_WIDTH // 2, SCREEN_HEIGHT * 2 // 3)
        pygame.display.flip()

    def handle_events(self):
        current_time = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == PLAYING:
                        self.state = PAUSED
                    elif self.state == PAUSED:
                        self.running = False
                    elif self.state == MENU or self.state == GAME_OVER:
                        self.running = False
                    elif self.state == MENU_TUTORIAL:
                        self.state = MENU  # Return to main menu from tutorial
                        
                if event.key == pygame.K_SPACE:
                    if self.state == MENU:
                        self.previous_state = MENU
                        self.state = MENU_TUTORIAL  # Show tutorial first
                    elif self.state == MENU_TUTORIAL:
                        if self.previous_state == PAUSED:
                            self.state = PLAYING  # Return to game from pause menu tutorial
                        else:
                            self.state = PLAYING  # Start game after tutorial
                            self.init_game()
                    elif self.state == GAME_OVER:
                        self.state = PLAYING
                        self.init_game()
                    elif self.state == PAUSED:
                        self.state = PLAYING
                        
                if event.key == pygame.K_t and self.state == PAUSED:
                    self.previous_state = PAUSED  # Remember we're coming from pause
                    self.state = MENU_TUTORIAL  # Show tutorial
                    
                if event.key == pygame.K_m and self.state == PLAYING:
                    self.player.use_medkit()
                    
                # Weapon switching
                if self.state == PLAYING:
                    if event.key == pygame.K_1:
                        self.player.current_weapon = "pistol"
                    elif event.key == pygame.K_2:
                        self.player.current_weapon = "smg"
                    elif event.key == pygame.K_3:
                        self.player.current_weapon = "assault_rifle"
                    elif event.key == pygame.K_4:
                        self.player.current_weapon = "shotgun"
                    elif event.key == pygame.K_5:
                        self.player.current_weapon = "rocket_launcher"

            elif event.type == pygame.MOUSEBUTTONDOWN and self.state == PLAYING:
                if event.button == 1:  # Left click
                    self.auto_fire = True
                    # Always fire immediately on initial click
                    weapon = self.player.weapons[self.player.current_weapon]
                    # Force a shot regardless of fire rate
                    if weapon.ammo > 0:
                        weapon.last_shot = current_time - weapon.shot_delay  # Reset cooldown
                        self.try_shoot()
            
            elif event.type == pygame.MOUSEBUTTONUP and self.state == PLAYING:
                if event.button == 1:  # Left click release
                    self.auto_fire = False

    def try_shoot(self):
        if self.state != PLAYING:
            return
            
        # Get mouse position and convert to world coordinates
        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x = mouse_x + self.camera_x
        world_y = mouse_y + self.camera_y
        
        # Call create_bullets without redundant check, as create_bullets already calls weapon.shoot()
        self.create_bullets(self.player.rect.centerx, self.player.rect.centery, world_x, world_y)

    def spawn_wave(self):
        # Clear existing barrels
        for barrel in self.barrels:
            barrel.kill()
            self.all_sprites.remove(barrel)
        self.barrels.empty()
        
        # Define player's field of view plus a buffer
        player_view_buffer = 600  # Extra buffer beyond screen dimensions
        if hasattr(self, 'player') and self.player:
            player_x = self.player.rect.centerx
            player_y = self.player.rect.centery
            view_left = max(0, player_x - (SCREEN_WIDTH//2) - player_view_buffer)
            view_right = min(WORLD_WIDTH, player_x + (SCREEN_WIDTH//2) + player_view_buffer)
            view_top = max(0, player_y - (SCREEN_HEIGHT//2) - player_view_buffer)
            view_bottom = min(WORLD_HEIGHT, player_y + (SCREEN_HEIGHT//2) + player_view_buffer)
        else:
            # If player doesn't exist yet, use default values
            view_left = 0
            view_right = WORLD_WIDTH
            view_top = 0
            view_bottom = WORLD_HEIGHT
        
        # Spawn new barrels (only outside player's field of view)
        barrel_attempts = 0
        barrels_spawned = 0
        max_barrel_attempts = 150  # Limit attempts to avoid infinite loop (reduced from 300)
        target_barrel_count = 50   # Reduced from 100 for better performance
        
        while barrels_spawned < target_barrel_count and barrel_attempts < max_barrel_attempts:
            barrel_attempts += 1
            valid_x, valid_y = self.map.find_valid_spawn_position(64, 64)  # Updated to 64x64 size
            
            # Check if position is outside player's field of view
            if (valid_x < view_left or valid_x > view_right or 
                valid_y < view_top or valid_y > view_bottom):
                barrel = ExplosiveBarrel(valid_x, valid_y)
                self.barrels.add(barrel)
                self.all_sprites.add(barrel)
                barrels_spawned += 1
        
        debug_print(f"Spawned {barrels_spawned} barrels after {barrel_attempts} attempts")
        
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
            spawn_candidates = self.map.get_closest_spawn_points(player_x, player_y, count=5)  # Increased from 3 to 5 for more options
            
            if spawn_candidates:
                # Shuffle the spawn candidates to try them in random order
                random.shuffle(spawn_candidates)
                
                # Try each spawn point until we find one that's not occupied
                for spawn_x, spawn_y in spawn_candidates:
                    # Create a temporary rect to check for collisions
                    temp_rect = pygame.Rect(spawn_x - 15, spawn_y - 15, 30, 30)
                    
                    # Check if any enemy is already at this position
                    occupied = False
                    for enemy in self.enemies:
                        if enemy.rect.colliderect(temp_rect):
                            occupied = True
                            break
                    
                    if not occupied:
                        # Create the enemy at this unoccupied spawn point
                        enemy = Enemy(spawn_x, spawn_y, enemy_type)
                        self.enemies.add(enemy)
                        self.all_sprites.add(enemy)
                        debug_print(f"{enemy_type} enemy spawned at unoccupied position ({spawn_x}, {spawn_y})")
                        return
                
                # If all spawn points are occupied, use the first one but add a random offset
                spawn_x, spawn_y = spawn_candidates[0]
                offset_x = random.randint(-50, 50)
                offset_y = random.randint(-50, 50)
                
                # Ensure the new position is valid
                new_x = max(30, min(WORLD_WIDTH - 30, spawn_x + offset_x))
                new_y = max(30, min(WORLD_HEIGHT - 30, spawn_y + offset_y))
                
                # Check if the new position is valid for spawning
                if self.map.is_valid_spawn_position(new_x, new_y, 30, 30):
                    enemy = Enemy(new_x, new_y, enemy_type)
                    self.enemies.add(enemy)
                    self.all_sprites.add(enemy)
                    debug_print(f"{enemy_type} enemy spawned at offset position ({new_x}, {new_y})")
                    return
                else:
                    # Find a valid spawn position near the chosen point
                    spawn_x, spawn_y = self.map.find_valid_spawn_position(30, 30, center_point=(spawn_x, spawn_y))
                    enemy = Enemy(spawn_x, spawn_y, enemy_type)
                    self.enemies.add(enemy)
                    self.all_sprites.add(enemy)
                    debug_print(f"{enemy_type} enemy spawned at fallback position ({spawn_x}, {spawn_y})")
                    return
        
        # Fall back to original spawn logic if no predefined points are available
        screen_x, screen_y = self.camera_x, self.camera_y
        screen_width, screen_height = SCREEN_WIDTH, SCREEN_HEIGHT
        
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
        enemy = Enemy(spawn_x, spawn_y, enemy_type)
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

    def is_sprite_visible(self, sprite, buffer=50):
        """Check if a sprite is visible on screen with an optional buffer."""
        if not hasattr(sprite, 'rect'):
            return False
            
        # Calculate sprite's screen position
        screen_x = sprite.rect.x - self.camera_x
        screen_y = sprite.rect.y - self.camera_y
        
        # Width and height default to 30x30 if not available
        width = getattr(sprite.rect, 'width', 30) 
        height = getattr(sprite.rect, 'height', 30)
        
        # Check if sprite is within the visible screen area with buffer
        return (-width - buffer <= screen_x <= SCREEN_WIDTH + buffer and
                -height - buffer <= screen_y <= SCREEN_HEIGHT + buffer)
    
    def update_sprite_quadrants(self):
        # Only update quadrants for visible sprites
        visible_sprites = []
        for sprite in self.all_sprites:
            if self.is_sprite_visible(sprite):
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

    def update(self):
        if self.state == PLAYING:
            # Start tracking update time
            update_start = time.time()
            
            # Get current time for game mechanics (in milliseconds)
            current_time = pygame.time.get_ticks()
            
            # Handle auto-fire - check weapon fire rate for continuous shooting
            if self.auto_fire:
                weapon = self.player.weapons[self.player.current_weapon]
                if weapon.can_shoot(current_time):
                    self.try_shoot()
                
            # Update camera to follow player
            self.update_camera()
            
            # Get visible enemies (optimization)
            visible_enemies = []
            for enemy in self.enemies:
                if self.is_sprite_visible(enemy):
                    visible_enemies.append(enemy)
            
            # Update sprite quadrants less frequently
            if current_time - self.last_quadrant_update > self.quadrant_update_interval:
                self.update_sprite_quadrants()
                self.last_quadrant_update = current_time
            
            # Update player
            self.player.update(self)
            
            # Clean up off-screen sprites less frequently
            if current_time - self.last_cleanup > self.cleanup_interval:
                self.cleanup_off_screen_sprites()
                self.last_cleanup = current_time
            
            # Update enemies with optimized checks
            should_update_paths = current_time - self.last_path_update > self.path_update_interval
            
            # Track enemy update time
            enemy_update_start = time.time()
            
            # Update all enemies
            for enemy in self.enemies:
                # Update paths for all enemies, but at different intervals based on visibility
                if enemy in visible_enemies:
                    if current_time - enemy.last_path_update > enemy.visible_path_update_interval:
                        enemy.path = self.map.find_path(
                            enemy.rect.centerx, enemy.rect.centery,
                            self.player.rect.centerx, self.player.rect.centery
                        )
                        enemy.path_index = 0
                        enemy.last_path_update = current_time
                else:
                    if current_time - enemy.last_path_update > enemy.path_update_interval:
                        enemy.path = self.map.find_path(
                            enemy.rect.centerx, enemy.rect.centery,
                            self.player.rect.centerx, self.player.rect.centery
                        )
                        enemy.path_index = 0
                        enemy.last_path_update = current_time

                # Always update enemy movement and behavior
                if enemy.type != "standard" and enemy in visible_enemies:
                    should_shoot = enemy.update(self.player, self, self.camera_x, self.camera_y)
                    if should_shoot:
                        bullet = Bullet(
                            enemy.rect.centerx,
                            enemy.rect.centery,
                            self.player.rect.centerx,
                            self.player.rect.centery,
                            "pistol",
                            10
                        )
                        self.enemy_bullets.add(bullet)
                        self.all_sprites.add(bullet)
                else:
                    enemy.update(self.player, self, self.camera_x, self.camera_y)
            
            self.performance_metrics["enemy_update_time"] = time.time() - enemy_update_start
            
            # Track collision detection time
            collision_start = time.time()
            
            # ... existing collision detection code ...
            # Check for bullet collisions with barrels
            barrel_check_start = time.time()
            barrel_hits = pygame.sprite.groupcollide(self.barrels, self.bullets, True, True)
            for barrel, bullets in barrel_hits.items():
                self.all_sprites.remove(barrel)
                for bullet in bullets:
                    self.all_sprites.remove(bullet)
                self.create_explosion(barrel.rect.centerx, barrel.rect.centery, 100)  # Standard explosion damage

            # Check for enemy bullet collisions with barrels
            enemy_barrel_hits = pygame.sprite.groupcollide(self.barrels, self.enemy_bullets, True, True)
            for barrel, bullets in enemy_barrel_hits.items():
                self.all_sprites.remove(barrel)
                for bullet in bullets:
                    self.all_sprites.remove(bullet)
                self.create_explosion(barrel.rect.centerx, barrel.rect.centery, 100)  # Standard explosion damage
            
            self.performance_metrics["barrel_checks_time"] = time.time() - barrel_check_start
            
            # ... rest of collision detection code ...
            
            self.performance_metrics["collision_time"] = time.time() - collision_start
            
            # ... rest of update code ...
            
            if should_update_paths:
                self.last_path_update = current_time
            
            # Update bullets with optimized collision checks
            visible_bullets = [b for b in self.bullets if 
                             -50 <= b.rect.x - self.camera_x <= SCREEN_WIDTH + 50 and
                             -50 <= b.rect.y - self.camera_y <= SCREEN_HEIGHT + 50]
            
            for bullet in visible_bullets:
                bullet.update()
                
                # Check if bullet has reached its target (for rocket launcher)
                if bullet.weapon_type == "rocket_launcher":
                    dx = bullet.rect.centerx - bullet.target_x
                    dy = bullet.rect.centery - bullet.target_y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < 10:  # If close enough to target
                        self.create_explosion(bullet.rect.centerx, bullet.rect.centery, bullet.damage)
                        bullet.kill()
                        self.all_sprites.remove(bullet)
                        continue
                
                # Check for collisions with obstacles
                if self.map.check_collision(bullet):
                    if bullet.weapon_type == "rocket_launcher":
                        self.create_explosion(bullet.rect.centerx, bullet.rect.centery, bullet.damage)
                    bullet.kill()
                    self.all_sprites.remove(bullet)

            # Update explosions and remove expired ones
            for explosion in self.explosions:
                explosion.update()
                if explosion.age >= explosion.lifetime:
                    explosion.kill()
                    self.all_sprites.remove(explosion)

            # Update enemy bullets with optimized collision checks
            for bullet in self.enemy_bullets:
                bullet.update()
                
                # Check for collisions with buildings
                if self.map.check_collision(bullet):
                    bullet.kill()
                    self.all_sprites.remove(bullet)
                    continue
                
                # Check if bullet is off screen with buffer
                screen_x = bullet.rect.centerx - self.camera_x
                screen_y = bullet.rect.centery - self.camera_y
                if (screen_x < -self.screen_buffer or screen_x > SCREEN_WIDTH + self.screen_buffer or 
                    screen_y < -self.screen_buffer or screen_y > SCREEN_HEIGHT + self.screen_buffer):
                    bullet.kill()
                    self.all_sprites.remove(bullet)
                    continue
                    
                # Check for collision with player
                if pygame.sprite.collide_rect(bullet, self.player):
                    self.player.health -= 30 if enemy.type == "officer" else 10
                    bullet.kill()
                    self.all_sprites.remove(bullet)
                    if self.player.health <= 0:
                        if self.score > self.high_score:
                            self.high_score = self.score
                        self.state = GAME_OVER

            # Check for bullet collisions with enemies using optimized group collision
            hits = pygame.sprite.groupcollide(self.enemies, self.bullets, False, True)
            for enemy, bullets in hits.items():
                for bullet in bullets:
                    self.all_sprites.remove(bullet)
                    if bullet.weapon_type == "rocket_launcher":
                        self.create_explosion(bullet.rect.centerx, bullet.rect.centery, bullet.damage)
                    else:
                        enemy.health -= bullet.damage

            # Check for player collision with enemies
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
                        enemy.health -= 5  # Player collision damage
                        self.player.last_collision = current_time
                    
                    if enemy.explode(self):  # Handle assault enemy explosion
                        enemy.kill()
                        self.all_sprites.remove(enemy)
                        self.score += 20
                    
                    if self.player.health <= 0:
                        if self.score > self.high_score:
                            self.high_score = self.score
                        self.state = GAME_OVER

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
            medkit_hits = pygame.sprite.spritecollide(self.player, self.medkits, False)  # Changed to False to not auto-remove
            for medkit in medkit_hits:
                if self.player.stored_medkits < self.player.max_medkits:
                    self.player.stored_medkits += 1
                    medkit.kill()  # Only remove the medkit if we can collect it
                    self.all_sprites.remove(medkit)
                # If at max capacity, ignore the medkit (do nothing)

            # Check for ammo pickup collection
            ammo_hits = pygame.sprite.spritecollide(self.player, self.ammo_pickups, True)
            for ammo in ammo_hits:
                self.all_sprites.remove(ammo)
                weapon = self.player.weapons[ammo.weapon_type]
                if weapon.ammo != float('inf'):
                    weapon.ammo += ammo.ammo_amount

            # Record total update time
            self.performance_metrics["update_time"] = time.time() - update_start

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
            self.state = GAME_OVER

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

    def draw(self):
        # Start tracking render time
        render_start = time.time()
        
        if self.state == MENU:
            self.draw_menu()
        elif self.state == MENU_TUTORIAL:
            self.draw_tutorial()
        elif self.state == GAME_OVER:
            self.draw_game_over()
        elif self.state == PLAYING:
            # Clear screen
            self.screen.fill(WHITE)
            
            # Draw map first
            self.map.draw(self.screen, self.camera_x, self.camera_y)
            
            # Draw only sprites that are visible on screen
            visible_sprites = []
            for sprite in self.all_sprites:
                # Use our helper method to check visibility
                if self.is_sprite_visible(sprite):
                    # Calculate sprite's screen position
                    screen_x = sprite.rect.x - self.camera_x
                    screen_y = sprite.rect.y - self.camera_y
                    # Draw the sprite
                    self.screen.blit(sprite.image, (screen_x, screen_y))
                    # For debugging, count visible sprites
                    visible_sprites.append(sprite)
            
            # Debug print for visible sprites count (can be commented out in production)
            debug_print(f"Visible sprites: {len(visible_sprites)} out of {len(self.all_sprites)}")
            
            # Create semi-transparent overlay for HUD
            hud_overlay = pygame.Surface((SCREEN_WIDTH, 100), pygame.SRCALPHA)
            pygame.draw.rect(hud_overlay, (0, 0, 0, 128), (0, 0, SCREEN_WIDTH, 100))
            self.screen.blit(hud_overlay, (0, 0))
            
            # Draw HUD elements
            self.draw_health_bar(self.screen, 10, 10, 200, 20)
            self.draw_text(f"Score: {self.score}", 36, WHITE, 60, 40)
            self.draw_text(f"Wave: {self.wave}", 36, WHITE, 50, 70)
            self.draw_text(f"High Score: {self.high_score}", 36, YELLOW, SCREEN_WIDTH - 100, 10)
            
            # Create semi-transparent overlay for weapon info
            weapon_overlay = pygame.Surface((200, 100), pygame.SRCALPHA)
            pygame.draw.rect(weapon_overlay, (0, 0, 0, 128), (0, 0, 200, 100))
            self.screen.blit(weapon_overlay, (0, SCREEN_HEIGHT - 100))
            
            # Draw weapon info
            weapon = self.player.weapons[self.player.current_weapon]
            self.draw_text(f"Weapon: {self.player.current_weapon.replace('_', ' ').title()}", 24, WHITE, 100, SCREEN_HEIGHT - 30)
            if weapon.ammo != float('inf'):
                self.draw_text(f"Ammo: {weapon.ammo}", 24, WHITE, 100, SCREEN_HEIGHT - 60)
            
            # Draw medkit count with semi-transparent background
            medkit_overlay = pygame.Surface((200, 30), pygame.SRCALPHA)
            pygame.draw.rect(medkit_overlay, (0, 0, 0, 128), (0, 0, 200, 30))
            self.screen.blit(medkit_overlay, (0, SCREEN_HEIGHT - 90))
            self.draw_text(f"Medkits: {self.player.stored_medkits}/{self.player.max_medkits}", 24, GREEN, 100, SCREEN_HEIGHT - 90)
            
            # Draw minimap
            self.draw_minimap()
            
            # Record render time
            self.performance_metrics["render_time"] = time.time() - render_start
            
            pygame.display.flip()
        elif self.state == PAUSED:
            # First draw the game state
            self.screen.fill(WHITE)
            self.map.draw(self.screen, self.camera_x, self.camera_y)
            for sprite in self.all_sprites:
                screen_x = sprite.rect.x - self.camera_x
                screen_y = sprite.rect.y - self.camera_y
                self.screen.blit(sprite.image, (screen_x, screen_y))
            # Then draw the pause menu on top
            self.draw_pause_menu()

    def run(self):
        self.running = True
        last_frame_time = time.time()
        
        try:
            while self.running:
                # Track frame time
                current_time = time.time()
                self.performance_metrics["frame_time"] = current_time - last_frame_time
                last_frame_time = current_time
                
                # Handle events
                self.handle_events()
                
                # Update game state
                self.update()
                
                # Draw everything
                self.draw()
                
                # Cap the frame rate
                self.clock.tick(FPS)
        finally:
            # Make sure to stop the pathfinding thread when the game ends
            self.pathfinding_manager.stop()
            pygame.quit()

    def __del__(self):
        """Destructor to ensure proper cleanup"""
        if hasattr(self, 'pathfinding_manager'):
            self.pathfinding_manager.stop()
            print("Pathfinding manager thread stopped")
        print("Game instance destroyed")

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
    
    # Set up game monitoring in a separate thread
    import game_monitor
    
    # Start the monitor in a separate thread
    monitor_thread = threading.Thread(target=game_monitor.monitor_game, args=(game,))
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Run the game
    game.run() 