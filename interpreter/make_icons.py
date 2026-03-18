"""Generate simple PNG app icons using only stdlib (no Pillow needed)."""
import struct, zlib, math
from pathlib import Path

def png_bytes(size: int) -> bytes:
    """Draw a mic-on-purple-gradient icon as a minimal PNG."""
    img = [[(0, 0, 0, 255)] * size for _ in range(size)]
    cx, cy, r = size // 2, size // 2, size // 2

    # Background: dark purple gradient circle
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx*dx + dy*dy)
            if dist <= r:
                t = dist / r
                ri = int(108 - t * 40)
                gi = int(99 - t * 40)
                bi = int(255 - t * 60)
                img[y][x] = (ri, gi, bi, 255)

    # Draw a simple microphone shape (white)
    mic_w = max(4, size // 8)
    mic_h = max(6, size // 4)
    mic_x = cx - mic_w // 2
    mic_y = cy - size // 4

    def set_px(x, y, color=(255, 255, 255, 255)):
        if 0 <= x < size and 0 <= y < size:
            img[y][x] = color

    # Mic body (rounded rect approximation)
    for y in range(mic_y, mic_y + mic_h):
        for x in range(mic_x, mic_x + mic_w):
            set_px(x, y)

    # Mic arc
    arc_r = mic_w * 0.8
    arc_cx, arc_cy = cx, mic_y + mic_h
    for angle_deg in range(0, 181):
        angle = math.radians(angle_deg)
        ax = int(arc_cx + arc_r * math.cos(math.pi - angle))
        ay = int(arc_cy + arc_r * math.sin(angle))
        set_px(ax, ay)
        set_px(ax + 1, ay)

    # Mic stand line
    for y in range(arc_cy, arc_cy + max(3, size // 12)):
        set_px(cx, y)
        set_px(cx + 1, y)

    # Mic base line
    base_w = mic_w
    base_y = arc_cy + max(3, size // 12)
    for x in range(cx - base_w // 2, cx + base_w // 2 + 1):
        set_px(x, base_y)

    # Encode PNG
    def chunk(name, data):
        c = name + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    rows = b''
    for row in img:
        row_bytes = b'\x00'
        for r2, g2, b2, a in row:
            row_bytes += bytes([r2, g2, b2, a])
        rows += row_bytes

    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    idat = zlib.compress(rows, 9)

    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', ihdr)
        + chunk(b'IDAT', idat)
        + chunk(b'IEND', b'')
    )

if __name__ == '__main__':
    icons_dir = Path(__file__).parent / 'static' / 'icons'
    icons_dir.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        path = icons_dir / f'icon-{size}.png'
        path.write_bytes(png_bytes(size))
        print(f'Created {path}')
