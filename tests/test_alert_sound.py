from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
from array import array
import hashlib
import _paths
from freshtray.alert_sound import PopupChime, SOUNDS, sound_settings

ASSETS = Path(__file__).resolve().parents[1]/'src/assets/sounds'

class ChimeTests(unittest.TestCase):
    def test_presets_are_distinct_short_pcm_with_headroom_and_soft_endpoints(self):
        hashes = set()
        for key, (_, filename) in SOUNDS.items():
            path = ASSETS/filename
            with self.subTest(sound=key), wave.open(str(path),'rb') as audio:
                self.assertEqual((audio.getnchannels(),audio.getsampwidth(),audio.getframerate()),(1,2,44100))
                self.assertGreaterEqual(audio.getnframes()/audio.getframerate(),1.0)
                self.assertLessEqual(audio.getnframes()/audio.getframerate(),3.0)
                values=array('h',audio.readframes(audio.getnframes()))
                self.assertLessEqual(max(abs(v) for v in values),10500)
                self.assertEqual(values[0],0); self.assertLessEqual(abs(values[-1]),1)
            hashes.add(hashlib.sha256(path.read_bytes()).digest())
        self.assertEqual(len(hashes),len(SOUNDS))
    def test_play_is_async_and_never_falls_back_to_system_beep(self):
        import winsound
        with patch('freshtray.alert_sound.winsound.PlaySound') as play:
            chime=PopupChime(ASSETS/'reminder.wav')
            self.addCleanup(chime.close)
            chime.play().result(timeout=2)
            flags=play.call_args.args[1]
            self.assertTrue(flags & winsound.SND_ASYNC)
            self.assertTrue(flags & winsound.SND_FILENAME)
            self.assertTrue(flags & winsound.SND_NODEFAULT)
            chime.stop(); self.assertEqual(play.call_args.args,(None,0))
    def test_volume_scales_only_local_waveform_and_zero_is_silent(self):
        with patch('freshtray.alert_sound.winsound.PlaySound') as play:
            chime=PopupChime(ASSETS/'reminder.wav')
            try:
                with wave.open(str(ASSETS/'warm_bell.wav'),'rb') as audio:
                    base=array('h',audio.readframes(audio.getnframes()))
                chime.play('warm_bell',30).result(timeout=2)
                target=Path(play.call_args.args[0])
                with wave.open(str(target),'rb') as audio:
                    soft=array('h',audio.readframes(audio.getnframes()))
                self.assertLessEqual(abs(max(map(abs,soft))-max(map(abs,base))*.5),1)
                chime.play('warm_bell',100).result(timeout=2)
                with wave.open(str(play.call_args.args[0]),'rb') as audio:
                    loud=array('h',audio.readframes(audio.getnframes()))
                self.assertLess(max(map(abs,loud)),32767)
                self.assertGreater(max(map(abs,loud)),max(map(abs,base)))
                play.reset_mock(); self.assertIsNone(chime.play('warm_bell',0))
                self.assertTrue(all(call.args[0] is None for call in play.call_args_list))
            finally:
                chime.close()
            self.assertFalse(target.exists())
    def test_missing_asset_or_unavailable_audio_is_nonfatal(self):
        with patch('freshtray.alert_sound.winsound.PlaySound') as play:
            chime=PopupChime(Path('not-a-real-chime.wav'))
            try:
                chime.play().result(timeout=2)
                self.assertTrue(all(call.args[0] is None for call in play.call_args_list))
            finally: chime.close()
        with patch('freshtray.alert_sound.winsound.PlaySound',side_effect=RuntimeError('No audio device')):
            chime=PopupChime(ASSETS/'reminder.wav')
            try: chime.play().result(timeout=2); chime.stop()
            finally: chime.close()
    def test_volume_cache_is_bounded(self):
        with patch('freshtray.alert_sound.winsound.PlaySound'):
            chime=PopupChime(ASSETS/'reminder.wav')
            try:
                for volume in range(5,55,5): chime.play('ethereal',volume).result(timeout=2)
                self.assertLessEqual(len(chime.cache),8)
                self.assertLessEqual(len(list(Path(chime.folder.name).glob('*.wav'))),8)
            finally: chime.close()
    def test_invalid_sound_settings_are_rejected(self):
        for sound, volume in [('unknown',60),([],60),('ethereal',-1),('ethereal',101),('ethereal',True),('ethereal','50')]:
            with self.subTest(sound=sound,volume=volume), self.assertRaises(ValueError): sound_settings(sound,volume)

    def test_existing_sound_is_preserved_for_followup_then_choices_persist_separately(self):
        import json
        from freshtray.storage import Preferences
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            path.write_text(json.dumps({'popup_sound_choice':'servo_sweep','popup_volume':35}))
            prefs=Preferences(path)
            self.assertEqual(prefs.data['remind_me_sound_choice'],'servo_sweep')
            prefs.save(remind_me_sound_choice='punchcard')
            loaded=Preferences(path)
            self.assertEqual(loaded.data['popup_sound_choice'],'servo_sweep')
            self.assertEqual(loaded.data['remind_me_sound_choice'],'punchcard')
            self.assertEqual(loaded.data['popup_volume'],35)
