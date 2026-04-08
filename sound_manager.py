import os
import sys
import subprocess
import config
from utils import resource_path

class SoundManager:
    def __init__(self, app):
        self.app = app
        self._initialize_audio()

    def _initialize_audio(self):
        """Initializes Pygame mixer in background if on Windows/Linux."""
        if config.OS_SYSTEM != "Darwin":
            try:
                import pygame
                pygame.mixer.init()
            except Exception as e:
                print(f"Warning: Audio mixer init failed: {e}")

    def play(self, sound_name: str):
        """Plays a sound file based on OS."""
        # Check from App Config variable directly
        if hasattr(self.app, 'sound_switch_var') and not self.app.sound_switch_var.get():
            return
        
        sound_file = resource_path(f"assets/sounds/{sound_name}.wav")
        if not os.path.exists(sound_file):
            return

        try:
            if config.OS_SYSTEM == "Darwin":
                # macOS: Native afplay (No lag)
                subprocess.Popen(
                    ["afplay", sound_file], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
            else:
                # Windows: Pygame
                import pygame
                pygame.mixer.Sound(sound_file).play()
        except Exception as e:
            print(f"Error playing sound '{sound_name}': {e}")