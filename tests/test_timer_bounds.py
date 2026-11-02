"""Window-area clamping, including negative monitor coordinates and taskbars."""
import unittest
from unittest.mock import patch
import _paths
from PySide6.QtCore import QRect
from freshtray.work_timer import WorkTimer

class Screen:
    def __init__(self,*rect):self.rect=QRect(*rect)
    def availableGeometry(self):return self.rect

class TimerBoundsTests(unittest.TestCase):
    def clamp(self,rect,screens=None):
        with patch('freshtray.work_timer.QGuiApplication.screens',return_value=screens or [Screen(0,0,1920,1032)]):
            return WorkTimer.constrainPosition(None,*rect)
    def test_all_edges_use_whole_window(self):
        for x,y in [(-100,200),(1900,200),(100,-50),(100,1020),(-500,-500),(4000,4000)]:
            p=self.clamp((x,y,260,370))
            self.assertGreaterEqual(p['x'],0);self.assertGreaterEqual(p['y'],0)
            self.assertLessEqual(p['x']+260,1920);self.assertLessEqual(p['y']+370,1032)
    def test_growing_near_bottom_moves_whole_expanded_window(self):
        p=self.clamp((1800,950,260,370));self.assertEqual((p['x'],p['y']),(1660,662))
    def test_negative_coordinate_monitor(self):
        p=self.clamp((-2000,50,170,170),[Screen(-1920,0,1920,1080),Screen(0,0,1920,1032)])
        self.assertEqual(p['x'],-1920)
    def test_monitor_chosen_by_window_overlap(self):
        p=self.clamp((-100,100,260,370),[Screen(-1920,0,1920,1080),Screen(0,0,1920,1032)])
        self.assertEqual(p['x'],0)
    def test_saved_position_on_removed_monitor(self):
        p=self.clamp((-3000,200,170,170));self.assertEqual(p['x'],0)

if __name__=='__main__':unittest.main()
