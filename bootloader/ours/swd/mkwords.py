#!/usr/bin/env python3
"""Turn a flat binary into the Tcl word list that write-words.tcl programs.

    python3 mkwords.py ../nrf5340-appcore-boot-rev2-ours.bin > loader-words.tcl
    python3 mkwords.py ../pendant-1.1.0-ourkey-signed.img    > app-words.tcl
"""
import struct
import sys

data = open(sys.argv[1], "rb").read()
data += b"\xff" * (-len(data) % 4)
print("set W {" + " ".join(hex(word) for (word,) in struct.iter_unpack("<I", data)) + "}")
