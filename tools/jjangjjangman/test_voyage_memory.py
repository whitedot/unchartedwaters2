"""Regression for the sailing freeze. Run with Python and pip install unicorn."""

import struct
import unittest
from pathlib import Path
from zipfile import ZipFile

from unicorn import Uc, UC_ARCH_X86, UC_MODE_16
from unicorn.x86_const import (
    UC_X86_REG_AX,
    UC_X86_REG_DX,
    UC_X86_REG_BX,
    UC_X86_REG_BP,
    UC_X86_REG_CS,
    UC_X86_REG_DS,
    UC_X86_REG_SS,
    UC_X86_REG_SP,
    UC_X86_REG_IP,
)
from korea_ports import HEADER, DS


class VoyageMemory(unittest.TestCase):
    def test_port_hooks_after_route_search(self):
        archive = Path(__file__).resolve().parents[2] / "game/mod_jjangjjangman.zip"
        with ZipFile(archive) as z:
            exe = bytearray(z.read("MAIN.EXE"))
        load = 0x1000
        # Load and relocate the shipped EXE exactly as DOS does.
        for i in range(struct.unpack_from("<H", exe, 6)[0]):
            off, seg = struct.unpack_from("<HH", exe, 30 + 4 * i)
            p = HEADER + 16 * seg + off
            struct.pack_into("<H", exe, p, load + struct.unpack_from("<H", exe, p)[0])
        native = load + struct.unpack_from("<H", exe, 0x16)[0]
        ds = native + DS
        cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        cpu.mem_map(0, 1 << 20)
        cpu.mem_write(load * 16, bytes(exe[HEADER:]))
        for reg in (UC_X86_REG_DS, UC_X86_REG_SS):
            cpu.reg_write(reg, ds)

        def native_hook(site, ax=0, dx=0):
            opcode, off, cs = struct.unpack(
                "<BHH", cpu.mem_read(native * 16 + site - HEADER, 5)
            )
            self.assertIn(opcode, (0x9A, 0xEA))
            cpu.reg_write(UC_X86_REG_CS, cs)
            cpu.reg_write(UC_X86_REG_AX, ax)
            cpu.reg_write(UC_X86_REG_DX, dx)
            cpu.reg_write(UC_X86_REG_SP, 0xFC80)
            cpu.mem_write(ds * 16 + 0xFC80, struct.pack("<HH", 0, 0x9000))
            cpu.emu_start(cs * 16 + off, 0x90000, count=5000)
            self.assertEqual(
                (cpu.reg_read(UC_X86_REG_CS), cpu.reg_read(UC_X86_REG_IP)), (0x9000, 0)
            )
            return cpu.reg_read(UC_X86_REG_AX)

        native_hook(0x1BEDB)  # new game
        econ = native_hook(0xAFA0, 130)
        port = native_hook(0xAF90, 130)
        for city, specialty in ((0, 47), (2, 46)):
            self.assertEqual(
                cpu.mem_read(ds * 16 + econ + city * 37 + 26, 1), bytes([specialty])
            )
        template = native_hook(0xAF70, 65)
        self.assertEqual(cpu.mem_read(ds * 16 + template, 6), "거북선".encode("cp949"))
        stats = native_hook(0xAF80, 25)
        self.assertEqual(cpu.mem_read(ds * 16 + stats + 1, 3), bytes([100] * 3))
        self.assertEqual(
            struct.unpack("<H", cpu.mem_read(ds * 16 + stats + 6, 2))[0], 3000
        )
        cpu.reg_write(UC_X86_REG_BX, 0x5210)
        for figure in (1, 9, 10, 11):
            cpu.mem_write(ds * 16 + 0x5210 + 29, bytes([figure]))
            self.assertEqual(native_hook(0x1E8BA), min(figure, 10))

        # Run the original battle initialization and range/power loop with
        # identical ships. Byte firepower at each distance must not wrap.
        def battle_profile(gun):
            frame, unit, ship = 0xB000, 0xB100, 0xB200
            cpu.mem_write(ds * 16 + unit + 2, struct.pack("<H", ship))
            cpu.mem_write(ds * 16 + ship + 8, bytes([0x10 | gun]))
            cpu.reg_write(UC_X86_REG_CS, native)
            cpu.reg_write(UC_X86_REG_BP, frame)
            cpu.reg_write(UC_X86_REG_AX, unit)
            for start, stop in ((0x14340, 0x14396), (0x14435, 0x1448E)):
                cpu.emu_start(
                    native * 16 + start - HEADER, native * 16 + stop - HEADER, count=300
                )
            return list(cpu.mem_read(ds * 16 + unit + 0x10, 6))

        self.assertEqual(battle_profile(0), [0, 0, 0, 0, 0, 0])
        self.assertEqual(battle_profile(7), [0, 200, 180, 160, 140, 5])
        self.assertEqual(battle_profile(8), [0, 250, 225, 200, 175, 5])
        values = bytes(range(111))
        cpu.mem_write(ds * 16 + econ, values)
        # The game may consume this entire native stack area for route queues.
        cpu.mem_write(ds * 16 + 0xC700, bytes([0xA5]) * (0xFC80 - 0xC700))
        for i, (x, y) in enumerate(((934, 378), (952, 386), (944, 374))):
            self.assertEqual(native_hook(0x277F2, x, y), 130 + i)
            self.assertEqual(native_hook(0xAF90, 130 + i), port + 20 * i)
            self.assertEqual(native_hook(0xAFA0, 130 + i), econ + 37 * i)
            cpu.mem_write(ds * 16 + port + 20 * i + 19, bytes([0x50 + i]))
        self.assertEqual(native_hook(0xAF90, 129), 0x5F54 + 129 * 20)
        self.assertEqual(native_hook(0xAFA0, 99), 0x697C + 99 * 37)
        self.assertEqual(native_hook(0x277F2, 2000, 3000), 0xFFFF)
        native_hook(0x1BB53)  # save; discard all transient records; load
        cpu.mem_write(ds * 16 + port, bytes(60))
        cpu.mem_write(ds * 16 + econ, bytes(111))
        native_hook(0x1B944)
        self.assertEqual(cpu.mem_read(ds * 16 + econ, 111), values)
        for i in range(3):
            self.assertEqual(
                cpu.mem_read(ds * 16 + port + 20 * i + 19, 1), bytes([0x50 + i])
            )


if __name__ == "__main__":
    unittest.main()
