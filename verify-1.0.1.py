#!/usr/bin/env python3
"""Verify the signed TLV block of the partial 1.0.1 image.

MCUboot signs the image digest, and the digest is stored in the 0x10 TLV, so
the ECDSA signature can be checked without the payload. The trust root is the
retail SPKI already published in bootloader/nrf5340-appcore-boot-0x0-0x14000.bin
at offset 0x1125F.

Usage:
    python verify-1.0.1.py [--image PATH] [--bootloader PATH]
"""
import argparse
import hashlib
import struct
import sys

DEFAULT_IMAGE = "usb-shell-dumps/pendant-1.0.1-partial-0x94000-0xF23D7.bin"
DEFAULT_BOOT = "bootloader/nrf5340-appcore-boot-0x0-0x14000.bin"

IMAGE_BASE = 0x94000          # flash address of the first byte in the file
TLV_ADDR = 0xF233C            # absolute address of the TLV info header
SPKI_OFF = 0x1125F            # inside the bootloader dump
SPKI_LEN = 91


def parse_tlvs(buf, off):
    magic, total = struct.unpack_from("<HH", buf, off)
    if magic != 0x6907:
        raise SystemExit(f"no TLV info magic at {off:#x} (got {magic:#06x})")
    out = {}
    p = off + 4
    end = off + 4 + total
    while p + 4 <= end:
        t, l = struct.unpack_from("<HH", buf, p)
        if t == 0 or l == 0:
            break
        out[t] = buf[p + 4:p + 4 + l]
        p += 4 + l + ((4 - l % 4) % 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--bootloader", default=DEFAULT_BOOT)
    a = ap.parse_args()

    img = open(a.image, "rb").read()
    boot = open(a.bootloader, "rb").read()

    tlvs = parse_tlvs(img, TLV_ADDR - IMAGE_BASE)
    digest = tlvs.get(0x10)
    keyhash = tlvs.get(0x01)
    sig = tlvs.get(0x22)
    if not (digest and keyhash and sig):
        raise SystemExit("missing one of the required TLVs")

    spki = boot[SPKI_OFF:SPKI_OFF + SPKI_LEN]
    spki_hash = hashlib.sha256(spki).hexdigest()

    print("image digest :", digest.hex())
    print("keyhash TLV  :", keyhash.hex())
    print("SPKI sha256  :", spki_hash)
    print("keyhash match:", spki_hash == keyhash.hex())

    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        from cryptography.hazmat.primitives.serialization import load_der_public_key
    except ImportError:
        print("\ncryptography not installed; pip install cryptography to check the signature")
        return 1 if spki_hash != keyhash.hex() else 0

    pub = load_der_public_key(spki)
    pub.verify(sig, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    print("\nECDSA verify over embedded digest: VALID")
    return 0 if spki_hash == keyhash.hex() else 1


if __name__ == "__main__":
    sys.exit(main())
