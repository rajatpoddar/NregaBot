import os
import subprocess
import platform
from typing import Dict, List, Optional, Tuple
from src import config
from src.utils import resource_path


class SoundManager:
    """
    Zero-dependency sound playback with optimizations:
    
    - macOS:  afplay with single-instance reuse (kills previous before starting new)
    - Windows: winsound (built-in, async, no extra process)
    - Linux:   aplay → paplay → ffplay (fallback chain, via subprocess)
    
    Optimizations:
    - Path caching: resolved file paths stored to avoid repeated disk lookups
    - macOS single-process: tracks last afplay PID and kills it before playing
      a new sound — prevents cacophony from rapid clicks
    
    No audio library (pygame, etc.) is needed — pure stdlib + OS utilities.
    """

    def __init__(self, app: object) -> None:
        self.app = app
        self._path_cache: Dict[str, str] = {}  # sound_name -> resolved file path
        self._last_process: Optional[subprocess.Popen] = None  # macOS: track last afplay

    def _get_sound_path(self, sound_name: str) -> Optional[str]:
        """Get cached sound file path. Resolves and caches on first access."""
        if sound_name not in self._path_cache:
            path = resource_path(f"assets/sounds/{sound_name}.wav")
            if not os.path.exists(path):
                self._path_cache[sound_name] = ""  # Mark as missing
                return None
            self._path_cache[sound_name] = path
        path = self._path_cache.get(sound_name, "")
        return path if path else None

    def _play_macos(self, sound_file: str) -> None:
        """Play sound on macOS using afplay.
        Kills the previous afplay process before starting a new one
        to prevent overlapping sounds (cacophony from rapid clicks)."""
        # Kill previous afplay if still running
        if self._last_process is not None:
            try:
                if self._last_process.poll() is None:  # Still running
                    self._last_process.kill()
                    self._last_process.wait(timeout=0.5)
            except Exception:
                pass
            self._last_process = None

        self._last_process = subprocess.Popen(
            ["afplay", sound_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _play_nix(self, sound_file: str) -> bool:
        """Try common Linux CLI players in order of preference."""
        players: List[Tuple[str, List[str]]] = [
            ("aplay",  ["aplay", "-q", sound_file]),
            ("paplay", ["paplay", sound_file]),
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", sound_file]),
        ]
        for name, cmd in players:
            try:
                self._last_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except FileNotFoundError:
                continue
        return False

    def play(self, sound_name: str) -> None:
        """Play a WAV sound file. Optimized with caching and single-instance afplay."""
        # Respect the sound toggle (defensive: never crash if the toggle var
        # is missing or not yet initialized — treat missing as 'sound on').
        try:
            switch = getattr(self.app, 'sound_switch_var', None)
            if switch is not None and hasattr(switch, 'get') and not switch.get():
                return
        except Exception:
            pass

        sound_file = self._get_sound_path(sound_name)
        if not sound_file:
            return

        system = platform.system()

        try:
            if system == "Darwin":
                # macOS — afplay with single-instance (kills previous to avoid cacophony)
                self._play_macos(sound_file)

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

    def cleanup(self) -> None:
        """Kill any lingering audio subprocess on app shutdown.
        Prevents orphan afplay/aplay processes after app closes."""
        if self._last_process is not None:
            try:
                if self._last_process.poll() is None:  # Still running
                    self._last_process.kill()
                    self._last_process.wait(timeout=0.5)
            except Exception:
                pass
            self._last_process = None
