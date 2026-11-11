#!/usr/bin/env python3
"""Upload a network-core image over MCUboot serial recovery (`image 3`).

This is the same path the vendor uses for network-core updates and the one the
stock bootloader hands straight to PCD with no signature check. See
`../bootloader/NET-CORE-UPDATE.md`.

The device must be in serial recovery (side button through a qualifying reset;
USB `2FE3:0100`).

Usage:
    python upload-net.py --port COM6 --file net-app-1.1.5-release.bin
    python upload-net.py --port COM6 --file net-app-1.1.5-release.bin --reset
    python upload-net.py --port COM6 --state
    python upload-net.py --port COM6 --wrap net-app-1.1.5-release.bin -o out.bin

Notes:
    * The stock bootloader's SMP receive buffer is 128 bytes, so base64 frames
      longer than ~127 characters are dropped without an error. 40-byte chunks
      work. At that size an upload takes about 15 minutes.
    * `os reset` returns EBUSY (10) while the PCD copy is running and 0 after
      the net core reports DONE, so it doubles as a completion check.
"""
import argparse
import base64
import struct
import sys
import time

import serial

IMAGE_MAGIC = 0x96F3B83D
HDR_SIZE = 0x200
NET_APP_SIZE = 0x29B04
B0N_ADDRESS = 0x01000000
CHUNK = 40


def crc16(crc, data):
    for b in data:
        crc = (((crc & 0xFF) << 8) | ((crc >> 8) & 0xFF)) ^ b
        crc = ((crc & 0xFF) >> 4) ^ crc
        crc = crc ^ ((crc & 0xF) << 12)
        crc = ((crc & 0xFF) << 5) ^ crc
        crc &= 0xFFFF
    return crc


def build(op, group, cmd, payload, seq=0):
    smp = struct.pack(">BBHHBB", op, 0, len(payload), group, seq, cmd) + payload
    body = smp + struct.pack(">H", crc16(0, smp))
    return b"\x06\x09" + base64.b64encode(struct.pack(">H", len(body)) + body) + b"\x0a"


def cbor(obj):
    if isinstance(obj, int):
        if obj < 24:
            return bytes([obj])
        if obj < 0x100:
            return b"\x18" + bytes([obj])
        if obj < 0x10000:
            return b"\x19" + struct.pack(">H", obj)
        if obj < 0x100000000:
            return b"\x1a" + struct.pack(">I", obj)
        return b"\x1b" + struct.pack(">Q", obj)
    if isinstance(obj, bytes):
        n = len(obj)
        if n < 24:
            return bytes([0x40 | n]) + obj
        if n < 0x100:
            return b"\x58" + bytes([n]) + obj
        return b"\x59" + struct.pack(">H", n) + obj
    if isinstance(obj, str):
        b = obj.encode()
        if len(b) < 24:
            return bytes([0x60 | len(b)]) + b
        return b"\x78" + bytes([len(b)]) + b
    if isinstance(obj, dict):
        out = bytes([0xA0 | len(obj)])
        for k, v in obj.items():
            out += cbor(k) + cbor(v)
        return out
    raise TypeError(type(obj))


class Reader:
    def __init__(self, b):
        self.b, self.i = b, 0

    def u(self, n):
        v = int.from_bytes(self.b[self.i:self.i + n], "big")
        self.i += n
        return v

    def item(self):
        ib = self.b[self.i]
        self.i += 1
        mt, ai = ib >> 5, ib & 31
        ln = {24: 1, 25: 2, 26: 4, 27: 8}.get(ai)
        n = ai if ai < 24 else (self.u(ln) if ln else None)
        if mt == 0:
            return n
        if mt == 1:
            return -1 - n
        if mt == 2:
            v = self.b[self.i:self.i + n]
            self.i += n
            return v
        if mt == 3:
            v = self.b[self.i:self.i + n].decode("utf8", "replace")
            self.i += n
            return v
        if mt == 4:
            out = []
            if ai == 31:
                while self.i < len(self.b) and self.b[self.i] != 0xFF:
                    out.append(self.item())
                self.i += 1
                return out
            return [self.item() for _ in range(n)]
        if mt == 5:
            out = {}
            if ai == 31:
                while self.i < len(self.b) and self.b[self.i] != 0xFF:
                    k = self.item()
                    out[k] = self.item()
                self.i += 1
                return out
            for _ in range(n):
                k = self.item()
                out[k] = self.item()
            return out
        if mt == 6:
            return self.item()
        return ib


