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


def executable(source):
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

    # Each stub replays the displaced instructions before returning.
    # The load hook replaces a TEST, so its condition flags must reach the caller.
    for site, addr, load, original in (
        (0x1BEDB, 0xC710, True, "8d1e2c0990"),
        (0x1B944, 0xC760, True, "f606300c42"),
        (0x1BB53, 0xC7B0, False, "b86c8b2d300c"),
    ):
        original = bytes.fromhex(original)
        routine = synchronize(load) + original + b"\xcb"
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
        (x, y, 0x12) for _, x, y in PORTS
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


def build(src, dest):
    if src.resolve() == dest.resolve():
        raise ValueError("Use a separate output file")
    with NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
        pass
    try:
        with ZipFile(src) as base, ZipFile(tmp.name, "w", ZIP_DEFLATED) as out:
            if not PATCHES.keys() <= set(base.namelist()):
                raise ValueError("Required DOS files missing")
            for member in base.infolist():
                data = base.read(member)
                if member.filename in PATCHES:
                    expected, patch = PATCHES[member.filename]
                    if hashlib.sha256(data).hexdigest() != expected:
                        raise ValueError(
                            f"Unexpected input version of {member.filename}"
                        )
                    data = patch(data)
                out.writestr(member, data)
        Path(tmp.name).chmod(0o644)
        Path(tmp.name).replace(dest)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


PATCHES = {
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
