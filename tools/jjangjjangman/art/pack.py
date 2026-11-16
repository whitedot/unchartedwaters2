"""Pack the two indexed illustrations. Requires Pillow only when editing the art."""

import struct
from pathlib import Path
from PIL import Image

here = Path(__file__).parent
ship = Image.open(here / "geobukseon.png")
assert ship.mode == "P" and ship.size == (128, 96)
graph = bytearray(struct.pack("<HH8H", 128, 96, *([0] * 8)))
for y in range(96):
    for x in range(0, 128, 4):
        value = sum(
            ((ship.getpixel((x + i, y)) >> plane) & 1) << (4 * plane + 3 - i)
            for plane in range(4)
            for i in range(4)
        )
        graph.extend(struct.pack(">BH", 0x38, value))
(here / "geobukseon.graph").write_bytes(graph)

head = Image.open(here / "yongdu.png")
assert head.mode == "P" and head.size == (48, 48)
planes = bytes(
    sum(((head.getpixel((x + i, y)) >> plane) & 1) << (7 - i) for i in range(8))
    for y in range(48)
    for x in range(0, 48, 8)
    for plane in range(4)
)
(here / "yongdu.transit").write_bytes(planes)