def frames(buf):
    out = []
    i = 0
    while i + 2 < len(buf):
        if buf[i:i + 2] in (b"\x06\x09", b"\x04\x14"):
            j = buf.find(b"\x0a", i + 2)
            if j < 0:
                break
            try:
                out.append(base64.b64decode(buf[i + 2:j]))
            except Exception:
                pass
            i = j + 1
        else:
            i += 1
    return b"".join(out)


def parse(msg):
    if len(msg) < 10:
        return None
    n = struct.unpack_from(">H", msg, 0)[0]
    body = msg[2:]
    if len(body) < n or crc16(0, body) != 0:
        return None
    smp = body[:-2]
    op, fl, ln, grp, sq, cid = struct.unpack_from(">BBHHBB", smp, 0)
    payload = smp[8:8 + ln]
    obj = Reader(payload).item() if payload else {}
    if isinstance(obj, dict):
        obj.update(_group=grp, _id=cid)
    return obj


def transact(sp, seq, op, group, cmd, obj, timeout=3.0):
    sp.reset_input_buffer()
    sp.write(build(op, group, cmd, cbor(obj) if obj is not None else b"\xa0", seq))
    sp.flush()
    end = time.time() + timeout
    buf = b""
    while time.time() < end:
        buf += sp.read(4096)
        msg = frames(buf)
        if msg:
            r = parse(msg)
            if r is not None:
                return r
    return None


def wrap(raw):
    """Wrap a 0x29b04 net app in the MCUboot container the hook expects."""
    if len(raw) != NET_APP_SIZE:
        sys.exit(f"expected {NET_APP_SIZE:#x} bytes, got {len(raw):#x}")
    hdr = struct.pack("<IIHHIIBBHII", IMAGE_MAGIC, 0, HDR_SIZE, 0,
                      len(raw), 0, 1, 1, 5, 0, 0)
    hdr += b"\x00" * (HDR_SIZE - len(hdr))
    return hdr + raw


def open_port(port):
    sp = serial.Serial(port, 115200, timeout=0.2)
    sp.dtr = True
    sp.rts = False
    time.sleep(0.3)
    return sp


def do_state(port):
    with open_port(port) as sp:
        print(transact(sp, 0, 0, 1, 0, {"image": 0}))


def do_reset(port, tries=12):
    with open_port(port) as sp:
        for i in range(tries):
            r = transact(sp, i & 0xFF, 2, 0, 5, None, timeout=2.0)
            print(f"reset {i}: {r}")
            if r and r.get("rc") == 0:
                return True
            time.sleep(1.0)
    return False


def do_upload(port, path, image=3):
    data = open(path, "rb").read()
    if struct.unpack_from("<I", data, 0)[0] != IMAGE_MAGIC:
        data = wrap(data)
    total = len(data)
    hdr_size = struct.unpack_from("<H", data, 8)[0]
    reset = struct.unpack_from("<I", data, hdr_size + 4)[0]
    print(f"{path}: {total} B, image {image}, hdr {hdr_size:#x}, reset {reset:#010x}")
    if reset <= B0N_ADDRESS:
        sys.exit("the hook would reject this image (reset vector)")

    with open_port(port) as sp:
        print("bootloader:", transact(sp, 0, 0, 1, 0, {"image": 0}))
        off, seq, retries, t0 = 0, 1, 0, time.time()
        while off < total:
            piece = data[off:off + CHUNK]
            last = off + len(piece) >= total
            r = transact(sp, seq & 0xFF, 2, 1, 1,
                         {"image": image, "data": piece, "len": total, "off": off},
                         timeout=20.0 if last else 3.0)
            if r is None or (r.get("rc", 0) == 0 and r.get("off") == off):
                retries += 1
                if retries > 8:
                    sys.exit(f"stuck at {off:#x}")
                time.sleep(0.2)
                continue
            if r.get("rc", 0) != 0:
                sys.exit(f"upload failed at {off:#x}: {r}")
            off = r["off"]
            retries = 0
            seq += 1
            if seq % 64 == 0 or off >= total:
                print(f"  {off:#08x}/{total:#08x} {100.0*off/total:5.1f}% "
                      f"{time.time()-t0:6.1f}s", flush=True)
    print(f"done in {time.time()-t0:.0f}s; the PCD copy has been issued")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM6")
    ap.add_argument("--file")
    ap.add_argument("--image", type=int, default=3)
    ap.add_argument("--state", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--wrap", metavar="RAW")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()

    if a.wrap:
        out = a.out or (a.wrap + "-update.bin")
        open(out, "wb").write(wrap(open(a.wrap, "rb").read()))
        print("wrote", out)
    elif a.state:
        do_state(a.port)
    elif a.reset:
        sys.exit(0 if do_reset(a.port) else 1)
    elif a.file:
        do_upload(a.port, a.file, a.image)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
