#!/usr/bin/env python3
"""Verify the network-core images in this directory.

For each `net-app-*.bin`:

  - `fw_info` magic and size
  - `sha256(app[0:size])` equals the hash in the validation info
  - the ECDSA P-256 signature verifies against the embedded public key
  - `sha256(public_key)` equals the key hash in the matching provision file

The signature is over `sha256(digest)`, not the digest: Nordic's
`bl_ecdsa_verify` hashes its input. That is the only non-obvious part.

Usage:
    python verify-net.py [--dir .]
"""
import argparse
import glob
import hashlib
import os
import struct
import sys

FW_INFO_OFF = 0x200
SIZE_OFF = 0x210          # fw_info.size
VERSION_OFF = 0x214


def parse(app):
    size = struct.unpack_from("<I", app, SIZE_OFF)[0]
    fw_magic = struct.unpack_from("<III", app, FW_INFO_OFF)
    val_magic = struct.unpack_from("<III", app, size)
    addr = struct.unpack_from("<I", app, size + 12)[0]
    digest = app[size + 16:size + 48]
    pub = app[size + 48:size + 112]
    sig = app[size + 112:size + 176]
    return {
        "size": size,
        "version": struct.unpack_from("<I", app, VERSION_OFF)[0],
        "fw_magic": fw_magic,
        "val_magic": val_magic,
        "addr": addr,
        "digest": digest,
        "pub": pub,
        "sig": sig,
        "key_hash": hashlib.sha256(pub).digest(),
        "hash_ok": hashlib.sha256(app[:size]).digest() == digest,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()

    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        sys.exit("cryptography not installed; pip install cryptography")

    bad = 0
    for path in sorted(glob.glob(os.path.join(a.dir, "net-app-*.bin"))):
        name = os.path.basename(path)
        app = open(path, "rb").read()
        v = parse(app)

        pub = ec.EllipticCurvePublicNumbers(
            int.from_bytes(v["pub"][:32], "big"),
            int.from_bytes(v["pub"][32:], "big"),
            ec.SECP256R1()).public_key()
        der = utils.encode_dss_signature(int.from_bytes(v["sig"][:32], "big"),
                                        int.from_bytes(v["sig"][32:], "big"))
        try:
            pub.verify(der, hashlib.sha256(v["digest"]).digest(),
                       ec.ECDSA(utils.Prehashed(hashes.SHA256())))
            sig_ok = True
        except InvalidSignature:
            sig_ok = False

        chan = "dev" if name.endswith("-dev.bin") else "release"
        ver = name[len("net-app-"):-len("-%s.bin" % chan)]
        prov_path = os.path.join(a.dir, f"net-provision-{ver}-{chan}.bin")
        prov_ok = None
        if os.path.exists(prov_path):
            prov = open(prov_path, "rb").read()
            prov_ok = prov[16:32] == v["key_hash"][:16]

        ok = (v["hash_ok"] and sig_ok and v["fw_magic"][0] == 0x281EE6DE
              and v["val_magic"][0] == 0x281EE6DE and v["val_magic"][1] == 0x86518483
              and v["addr"] == 0x01008800 and prov_ok is not False)
        bad += 0 if ok else 1
        print(f"{name:30s} size {v['size']:#07x} ver {v['version']} "
              f"hash {'ok' if v['hash_ok'] else 'BAD'} "
              f"sig {'ok' if sig_ok else 'BAD'} "
              f"provision {'ok' if prov_ok else ('BAD' if prov_ok is False else 'n/a')}")
        print(f"   digest   {v['digest'].hex()}")
        print(f"   key hash {v['key_hash'].hex()[:32]}")

    print("\nall verified" if bad == 0 else f"\n{bad} file(s) failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
