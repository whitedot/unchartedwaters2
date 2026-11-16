"""Build the Korean DOS port and terrain patch for the original 짱짱맨 archive."""

import hashlib
from tempfile import NamedTemporaryFile
import struct
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

# Coordinates are in the game's sailing grid, not chart longitude/latitude.
PORTS = (("인천", 934, 378), ("부산", 952, 386), ("서울", 944, 374))
# Two large tiles across at the bend; the fleet occupies four small tiles.
RIVER = [(x, 376) for x in range(932, 946, 2)] + [(940, 374), (942, 374)]
ORIGINAL_TABLE = 0x5F54
PORT_SIZE = 20
DS = 0x355B
HEADER = 0x5400


def word(n):
    return struct.pack("<H", n)


def change(buf, at, old, new):
    if buf[at : at + len(old)] != old or len(old) != len(new):
        raise ValueError(f"Unexpected original instruction at {at:#x}")
    buf[at : at + len(new)] = new


def shipyard_catalog(exe, start, description_id):
    data = exe[HEADER + 16 * DS :]
    block = bytearray(256)
    block[:92] = data[0x764:0x7C0]
    struct.pack_into("<HH", block, 92, 0xFDED, 0xFDF2)
    block[0x60:0x76] = data[0x8C4:0x8DA]
    struct.pack_into("<H", block, 0x76, 0xFDF7)
    template = 0x57CE - 0xC30 + (40 + 22) * 25
    block[0x78:0x91] = start[template : template + 25]
    block[0x78:0x8A] = "거북선".encode("cp949").ljust(18, b"\0")
    block[0x8A] = 25
    block[0x91:0x9D] = struct.pack(
        "<6BH2BH", 0, 100, 100, 100, 45, 45, 3000, 150, 2, 14000
    )
    block[0x9D:0xA5] = bytes([25, 17] + [255] * 6)
    block[0xAA:0xDC] = data[0xB7AA:0xB7DC]
    struct.pack_into("<H", block, 0xDC, description_id)
    for offset, name in ((0xED, "홍삼"), (0xF2, "꽃게"), (0xF7, "용두")):
        block[offset : offset + 4] = name.encode("cp949")
    # Nine entries per table, including the unequipped (0) and Busan (8) rows.
    guns = bytearray()
    for table, value in (
        (0x808, 0xFC90 + 90),
        (0x818, 25),
        (0x828, 5),
        (0x838, 25),
        (0x848, 1000),
    ):
        guns.extend(data[table : table + 16] + word(value))
    guns.extend("천자총통".encode("cp949") + b"\0")
    return block + guns


def append_description(source):
    first = struct.unpack_from(">H", source)[0]
    offsets = struct.unpack_from(f">{first//2}H", source)
    line = (
        "조선의 거북선입니다. 돌격을 위한 튼튼한 선체에 용머리를 달았습니다.".encode(
            "cp949"
        )
        + b"\0"
    )
    return (
        b"".join(struct.pack(">H", v + 2) for v in (*offsets, len(source)))
        + source[first:]
        + line
    )


def append_ship_picture(source):
    first = struct.unpack_from(">I", source)[0]
    assert first == 65 * 4
    offsets = struct.unpack_from(">65I", source)
    art = Path(__file__).with_name("art")
    return (
        b"".join(struct.pack(">I", v + 4) for v in (*offsets, len(source)))
        + source[first:]
        + (art / "geobukseon.graph").read_bytes()
    )


