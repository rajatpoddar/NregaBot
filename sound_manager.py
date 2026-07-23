import os
import subprocess
import platform
from typing import List, Tuple
import config
from utils import resource_path


class SoundManager:
    """
    Zero-dependency sound playback.
    
    - macOS:  afplay (built-in, via subprocess)
    - Windows: winsound (built-in, no extra import at play time)
    - Linux:   aplay → paplay → ffplay (fallback chain, via subprocess)
    
    No audio library (pygame, etc.) is needed — pure stdlib + OS utilities.
    """

    def __init__(self, app: object) -> None:
        self.app = app

    def _play_nix(self, sound_file: str) -> bool:
        """Try common Linux CLI players in order of preference."""
        players: List[Tuple[str, List[str]]] = [
            ("aplay",  ["aplay", "-q", sound_file]),
            ("paplay", ["paplay", sound_file]),
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", sound_file]),
        ]
        for name, cmd in players:
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except FileNotFoundError:
                continue
        return False

    def play(self, sound_name: str) -> None:
        """Play a WAV sound file. No dependencies required."""
        # Respect the sound toggle
        if hasattr(self.app, 'sound_switch_var') and not self.app.sound_switch_var.get():
            return

        sound_file = resource_path(f"assets/sounds/{sound_name}.wav")
        if not os.path.exists(sound_file):
            return

        system = platform.system()

        try:
            if system == "Darwin":
                # macOS — afplay is always available
                subprocess.Popen(
                    ["afplay", sound_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            elif system == "Windows":
                # Windows — winsound.PlaySound is built into the interpreter.
                # It plays WAV files asynchronously (SND_ASYNC | SND_FILENAME).
                import winsound
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)

            else:
                # Linux — try aplay, paplay, ffplay
                if not self._play_nix(sound_file):
                    print(f"Warning: No audio player found for '{sound_name}'. "
                          f"Install aplay (alsa-utils) or paplay (pulseaudio-utils).")

        except Exception as e:
            print(f"Error playing sound '{sound_name}': {e}")
