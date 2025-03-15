import pygame
import time
import datetime
import threading

class GameMonitor:
    def __init__(self):
        # Create timestamped log file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"game_log_{timestamp}.txt"
        
        # Initialize tracking variables
        self.start_time = time.time()
        self.last_event_time = time.time()
        
        # Define game states for logging
        self.game_states = {
            0: "MENU",
            1: "MENU_TUTORIAL",
            2: "PLAYING", 
            3: "GAME_OVER",
            4: "PAUSED",
            5: "INGAME_TUTORIAL"
        }
        
        # Open log file and write header
        with open(self.log_file, 'w') as f:
            f.write("Game Monitor Log\n")
            f.write("================\n\n")
    
    def log_event(self, event_type, details):
        current_time = time.time()
        elapsed = current_time - self.start_time
        event_time = current_time - self.last_event_time
        
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {event_type}: {details} (Elapsed: {elapsed:.2f}s, Since last: {event_time:.2f}s)\n"
        
        print(log_entry.strip())  # Print to console
        with open(self.log_file, 'a') as f:
            f.write(log_entry)
        
        self.last_event_time = current_time
    
    def monitor_game_state(self, game):
        """Log the current game state and player information"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        since_last = current_time - self.last_event_time
        self.last_event_time = current_time
        
        # Get current game state
        state_name = "UNKNOWN"
        if hasattr(game, 'state'):
            if game.state == 0:
                state_name = "MENU"
            elif game.state == 1:
                state_name = "MENU_TUTORIAL"
            elif game.state == 2:
                state_name = "PLAYING"
            elif game.state == 3:
                state_name = "GAME_OVER"
            elif game.state == 4:
                state_name = "PAUSED"
            elif game.state == 5:
                state_name = "INGAME_TUTORIAL"
        
        self.log_event("Game State", f"Current state: {state_name} (Elapsed: {elapsed:.2f}s, Since last: {since_last:.2f}s)")
        
        # Log player information if available
        if hasattr(game, 'player') and game.player is not None:
            self.log_event("Player Status", 
                          f"Position: ({game.player.rect.x}, {game.player.rect.y}), "
                          f"Health: {game.player.health}, "
                          f"Current Weapon: {game.player.current_weapon}")
        
        # Monitor key presses
        keys = pygame.key.get_pressed()
        pressed_keys = [pygame.key.name(i) for i, v in enumerate(keys) if v]
        if pressed_keys:
            self.log_event("Key Press", f"Pressed keys: {', '.join(pressed_keys)}")
        
        # Monitor mouse position and buttons
        mouse_pos = pygame.mouse.get_pos()
        mouse_buttons = pygame.mouse.get_pressed()
        if any(mouse_buttons):
            self.log_event("Mouse", f"Position: {mouse_pos}, Buttons: {mouse_buttons}")
        
        # Monitor sprite counts
        if hasattr(game, 'all_sprites'):
            self.log_event("Sprites", 
                          f"Total: {len(game.all_sprites)}, "
                          f"Enemies: {len(game.enemies)}, "
                          f"Bullets: {len(game.bullets)}")

def monitor_game(game):
    """Monitor game state and log information"""
    monitor = GameMonitor()
    
    try:
        while getattr(game, 'running', True):
            try:
                monitor.monitor_game_state(game)
                
                # Log sprite counts
                if hasattr(game, 'all_sprites') and hasattr(game, 'enemies') and hasattr(game, 'bullets'):
                    monitor.log_event("Sprites", 
                                    f"Total: {len(game.all_sprites)}, "
                                    f"Enemies: {len(game.enemies)}, "
                                    f"Bullets: {len(game.bullets)}")
                
                # Log key presses
                keys = pygame.key.get_pressed()
                pressed = [chr(i) for i in range(len(keys)) if keys[i] and 32 <= i < 127]
                monitor.log_event("Key Press", f"Pressed keys: {', '.join(pressed)}")
                
                # Log mouse state
                mouse_pos = pygame.mouse.get_pos()
                mouse_buttons = pygame.mouse.get_pressed()
                monitor.log_event("Mouse", f"Position: {mouse_pos}, Buttons: {mouse_buttons}")
                
            except Exception as e:
                monitor.log_event("ERROR", str(e))
            time.sleep(0.1)  # Sleep to reduce CPU usage
    except:
        pass
    
    # Final log entry
    try:
        monitor.log_event("Monitor", "Game monitoring stopped")
    except:
        pass

if __name__ == "__main__":
    # Import and run the game with monitoring
    import alien_shooter
    
    # Create the game instance first
    game = alien_shooter.Game()
    
    # Start the monitor in a separate thread
    monitor_thread = threading.Thread(target=monitor_game, args=(game,))
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Run the game
    game.run() 