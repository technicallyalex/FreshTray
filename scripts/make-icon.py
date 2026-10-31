"""Draw a small native clock icon without external dependencies."""
import math
from pathlib import Path
import struct

size = 32
pixels = bytearray()
for y in reversed(range(size)):
    for x in range(size):
        dx, dy = x - 15.5, y - 15.5
        radius = math.hypot(dx, dy)
        color = (0, 117, 221, 255) if radius < 15 else (0, 0, 0, 0)
        if 10.3 < radius < 11.7 or (abs(dx) < 1 and -7 < dy < 1) or (abs(dy) < 1 and -1 < dx < 7):
            color = (255, 255, 255, 255)
        r, g, b, a = color
        pixels.extend((b, g, r, a))
bitmap = struct.pack('<IIIHHIIIIII', 40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0) + pixels + bytes(128)
icon = struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(bitmap), 22) + bitmap
(Path(__file__).resolve().parents[1] / 'src/assets/freshtray.ico').write_bytes(icon)
