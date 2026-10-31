"""Original local chimes with app-only PCM volume and asynchronous playback."""
from array import array
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import threading
import wave
import winsound

SOUNDS = {'ethereal': ('Ethereal', 'reminder.wav'),
          'warm_bell': ('Warm Bell', 'warm_bell.wav'),
          'glass_drops': ('Glass Drops', 'glass_drops.wav'),
          'soft_horizon': ('Soft Horizon', 'soft_horizon.wav'),
          'low_pulse': ('Low Pulse', 'low_pulse.wav'),
          'soft_breath': ('Soft Breath', 'soft_breath.wav'),
          'punchcard': ('Punchcard', 'punchcard.wav'),
          'relay_click': ('Relay Click', 'relay_click.wav'),
          'servo_sweep': ('Servo Sweep', 'servo_sweep.wav')}


def sound_settings(sound, volume):
    if not isinstance(sound, str) or sound not in SOUNDS:
        raise ValueError('Choose one of the available reminder sounds.')
    if type(volume) not in (int, float) or not 0 <= volume <= 100:
        raise ValueError('Choose a sound volume between 0 and 100 percent.')
    return sound, round(volume)


class PopupChime:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='FreshTraySound')
        self.generation, self.closed = 0, False
        self.folder = None
        self.cache = OrderedDict()

    def play(self, sound='ethereal', volume=60):
        try:
            sound, volume = sound_settings(sound, volume)
        except ValueError:
            sound, volume = 'ethereal', 60
        with self.lock:
            if self.closed:
                return None
            self.generation += 1
            generation = self.generation
            try:
                winsound.PlaySound(None, 0)
            except (RuntimeError, OSError):
                pass
            if volume == 0:
                return None
            return self.executor.submit(self._play, sound, volume, generation)

    def _play(self, sound, volume, generation):
        with self.lock:
            if self.closed or generation != self.generation:
                return
        source = self.path if sound == 'ethereal' else self.path.parent/SOUNDS[sound][1]
        if not source.is_file():
            return
        try:
            # Normal 60% preserves the preceding build's reminder level. Scale
            # the waveform itself; never touch system or device volume.
            key = (sound, volume)
            target = source
            if volume != 60:
                if self.folder is None:
                    self.folder = tempfile.TemporaryDirectory(prefix='FreshTray-audio-')
                target = self.cache.get(key)
                if target is None:
                    target = Path(self.folder.name)/f'{sound}-{volume}.wav'
                    with wave.open(str(source), 'rb') as audio:
                        if (audio.getnchannels(), audio.getsampwidth()) != (1, 2):
                            return
                        rate = audio.getframerate()
                        pcm = array('h', audio.readframes(audio.getnframes()))
                    if sys.byteorder != 'little': pcm.byteswap()
                    pcm = array('h', (max(-32768, min(32767, round(v*volume/60))) for v in pcm))
                    if sys.byteorder != 'little': pcm.byteswap()
                    with wave.open(str(target), 'wb') as audio:
                        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(rate); audio.writeframes(pcm.tobytes())
                    self.cache[key] = target
                    while len(self.cache) > 8:
                        _, old = self.cache.popitem(last=False)
                        try: old.unlink(missing_ok=True)
                        except OSError: pass
                else:
                    self.cache.move_to_end(key)
            with self.lock:
                if self.closed or generation != self.generation:
                    return
                winsound.PlaySound(str(target), winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
        except (RuntimeError, OSError, ValueError, wave.Error, EOFError):
            pass  # Missing files or unavailable output never block the popup.

    def stop(self):
        with self.lock:
            self.generation += 1  # Cancel an older preview still being prepared.
            try: winsound.PlaySound(None, 0)
            except (RuntimeError, OSError): pass

    def close(self):
        self.stop()
        with self.lock:
            self.closed = True
        self.executor.shutdown(wait=True, cancel_futures=True)
        if self.folder:
            self.folder.cleanup()
