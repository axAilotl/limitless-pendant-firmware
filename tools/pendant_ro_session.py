#!/usr/bin/env python3
"""Read-only Pendant USB shell session driver (2026-11-11).

Rules from knowledge/05-usb-shell (all baked in):
- `shell echo off` FIRST (RX-ring overflow crashes come from echo+pipelines)
- byte-paced writes (~3 ms/char), never pipeline >8 commands
- one process per tty, prompt-wait between commands
- READ-ONLY: no devmem writes, no erase/clear/erase_secondary, no uploads

Usage: pendant_ro_session.py <port> <cmdfile>   # one command per line
Logs raw transcript to stdout. Refuses commands on the denylist.
"""
import serial, sys, time, re

DENY = re.compile(r"(devmem\s+\S+\s+\d+\s+\S+|erase|clear|write|upload|reset|format|set_active|gen_keys|wifi|comm |settings\s+write|flash\s+page|boot_set)", re.I)
PROMPT = b"uart:~$ "

def paced_write(s, data):
    for b in data:
        s.write(bytes([b]))
        time.sleep(0.003)

def wait_prompt(s, timeout=6.0):
    buf = b""
    t0 = time.time()
    while time.time() - t0 < timeout:
        chunk = s.read(256)
        if chunk:
            buf += chunk
            if buf.rstrip().endswith(PROMPT.strip()) and time.time() - t0 > 0.3:
                break
        else:
            time.sleep(0.05)
    return buf.decode(errors="replace")

def main():
    port, cmdfile = sys.argv[1], sys.argv[2]
    cmds = [l.strip() for l in open(cmdfile) if l.strip() and not l.startswith("#")]
    for c in cmds:
        if DENY.search(c):
            print(f"### REFUSED (denylist): {c}")
            return 2
    s = serial.Serial(port, 115200, timeout=0.2)
    time.sleep(0.4)
    s.reset_input_buffer()
    paced_write(s, b"shell echo off\n")
    print("### echo-off:", wait_prompt(s).replace("\r", ""))
    for i in range(0, len(cmds), 8):
        batch = cmds[i:i+8]
        for c in batch:
            paced_write(s, c.encode() + b"\n")
            out = wait_prompt(s)
            print(f"### CMD: {c}\n{out}\n")
            time.sleep(0.2)
    s.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
