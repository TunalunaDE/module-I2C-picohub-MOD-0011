# SPDX-License-Identifier: MIT
# Copyright (c) 2026 noknok
"""MOD-0011 - module I2C traffic on bus B while its 3.3 V rail is loaded (DEV-146). Runs on the brain.

Bus B = GP21 (SCL) / GP20 (SDA) = Qwiic J5/J6. Finds one noknok module: either waiting at the
enumeration address 0x7F (it is given TEST_ADDR) or already assigned (answers 0xB1 GET_VERSION).
Then reads 0xB1 every 0.5 s for SECS seconds and prints one line per read (L ok / E error), plus a
summary. Run it while an electronic load draws from the bus B rail (bench: DL24P on a Qwiic cable in
J5, pin 1 GND / pin 2 3.3 V, data wires open; module in J6).
Driver: SECS = 400; exec(open("/busb_traffic_log.py").read())
"""
import time
import board
import busio

TEST_ADDR = 0x40
try:
    SECS
except NameError:
    SECS = 400

i2c = busio.I2C(board.GP21, board.GP20, frequency=100000)
while not i2c.try_lock():
    pass


def crc8(data):
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def version(a):
    i2c.writeto(a, bytes([0xB1]))
    b = bytearray(4)
    i2c.readfrom_into(a, b)
    return tuple(b)


addr = None
t0 = time.monotonic()
while addr is None and time.monotonic() - t0 < 5:     # enumeration address first (Conductor style)
    try:
        b = bytearray(10)
        i2c.readfrom_into(0x7F, b)
        if crc8(b[:9]) == b[9]:
            i2c.writeto(0x7F, bytes([0x1D, TEST_ADDR]))
            time.sleep(0.05)
            addr = TEST_ADDR
            print("enumerated type 0x%02x, assigned 0x%02x" % (b[8], addr))
    except OSError:
        time.sleep(0.02)
if addr is None:
    for a in i2c.scan():
        if a in (0x7E, 0x7F):
            continue
        try:
            v = version(a)
            if v[0] == 1:
                addr = a
                print("already assigned at 0x%02x" % a)
                break
        except OSError:
            pass
if addr is None:
    print("no module found on bus B; scan:", [hex(a) for a in i2c.scan()])
    raise SystemExit
print("module at 0x%02x, version %s" % (addr, version(addr)))
ok = err = 0
t0 = time.monotonic()
while time.monotonic() - t0 < SECS:
    try:
        v = version(addr)
        ok += 1
        print("L %5.1f %s" % (time.monotonic() - t0, v))
    except OSError as e:
        err += 1
        print("E %5.1f %s" % (time.monotonic() - t0, e))
    time.sleep(0.5)
print("end: %d reads ok, %d errors" % (ok, err))
