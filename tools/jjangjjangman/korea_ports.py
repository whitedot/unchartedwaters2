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
PORT_TABLE = 0xC800
PORT_SIZE = 20
DS = 0x355B
HEADER = 0x5400


def word(n):
    return struct.pack("<H", n)


def change(buf, at, old, new):
    if buf[at : at + len(old)] != old or len(old) != len(new):
        raise ValueError(f"Unexpected original instruction at {at:#x}")
    buf[at : at + len(new)] = new


def executable(source, profiles):
    b = bytearray(source)
    # The Korean program clears BSS through DS:C6FF. Place the extension
    # directly above it, below the downward-growing stack. Keep the original
    # stack top: the DOS allocator derives its graphics arena from that value.
    for p in (0xAF9A, 0x36AEA):
        change(b, p, word(ORIGINAL_TABLE), word(PORT_TABLE))
    # Known ports, coordinate lookup, chart inspection, lookout, duplicate names.
    for p in (0x181EC, 0x208EC, 0x24B56, 0x35BD5, 0x2D36C):
        change(b, p, b"\x82", b"\x85")
    # The map renderer's hash index is authored for the old coordinates.
    # Use the same register contract as its original far routine (AX=x, DX=y).
    lookup = (
        bytes.fromhex("53 51 56 be")
        + word(PORT_TABLE)
        + bytes.fromhex(
            "31 db b9 85 00 39 04 75 05 39 54 02 74 0b 83 c6 14 43 e2 f1 "
            "b8 ff ff eb 02 89 d8 5e 59 5b cb"
        )
    )
    change(b, 0x277F2, source[0x277F2 : 0x277F2 + len(lookup)], lookup)

    db = HEADER + DS * 16
    b.extend(bytes(db + PORT_TABLE + 133 * PORT_SIZE - len(b)))
    # Replace the disabled mouse-motion reader in the port walking loop.
    # Its six far calls no longer exist, so the DOS loader must not relocate
    # their former segment words inside the new instructions.
    start, end = 0x20736, 0x2079A
    walk = Path(__file__).with_name("town_walk.bin").read_bytes()
    change(b, start, source[start:end], walk)
    count = struct.unpack_from("<H", b, 6)[0]
    entries = [b[0x1E + i * 4 : 0x22 + i * 4] for i in range(count)]
    kept = []
    for entry in entries:
        off, segment = struct.unpack("<HH", entry)
        if not start <= HEADER + segment * 16 + off < end:
            kept.append(entry)
    assert count - len(kept) == 6
    b[0x1E : 0x1E + 4 * count] = b"".join(kept) + bytes(24)
    struct.pack_into("<H", b, 6, len(kept))
    b[db + 0xC700 : db + 0xC709] = b"WALK.KEY\0"
    # Near call to the timer at offset 0x47 in town_walk.asm.
    change(
        b,
        0x207E5,
        bytes.fromhex("a0300c24013c011bc024fc050800"),
        bytes.fromhex("a0300c83e00140c1e002")
        + b"\xe8"
        + struct.pack("<h", start + 0x47 - 0x207F2)
        + b"\x90",
    )
    for i, (name, x, y) in enumerate(PORTS, 130):
        off = db + PORT_TABLE + i * PORT_SIZE
        b[off : off + 20] = struct.pack("<HH15sB", x, y, name.encode("cp949"), 0x16)

    # Mirror the original 130 records at native load/save boundaries. Store
    # only the three new discovery flags, in unused name padding of the first
    # three ports (well past their Korean names' terminating NUL).
    def synchronize(load):
        src, dst = (
            (ORIGINAL_TABLE, PORT_TABLE) if load else (PORT_TABLE, ORIGINAL_TABLE)
        )
        code = bytearray.fromhex("9c 50 51 56 57 06 1e 07 fc be")
        code += word(src) + b"\xbf" + word(dst) + bytes.fromhex("b9 14 05 f3 a5")
        for i in range(3):
            padding = ORIGINAL_TABLE + i * 20 + 18
            flags = PORT_TABLE + (130 + i) * 20 + 19
            code += b"\xa0" + word(padding if load else flags) + bytes.fromhex("24 50")
            if load:
                code += bytes.fromhex("0c 16")
            code += b"\xa2" + word(flags if load else padding)
        return code + bytes.fromhex("07 5f 5e 59 58 9d")

    # Additional native entry points run in the existing data segment.
    runtime = Path(__file__).with_name("regular_ports.bin").read_bytes()
    b.extend(bytes(db + 0xD400 - len(b)) + runtime)
    b[db + 0xD300 : db + 0xD300 + 111] = profiles

    def hook(site, slot, original, jump=False):
        old = bytes.fromhex(original)
        far = bytes([0xEA if jump else 0x9A]) + word(0xD400 + slot * 3) + word(DS)
        change(b, site, old, far.ljust(len(old), b"\x90"))
        count = struct.unpack_from("<H", b, 6)[0]
        rel = site + 3 - HEADER
        assert 0x1E + 4 * (count + 1) <= HEADER
        struct.pack_into("<HH", b, 0x1E + 4 * count, rel % 16, rel // 16)
        struct.pack_into("<H", b, 6, count + 1)

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

    # Each stub replays the displaced instructions before returning.
    # The load hook replaces a TEST, so its condition flags must reach the caller.
    for site, addr, load, original in (
        (0x1BEDB, 0xC710, True, "8d1e2c0990"),
        (0x1B944, 0xC760, True, "f606300c42"),
        (0x1BB53, 0xC7B0, False, "b86c8b2d300c"),
    ):
        original = bytes.fromhex(original)
        routine = synchronize(load)
        target = 0xD400 + 3 * {0xC710: 7, 0xC760: 8, 0xC7B0: 9}[addr]
        routine += b"\xe8" + struct.pack("<h", target - (addr + len(routine) + 3))
        routine += original + b"\xcb"
        assert len(routine) <= 0x50
        b[db + addr : db + addr + len(routine)] = routine
        change(
            b,
            site,
            original,
            b"\x9a" + word(addr) + word(DS) + b"\x90" * (len(original) - 5),
        )
        count = struct.unpack_from("<H", b, 6)[0]
        relocation = site + 3 - HEADER
        struct.pack_into("<HH", b, 0x1E + count * 4, relocation % 16, relocation // 16)
        struct.pack_into("<H", b, 6, count + 1)
    struct.pack_into("<HH", b, 2, len(b) % 512, (len(b) + 511) // 512)
    growth = (len(b) + 15) // 16 - (len(source) + 15) // 16
    minimum = struct.unpack_from("<H", source, 10)[0]
    struct.pack_into("<H", b, 10, minimum - growth)
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
            for i in range(120):
                pos = ORIGINAL_TABLE - 0xC30 + 20 * i
                if i != 53:
                    assert 0 in start[pos + 4 : pos + 18] and start[pos + 18] == 0
            pos = 0x697C - 0xC30
            profiles = b"".join(
                start[pos + i * 37 : pos + (i + 1) * 37] for i in (94, 95, 97)
            )
            maps, coords = town_assets(
                base.read("PORTMAP.LZW"), base.read("ZA_DAT.DAT")
            )
            for member in base.infolist():
                data = base.read(member)
                if member.filename in PATCHES:
                    expected, patch = PATCHES[member.filename]
                    if hashlib.sha256(data).hexdigest() != expected:
                        raise ValueError(
                            f"Unexpected input version of {member.filename}"
                        )
                    if member.filename == "MAIN.EXE":
                        data = patch(data, profiles)
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
