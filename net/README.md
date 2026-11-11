# Network-core artifacts

The nRF5340 network core had no artifact in this archive until now. It is not
served as a standalone file: the vendor's firmware endpoint only advertises
`app_update.bin` in the manifest. But the same endpoint will sign a URL for the
sysbuild multi-domain output, which contains both cores.

Ask `generateFirmwareSignedUrlV2` for:

```
artifacts/pendant/signed-release/1.1.5_0e21a76/merged_domains.hex
```

and the Intel HEX you get back covers:

```
0x00000000..0x00011eb4   app-core bootloader
0x00014000..0x00093d43   app slot
0x01000000..0x010055e0   network-core B0N          (0x55e0)
0x010085a8..0x010087b0   network-core provision    (0x208)
0x01008800..0x01032304   network-core app          (0x29b04)
```

The files here are the three net-core regions, extracted from those builds for
1.0.1, 1.1.5 and 1.1.20, release and development.

## Inventory

| File | Bytes | SHA-256 |
|---|---|---|
| `net-b0n-3686abd4.bin` | 21,984 | `3686abd422571682d6236e2097dcf1529281517e9d1981dc439c720d6e2872ac` |
| `net-app-1.0.1-release.bin` | 170,756 | `0535bff523d7d59ae34c5488b5aff08d100c4a682c5c1ff2db83b741ac4db70f` |
| `net-app-1.0.1-dev.bin` | 170,756 | `704001209c97388ec1670059f072a0e3859b480ab2e9c3e8a76b845984c87bf2` |
| `net-app-1.1.5-release.bin` | 170,756 | `32be0018b6767d1ba7fbd7a6038d172b3a78fc5719cd941d6082b95760899863` |
| `net-app-1.1.5-dev.bin` | 170,756 | `1214e15c99ff427a9d95a72bd6339e77c530b5975a711671b28de8b291b82fd1` |
| `net-app-1.1.20-release.bin` | 170,756 | `f2b3b380e31c32df7846b154c6b2c79a6dddca717b71eab8ce9e3b8ca4a0ab44` |
| `net-app-1.1.20-dev.bin` | 170,756 | `cc51c62a20c5b7b1fbdb537f1aa3d0498e098ac00f01704c1df19e71c7313f79` |
| `net-provision-1.0.1-release.bin` | 520 | `b0e7b6715e8ed7a340dbf78fb27d55ffc0b69eedb615146c690b1d6d23891ce2` |
| `net-provision-1.0.1-dev.bin` | 520 | `861bdf59d7c13763fb243c87c2dfddaf7fd7874b6b72f61a4ac3b238abaa5160` |
| `net-provision-1.1.5-release.bin` | 520 | `096164c0e07d52526fa913c1c19cb6fbf462736ff0b128eb035435cedcb7ca79` |
| `net-provision-1.1.5-dev.bin` | 520 | `6dc5c9ce6ea08ac384626498931e06617c92d71585ff58069d098bf0eb9d6c3e` |
| `net-provision-1.1.20-release.bin` | 520 | `0d26ce13eddeec4ce2af5c57032f2e4fb4bf5dad486e4289e9e6be137c8e665c` |
| `net-provision-1.1.20-dev.bin` | 520 | `9d0f2c34e5265610a9fe8acbb956aab81f69dd8fc671a62d41ba436d0fa5294e` |

The B0N is **byte-identical in all six builds**. The net app payload is
byte-identical too: `sha256(app[0:0x29a54])` is
`0d00cb8ef4352fb8691f490c0bc3684a75b5fb1c5d61e1895184ded6178ee824` for every
version and channel. Only the signing key, the signature and the provision
differ per build — the firmware itself has not changed from 1.0.1 to 1.1.20.

## Sizes and layout

```
net-app + 0x000  vector table
net-app + 0x200  fw_info
                   +0x00  magic        0x281ee6de 0x8fcebb4c 0x00003502
                   +0x0c  total_size   0x3c
                   +0x10  size         0x29a54
                   +0x14  version      1
                   +0x18  address      0x01008800
                   +0x1c  boot_address 0x01008800
                   +0x20  valid        0x9102ffff
net-app + 0x29a54  validation info
                   +0x00  magic        0x281ee6de 0x8fcebb4c 0x00013502
                   +0x0c  address      0x01008800
                   +0x10  hash[32]      sha256(app[0:0x29a54])
                   +0x30  public_key[64] x||y, raw, big-endian
                   +0x70  signature[64]  r||s, raw, big-endian
```

The provision at `0x010085a8` is 520 bytes; bytes 16..32 are
`sha256(public_key)`. Each build carries its own key, and each
`net-provision-*.bin` matches the key in the corresponding net app.

The signature is ECDSA P-256 over `sha256(sha256(app[0:size]))` — Nordic's
`bl_ecdsa_verify` hashes its input, so the signed message is the digest of the
digest, not the digest. `verify-net.py` implements this.

## Verifying

```
python verify-net.py
```

It checks, for all six net apps: the payload hash, the signature against the
key, and that `sha256(key)` equals the provisioned key hash.

## Flashing

These are the exact images the vendor's own network-core update path writes to
`0x01008800`. See `../bootloader/NET-CORE-UPDATE.md` for the path and
`upload-net.py` for a client. The B0N and provision are normally never
rewritten; they are here for preservation, not for flashing.

## Note on the provision

A network-core image update erases the first target sector, `0x01008000`, which
contains the provision. The B0N does not read it (see
`../bootloader/NET-CORE-UPDATE.md`), so this is harmless, but it does mean the
provision file here is only useful for a device whose provision is intact.
