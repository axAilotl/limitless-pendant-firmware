#!/usr/bin/env python3
"""Audit a Pendant MCUboot serial-recovery console without writing flash.

Framing comes from the archive's net/upload-net.py (hardware-proven), so this
script never invents bytes on the wire. Three phases, all non-destructive:

  1. read sweep      read op over a grid of SMP groups/ids
  2. write sweep     write op with an empty map (handled ids skipped)
  3. upload sizing   partial upload of junk to image 3 (RAM staging, lost on
                     reset); the declared size is never reached, so the
                     post-upload hook (and with it the PCD copy) never runs

Never sent: group 0 / id 5 (os reset fires on any op), group 1 / id 0 writes
(confirm/test -> trailer writes), and a completed upload.

Usage: python3 recovery_console_audit.py --port /dev/ttyACM0 \
           [--upload-net ../net/upload-net.py] \
           [--skip-upload]
"""
import argparse
import importlib.util
import os
import select
import sys
import time

RESET = (0, 5)          # fires on read or write
STATE_WRITE = (1, 0)   # test/confirm -> slot trailer writes
UPLOAD = (1, 1)
GROUPS = list(range(0, 9)) + [63, 64, 60000]
IDS = list(range(0, 16))
STAGING = 3            # image 3 -> RAM staging area, not flash
DECLARED = 0x29D04     # stock net update size; we send well under a quarter
SIZES = [40, 44, 48, 49, 50, 52, 56, 64, 80, 96, 120, 160, 192, 240, 256]


def load(path):
    spec = importlib.util.spec_from_file_location("upload_net", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def junk(n, seed=0):
    return bytes(((i * 7919 + seed * 104729) >> 3) & 0xFF for i in range(n))


def guard(group, ident, op):
    assert (group, ident) != RESET, "refusing to send os reset"
    assert not (op == 2 and (group, ident) in (STATE_WRITE, UPLOAD)), "refusing state write/upload"


def ask(sp, u, seq, op, group, ident, obj=None, timeout=1.5):
    guard(group, ident, op)
    return u.transact(sp, seq & 0xFF, op, group, ident, obj, timeout=timeout)


def chunk(sp, u, seq, data, off, timeout):
    assert off + len(data) < DECLARED, "refusing to complete the upload"
    return u.transact(sp, seq & 0xFF, 2, *UPLOAD,
                      {"image": STAGING, "data": data, "len": DECLARED, "off": off}, timeout=timeout)


def fast_chunk(sp, u, seq, data, off, timeout):
    """Same request as chunk(), reading the port directly and returning as soon
    as one whole frame arrives (before 2026-11-23, upload-net.transact waited
    out the port's 0.2 s read timeout on every reply)."""
    assert off + len(data) < DECLARED, "refusing to complete the upload"
    sp.reset_input_buffer()
    sp.write(u.build(2, 1, 1, u.cbor({"image": STAGING, "data": data, "len": DECLARED, "off": off}), seq & 0xFF))
    sp.flush()
    end, buf = time.monotonic() + timeout, b""
    while time.monotonic() < end:
        if not select.select([sp.fileno()], [], [], 0.05)[0]:
            continue
        buf += sp.read(sp.in_waiting)
        msg = u.frames(buf)
        if msg:
            parsed = u.parse(msg)
            if parsed is not None:
                return parsed
    return None


def sweeps(sp, u):
    rows, seq = [], 0
    for op in (0, 2):
        for g in GROUPS:
            for i in IDS:
                if (g, i) == RESET or (op == 2 and (g, i) in (STATE_WRITE, UPLOAD)):
                    continue
                obj = {"echo": "audit"} if (op, g, i) == (2, 0, 1) else {}
                seq += 1
                r = ask(sp, u, seq, op, g, i, obj)
                rows.append((op, g, i, r))
    for op, g, i, r in rows:
        if r is None or r.get("rc", 0) != 8:
            brief = {k: (v.hex()[:16] if isinstance(v, bytes) else v) for k, v in r.items()} if r else None
            print(f"  op={'read ' if op == 0 else 'write'} grp={g:<5} id={i:<2} -> {brief}")
    answered = sum(r is not None for _, _, _, r in rows)
    print(f"  {len(rows)} requests, {answered} answered, "
          f"{sum(r is not None and r.get('rc', 0) == 8 for _, _, _, r in rows)} x rc 8 (ENOTSUP)")
    return rows


def sustained(sp, u, send, expected, chunks=256):
    """48-byte chunks from the acknowledged offset; never completes the upload."""
    off, t0, failed, sent = expected, time.time(), 0, 0
    while sent < chunks and failed < 8:
        r = send(sp, u, off, junk(48, off), off, timeout=3.0)
        if r is None or r.get("rc", 0) != 0:
            failed += 1
            continue
        off, failed = r["off"], 0
        sent += 1
    dt = time.time() - t0
    staged = off - expected
    print(f"  sustained ({send.__name__}): {sent} x 48 B chunks, {staged} B staged in {dt:.1f}s "
          f"({staged / dt:.0f} B/s, {1000 * dt / max(sent, 1):.0f} ms/chunk), {failed} failed; "
          f"left incomplete at {100.0 * off / DECLARED:.1f}%")
    return off


def upload_probe(sp, u, fast_only=False):
    expected = 0
    if not fast_only:
        def reply(r):
            if r is None:
                return "NO RESPONSE"
            return "off %s" % r.get("off") if r.get("rc", 0) == 0 else "rc %s" % r["rc"]

        def chars(n, off):
            return len(u.build(2, 1, 1, u.cbor({"image": STAGING, "data": junk(n), "len": DECLARED, "off": off}))) - 3

        print("  frame ceiling at off=0 (1-byte offset encoding):")
        for n in SIZES:
            r = chunk(sp, u, 0, junk(n), 0, timeout=1.5)
            print(f"    data={n:<4} b64={chars(n, 0):<4} -> {reply(r)}")
        print("  write unit (data at off=0 -> acknowledged offset):")
        for n in (44, 45, 46, 47, 48, 49, 50):
            r = chunk(sp, u, 0, junk(n), 0, timeout=1.5)
            print(f"    {n} B -> {reply(r)}")
            expected = (r or {}).get("off", expected)
        print("  frame ceiling at a 3-byte offset encoding (out of order: acknowledged, not written):")
        for n in (44, 48, 49):
            r = chunk(sp, u, 0, junk(n), expected + 0x100, timeout=1.5)
            print(f"    data={n} b64={chars(n, expected + 0x100)} -> {reply(r)}")
    print("  sustained transfers (RAM staging, never completed):")
    expected = sustained(sp, u, chunk, expected)
    sustained(sp, u, fast_chunk, expected)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--upload-net", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "net", "upload-net.py"))
    ap.add_argument("--skip-upload", action="store_true")
    ap.add_argument("--skip-sweep", action="store_true")
    ap.add_argument("--fast-only", action="store_true", help="skip sizing; run only the two sustained transfers")
    a = ap.parse_args()
    u = load(a.upload_net)
    with u.open_port(a.port) as sp:
        print("bootloader:", ask(sp, u, 0, 0, 1, 0, {"image": 0}, timeout=3.0))
        if not a.skip_sweep:
            print("sweep (lines shown = everything that is not rc 8):")
            sweeps(sp, u)
        if not a.skip_upload:
            print(f"upload probe, image {STAGING} (RAM staging), never completed:")
            upload_probe(sp, u, a.fast_only)


if __name__ == "__main__":
    sys.exit(main())