def executable(source, profiles, catalog):
    b = bytearray(source)
    runtime = Path(__file__).with_name("regular_ports.bin").read_bytes()
    assert len(runtime) <= 0x800
    # Give the extension its own DOS load segment BEFORE the native image.
    # Native near pointers and offsets stay unchanged (including SS == DS).
    towns = b"".join(
        struct.pack("<HH15sB", x, y, name.encode("cp949"), 0x16) for name, x, y in PORTS
    )
    prefix = runtime.ljust(0x800, b"\0") + profiles + towns + b"WALK.KEY\0\0\0"
    prefix = prefix.ljust(0x900, b"\0") + catalog
    prefix += bytes(-len(prefix) % 16)
    delta = len(prefix) // 16
    relocated = []
    count = struct.unpack_from("<H", b, 6)[0]
    removed = 0
    for i in range(count):
        off, seg = struct.unpack_from("<HH", b, 0x1E + 4 * i)
        site = HEADER + 16 * seg + off
        if 0x20736 <= site < 0x2079A:
            removed += 1
            continue
        target = struct.unpack_from("<H", b, site)[0]
        struct.pack_into("<H", b, site, target + delta)
        relocated.append((off, seg + delta))
    assert removed == 6

    def hook(site, slot, original, jump=False):
        old = bytes.fromhex(original)
        far = bytes([0xEA if jump else 0x9A]) + word(slot * 3) + word(0)
        change(b, site, old, far.ljust(len(old), b"\x90"))
        offset = site + 3 - HEADER
        relocated.append((offset % 16, offset // 16 + delta))

    hook(0x879E, 21, "161fff365bbd")
    hook(0x1BEDB, 22, "8d1e2c0990")
    hook(0x1B944, 23, "f606300c42")
    hook(0x1BB53, 24, "b86c8b2d300c")
    hook(0xAF90, 13, "558bec50b014f666fe05545f8be55dcb", jump=True)
    hook(0x36AE1, 14, "b014f666ff8bf081c6545f")
    hook(0x181EA, 15, "81fe82007ce3")
    hook(0x208EA, 16, "81ff82007d19")
    hook(0x24B54, 17, "81ff82007d62")
    hook(0x35BD3, 18, "81ff82007d58")
    hook(0x2D38B, 19, "fe46ff83c614")
    change(b, 0x2D36C, bytes([130]), bytes([133]))
    hook(0x277F2, 20, "558bec83ec02", jump=True)

    start, end = 0x20736, 0x2079A
    walk = Path(__file__).with_name("town_walk.bin").read_bytes()
    change(b, start, source[start:end], walk)
    change(
        b,
        0x207E5,
        bytes.fromhex("a0300c24013c011bc024fc050800"),
        bytes.fromhex("a0300c83e00140c1e002")
        + b"\xe8"
        + struct.pack("<h", start + 0x47 - 0x207F2)
        + b"\x90",
    )
    for site in (0xB875, 0xDA3C, 0xDA9E, 0xDB54, 0x2017B, 0x20B88):
        hook(site, 0, "803e3a0c64")
    hook(0xDB1B, 1, "3c647602b064")
    for site in (0xDB99, 0xDBCC):
        hook(site, 2, "a03a0c2ae48bf88a4394")
    hook(0xAFA0, 3, "558bec50b025f666fe057c698be55dcb", jump=True)
    hook(0x36AEF, 4, "b025f666ff8bf081c67c69")
    hook(0x1C80E, 5, "83c7258b76f84683fe64")
    hook(0x1E473, 6, "83c72583c614fe46fd807efd64")

    hook(0x1C8A2, 10, "83c71483c625ff46f8837ef864")
    hook(0x2EDCC, 11, "83c71483c625ff46fc837efc64")
    hook(0x2ECDF, 12, "83c71483c625fe46ff")
    change(b, 0x2ECD2, bytes([99]), bytes([102]))
    change(b, 0x2ECEB, bytes([100]), bytes([103]))

    # Expanded native catalog tables are copied into the reserved page on load.
    hook(0xAF70, 25, "558bec50b019f666fe05ce578be55dcb", jump=True)
    hook(0xAF80, 26, "558bec50b00cf666fe05285e8be55dcb", jump=True)
    hook(0x19664, 25, "b81900f76efe")  # ship name in selection lists
    change(b, 0x1966C, bytes.fromhex("81c3ce57"), b"\x90" * 4)
    hook(0x2FD23, 36, "f7f98846ff")  # shipyard specification card
    hook(0x308CF, 27, "d3e681c652b7")
    hook(0x30AC1, 28, "d3e38a8752b7")
    hook(0xD2F6, 29, "d3e08d5f1c")
    hook(0x30E57, 30, "8946f82bf6")
    hook(0x1E8BA, 31, "8a471d2ae4")
    hook(0x30A27, 32, "8b5ef4884703")
    hook(0x30890, 33, "f7f9ba6400")
    for site in (0x30453, 0x30A30):
        hook(site, 34, "a03a0c0c80")
    hook(0x29A21, 35, "8a5efe2aff")
    hook(0x30E92, 37, "884eff2aed8bc1")
    hook(0x30E5E, 38, "8d44018bde")
    change(b, 0x2FE65, b"\x0b", b"\x0c")
    change(b, 0x199EB, word(0x8C4), word(0xFD60))
    for site in (0x30943, 0x30C07):
        change(b, site, word(0xB7AA), word(0xFDAA))
    for site in (
        0xB930,
        0x196EA,
        0x21BA8,
        0x21D7E,
        0x21DDA,
        0x21DF1,
        0x23292,
        0x2436C,
        0x2456E,
        0x29587,
        0x29682,
        0x29716,
        0x297AD,
        0x298E5,
        0x29AA1,
        0x29F9A,
        0x2A7A9,
        0x2A8AB,
        0x2BBA4,
        0x2BE82,
        0x2BEE2,
    ):
        change(b, site, word(0x764), word(0xFD00))
    change(b, HEADER + 16 * DS + 0x7C9, bytes([46]), bytes([48]))

    # Preserve the stock menu and append a separate saved gun type at Busan.
    hook(0x30F51, 39, "b891008b56ee")
    hook(0x30F6E, 40, "8846f9ff46f6")
    gun_tables = (
        (0x808, (0x19A08, 0x21207, 0x21500, 0x30FC0, 0x31020)),
        (0x818, (0xB0CB, 0x21233, 0x21529)),
        (0x828, (0x14448, 0x22214)),
        (0x838, (0x1447E, 0x2221A)),
        (0x848, (0x31003,)),
    )
    for index, (original, sites) in enumerate(gun_tables):
        for site in sites:
            change(b, site, word(original), word(0xFC90 + 18 * index))
    # Widen gun-type reads (including fleet info, transfer, and battle)
    # and clear all four bits when replacing a ship's guns.
    for site in (
        0xB0C6,
        0x1443C,
        0x21202,
        0x21226,
        0x2122E,
        0x214FB,
        0x2151C,
        0x21524,
        0x2220F,
        0x300D4,
        0x30F98,
        0x3107B,
    ):
        change(b, site, b"\x07", b"\x0f")
    for site in (0x300C9, 0x31092):
        change(b, site, b"\xf8", b"\xf0")

    # The stock class guard counts even defeated fleets as being at sea.
    # Let all existing NPC slots depart when their normal objective calls.
    change(b, 0x383B0, bytes.fromhex("558bec"), bytes.fromhex("31c0cb"))
    hook(0x1E4B3, 41, "c606390c00")
    # Shorter waits keep existing fleets sailing between rebuilds.
    for site, old, new in (
        (0x1EF60, 8, 3),
        (0x1EF68, 8, 3),
        (0x1D5A2, 10, 4),
        (0x1D5AA, 5, 2),
    ):
        change(b, site, bytes([old]), bytes([new]))

    # Relocation locations and the original startup segments move with the
    # native image. The extension targets above remain relative to segment 0.
    assert 0x1E + 4 * len(relocated) <= HEADER
    for i, (off, seg) in enumerate(relocated):
        struct.pack_into("<HH", b, 0x1E + 4 * i, off, seg)
    struct.pack_into("<H", b, 6, len(relocated))
    for field in (0x0E, 0x16):  # initial SS, CS
        struct.pack_into("<H", b, field, struct.unpack_from("<H", b, field)[0] + delta)
    b[HEADER:HEADER] = prefix
    struct.pack_into("<HH", b, 2, len(b) % 512, (len(b) + 511) // 512)
    return b


def asia_terrain(data):
    offsets = struct.unpack_from("<1350H", data)
    edits = {}
    for x, y, tile in [(x, y, 0) for x, y in RIVER] + [
        (x, y, 0x10) for _, x, y in PORTS
    ]:
        col, row = (x - 720) // 2, y // 2
        edits.setdefault(row // 12 * 30 + col // 12, {})[
            row % 12 * 12 + col % 12
        ] = tile
    # DOS seeks to the first block of each visible row, then reads three
    # consecutive blocks. Rebuild the stream in row order after resizing.
    blocks = bytearray(2700)
    ends = (*offsets[1:], len(data) - 2700)
    for index, offset in enumerate(offsets):
        pos = 2700 + offset
        struct.pack_into("<H", blocks, index * 2, len(blocks) - 2700)
        if index not in edits:
            blocks.extend(data[pos : 2700 + ends[index]])
            continue
        replacements = edits[index]
        head = data[pos]
        mask = int.from_bytes(data[pos + 1 : pos + 19], "big") if head < 128 else 0
        cursor = pos + 19
        changed = {}
        for cell in range(144):
            if mask & (1 << (143 - cell)):
                changed[cell] = data[cursor]
                cursor += 1
        changed.update(replacements)
        mask = sum(1 << (143 - cell) for cell in changed)
        blocks.append(head & 127)
        blocks.extend(mask.to_bytes(18, "big"))
        blocks.extend(changed[cell] for cell in sorted(changed))
    return blocks


def decode(stream, table, size):
    bits = iter("".join(f"{x:08b}" for x in stream))

    def value():
        width = 1
        while next(bits) == "1":
            width += 1
        return (1 << width) - 2 + int("".join(next(bits) for _ in range(width)), 2)

    out = bytearray()
    while len(out) < size:
        n = value()
        if n < 256:
            out.append(table[n])
        else:
            for _ in range(value() + 3):
                out.append(out[-(n - 256)])
    return out


def encode(data, table):
    # LS11 backreferences may overlap. Limit the search to the most recent
    # matching triplet; compression ratio is secondary on this 22 KiB map.
    codes = []

    def emit(n):
        w = (n + 2).bit_length() - 1
        codes.append("1" * (w - 1) + "0" + format(n + 2 - (1 << w), f"0{w}b"))

    literal = {v: i for i, v in enumerate(table)}
    recent = {}
    i = 0
    while i < len(data):
        k = bytes(data[i : i + 3])
        prev = recent.get(k)
        length = 0
        if prev is not None and len(k) == 3:
            while i + length < len(data) and data[i + length] == data[prev + length]:
                length += 1
        if length >= 3:
            emit(256 + i - prev)
            emit(length - 3)
        else:
            emit(literal[data[i]])
            length = 1
        for j in range(i, i + length):
            recent[bytes(data[j : j + 3])] = j
        i += length
    bits = "".join(codes)
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[j : j + 8], 2) for j in range(0, len(bits), 8))


def world_map(source):
    result = bytearray(source)
    entry = 0x110 + 12  # Asian map
    compressed, size, offset = struct.unpack_from(">III", source, entry)
    table = source[16:272]
    asia = asia_terrain(decode(source[offset : offset + compressed], table, size))
    packed = encode(asia, table)
    assert decode(packed, table, len(asia)) == asia
    # Keep the other entries' original offsets and compressed streams.
    struct.pack_into(">III", result, entry, len(packed), len(asia), len(result))
    result.extend(packed)
    return result


def archive_entry(source, i):
    n, size, offset = struct.unpack_from(">III", source, 272 + 12 * i)
    return decode(source[offset : offset + n], source[16:272], size)


def town_assets(source, entrances):
    """Keep the original archive payload; append three independent town maps."""
    reference = (0, 2, 1)  # Lisbon, Istanbul, Seville
    towns = {i: archive_entry(source, i) for i in (94, 95, 97)}
    extra = []
    coords = bytearray(entrances + entrances[-24:] * 29)
    for city, ref in enumerate(reference):
        record = bytearray(entrances[24 * ref : 24 * (ref + 1)])
        town = bytearray([4]) * 9216

        def stamp(donor, sx, sy, x, y, width, height):
            assert 0 <= x <= 96 - width and 0 <= y <= 96 - height
            for dy in range(height):
                a = (sy + dy) * 96 + sx
                b = (y + dy) * 96 + x
                town[b : b + width] = towns[donor][a : a + width]

        # Quays follow the estuary, eastern strait, and Han river respectively.
        for y in range(96):
            for x in range(96):
                edge = (
                    73 + min(7, abs(x - 23) // 4) + (4 if 47 <= x <= 61 else 0),
                    75 + min(10, abs(y - 28) // 3) + (3 if 46 <= y <= 57 else 0),
                    75 + min(5, abs(x - 69) // 8) + (4 if 35 <= x <= 50 else 0),
                )[city]
                depth = (x if city == 1 else y) - edge
                if depth >= -5:
                    town[96 * y + x] = (
                        0x3A
                        if depth >= 1
                        else (0x3C if city == 1 else 0x31) if depth == 0 else 0x0D
                    )
                elif x < 5 or y < 3 or x >= 92 or y >= 91:
                    town[96 * y + x] = 0x06
        # Wide avenues connect the waterfront squares to the northern compound.
        for f in (0, 1, 2, 3, 4, 6, 8, 9):
            x, y = record[f * 2 : f * 2 + 2]
            for yy in range(y + 2, y + 5):
                for xx in range(min(x, 48) - 2, max(x, 48) + 4):
                    town[yy * 96 + xx] = 0x0D
        for yy in range(19, 74):
            town[yy * 96 + 46 : yy * 96 + 52] = bytes([0x0D]) * 6

        # A complete East Asian walled compound and ornamental groves.
        px, py = record[10:12]
        stamp(97, 33, 0, px - 14, max(0, py - 14), 32, 19)

        # Grass courtyards with clipped corners, trees, and residential lanes.
        def garden(x, y, w, h):
            for j in range(h):
                for i in range(w):
                    edge = (j in (0, h - 1), i in (0, w - 1))
                    tile = 0x06
                    if edge == (True, True):
                        tile = ((0x09, 0x07), (0x00, 0x02))[j == h - 1][i == w - 1]
                    elif edge[0]:
                        tile = 0x08 if j == 0 else 0x01
                    elif edge[1]:
                        tile = 0x05 if i == 0 else 0x03
                    elif j % 3 == 1 and i % 4 == 2:
                        tile = 0x52
                    town[(y + j) * 96 + x + i] = tile

        for box in (
            ((9, 26, 17, 9), (51, 44, 12, 9), (60, 60, 10, 7), (29, 72, 12, 4)),
            ((8, 31, 17, 8), (49, 28, 16, 9), (64, 52, 7, 8), (28, 70, 11, 6)),
            ((8, 25, 21, 8), (58, 24, 15, 10), (49, 62, 12, 8), (22, 66, 10, 6)),
        )[city]:
            garden(*box)
        # A local temple marks the original cathedral square. The royal court
        # and temple are scenery and do not dispatch European story scripts.
        tx, ty = record[20:22]
        stamp(94, 31, 32, tx - 5, ty - 6, 12, 8)
        for x, y in (
            ((16, 14), (69, 25), (69, 57), (19, 68)),
            ((50, 13), (18, 38), (36, 57), (48, 77)),
            ((15, 14), (68, 13), (49, 34), (49, 72)),
        )[city]:
            # Small blue-tiled row houses, without shop signs/entrances.
            for dy, row in enumerate(
                (
                    (0x49,) * 6,
                    (0x54,) * 6,
                    (0x5D,) * 6,
                    (0x67, 0x68, 0x60, 0x68, 0x60, 0x61),
                    (0x26, 0x2C, 0x27, 0x2D, 0x27, 0x2F),
                )
            ):
                pos = (y + dy) * 96 + x
                town[pos : pos + 6] = bytes(row)

        # Native facades include the doorway's two collision tiles. Guild and
        # fortune teller share a building in Changan; use separate Macao shops.
        for f in range(12):
            x, y = record[f * 2 : f * 2 + 2]
            if f in (5, 7, 10) or x == 255:
                record[2 * f : 2 * f + 2] = b"\xff\xff"
                continue
            donor = 95 if f in (6, 11) else 97
            sx, sy = entrances[donor * 24 + 2 * f : donor * 24 + 2 * f + 2]
            row = towns[donor][(sy + 1) * 96 : (sy + 2) * 96]
            left = row.rindex(0x26, 0, sx + 1)
            right = row.index(0x2F, sx)
            roof = next(
                h
                for h in range(3, 7)
                if towns[donor][(sy - h) * 96 + sx] in (0x48, 0x49)
            )
            stamp(
                donor,
                left,
                sy - roof,
                x + left - sx,
                y - roof,
                right - left + 1,
                roof + 2,
            )

        # Verify the native two-tile foot test from the dock to every doorway.
        from collections import deque

        doors = list(zip(record[::2], record[1::2]))
        x, y = doors[3]
        queue = deque([(x, y + 1)])
        seen = set(queue)
        while queue:
            x, y = queue.popleft()
            for a, b in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not (0 <= a < 94 and 0 <= b < 94) or (a, b) in seen:
                    continue
                l, r = town[(b + 1) * 96 + a : (b + 1) * 96 + a + 2]
                if l < 0x2A and (r < 0x25 or 0x2A <= r < 0x30):
                    seen.add((a, b))
                    queue.append((a, b))
        assert all(p in seen or p == (255, 255) for p in doors), (
            city,
            doors,
            seen & set(doors),
        )
        coords.extend(record)
        extra.append(town)

    shift = 32 * 12
    head = bytearray(source[:272])
    for i in range(130):
        c, n, o = struct.unpack_from(">III", source, 272 + 12 * min(i, 100))
        head.extend(struct.pack(">III", c, n, o + shift))
    payload = bytearray(source[272 + 101 * 12 + 4 :])
    for town in extra:
        packed = encode(town, source[16:272])
        offset = 272 + 133 * 12 + 4 + len(payload)
        head.extend(struct.pack(">III", len(packed), 9216, offset))
        payload.extend(packed)
    result = head + bytes(4) + payload
    assert all(archive_entry(result, 130 + i) == town for i, town in enumerate(extra))
    return result, coords


def build(src, dest):
    if src.resolve() == dest.resolve():
        raise ValueError("Use a separate output file")
    with NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
        pass
    try:
        with ZipFile(src) as base, ZipFile(tmp.name, "w", ZIP_DEFLATED) as out:
            if not PATCHES.keys() <= set(base.namelist()):
                raise ValueError("Required DOS files missing")
            start = archive_entry(base.read("DATA1.LZW"), 15)
            for i in range(121):
                pos = ORIGINAL_TABLE - 0xC30 + 20 * i
                if i != 53:
                    assert 0 in start[pos + 4 : pos + 18] and start[pos + 18] == 0
            pos = 0x697C - 0xC30
            profiles = b"".join(
                start[pos + i * 37 : pos + (i + 1) * 37] for i in (94, 95, 97)
            )
            profiles = bytearray(profiles)
            for city, good, price in ((0, 47, 12), (2, 46, 32)):
                struct.pack_into("<HBB", profiles, city * 37 + 24, price, good, 0)
            catalog = shipyard_catalog(
                base.read("MAIN.EXE"),
                start,
                struct.unpack(">H", base.read("MESSAGE.DAT")[:2])[0] // 2,
            )
            maps, coords = town_assets(
                base.read("PORTMAP.LZW"), base.read("ZA_DAT.DAT")
            )
            for member in base.infolist():
                data = base.read(member)
                if member.filename == "MESSAGE.DAT":
                    data = append_description(data)
                elif member.filename == "GRAPH.DAT":
                    data = append_ship_picture(data)
                elif member.filename == "TRANSIT.DAT":
                    assert len(data) == 0x1980 + 11 * 0x480
                    data += (
                        Path(__file__)
                        .with_name("art")
                        .joinpath("yongdu.transit")
                        .read_bytes()
                    )
                if member.filename in PATCHES:
                    expected, patch = PATCHES[member.filename]
                    if hashlib.sha256(data).hexdigest() != expected:
                        raise ValueError(
                            f"Unexpected input version of {member.filename}"
                        )
                    if member.filename == "MAIN.EXE":
                        data = patch(data, profiles, catalog)
                    elif member.filename == "PORTMAP.LZW":
                        data = maps
                    elif member.filename == "ZA_DAT.DAT":
                        data = coords
                    else:
                        data = patch(data)
                out.writestr(member, data)
        Path(tmp.name).chmod(0o644)
        Path(tmp.name).replace(dest)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


PATCHES = {
    "PORTMAP.LZW": (
        "ed3161c45b038fbc715840e9798bc4a2d3c5615d036b27c8048e93c8c6b7c25d",
        None,
    ),
    "ZA_DAT.DAT": (
        "6760ebc1cdb7356b3f6a66c67fed1a3e29eb3e357a9958ff698b4598774ad92a",
        None,
    ),
    "MAIN.EXE": (
        "1718bbbbcdd938dfe44403d9bd5254dfc02d431217dea39ae5fb3fcde1597747",
        executable,
    ),
    "WORLDMAP.LZW": (
        "135e89cb1c894a8a70c67168898b816fab00a6a7d13a61f5965bacfaec6986fa",
        world_map,
    ),
}

if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
