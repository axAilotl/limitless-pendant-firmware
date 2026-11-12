# Limitless Pendant firmware archive

Preserved stock firmware artifacts for the Limitless Pendant (Nordic nRF5340,
Zephyr 3.5.99, MCUboot). Purpose: **device rescue and preservation before the
vendor service disappears**. Every artifact here was obtained from retail
hardware we own, or from the vendor's own anonymous firmware-delivery endpoint —
no credentials, signed URLs, account data, device identifiers, or captured
audio are included, and no vendor private key material exists on these devices
(only public keys).

Discussion and provenance details: [limitless-libre issue #1](https://github.com/shade-familiar/limitless-libre/issues/1)
and the research gists linked at the bottom.

## Inventory

| Artifact | Bytes | SHA-256 | How obtained |
|---|---|---|---|
| `ota/limitless-pendant-1.1.9-production-release-b1da1573.img` | 512.2 KiB | `b1da1573b9c186cc1e8fbd4e1b6afea63778f8dbe0278cc506fe1fa32610677d` | vendor OTA endpoint, signed-release channel |
| `usb-shell-dumps/pendant-1.1.0-app-payload.bin` | 921,288 | `350787a28f7b66fc9100014fab7bb36b3879bdf5e24d0771606015fea3bd49c7` | payload split out of the slot dump above |
| `ota/limitless-pendant-1.1.20-dev-release-0fdd5897.img` | 512.3 KiB | `0fdd58978f395caa2f72b1a62647fa5c4071db7899d7940234b2697afb133b48` | vendor OTA endpoint, development channel (same payload as release; only KEYHASH TLV differs) |
| `usb-shell-dumps/pendant-1.1.0-slot0-internal.bin` | 966,656 | `fcd5ee7a8fd1c635c6b614ce3343aea888cfa636311834d786e6adb0dd633bde` | read from a retail unit's app slot over the stock USB shell (word reads at `0x14000+`, verified by sample re-reads) |
| `usb-shell-dumps/pendant-1.1.5-signed-app-0x14000-0x93D43.bin` | 523,587 | `94d38ea4f7cc8a273081ec6f5b76c87ab8b12bb11af08dd50c7c0016cd146eeb` | read-only `devmem` word reads over the stock USB shell by @smanaton; bounded signed image, ECDSA P-256 verified against the retail SPKI |
| `bootloader/nrf5340-appcore-boot-0x0-0x14000.bin` | 81,920 | `bd35f61d3be2e89d49d2c438603065d17854bb869c4f19262f3448c00e4c0e5a` | app-core internal flash `0x0-0x14000`, read from a retail unit |
| `usb-shell-dumps/pendant-1.0.1-partial-0x94000-0xF23D7.bin` | 386,007 | `4c1eb90b03123dcfe39ef61b44ef07ffb12726ed26ab554ebbc7401e3149ad5d` | read-only `devmem` over the stock USB shell (no writes, no recovery, no teardown). **Partial**: tail of the image plus intact signed TLV block. Not restorable — see `pendant-1.0.1-partial.manifest.json`. |
| `ota/limitless-pendant-1.0.1-production-release-a584e7cf.img` | 509,422 | `a584e7cfc1aeb985c1af3ac0275aecddea8e5000e409d01d046be60634173c66` | vendor OTA endpoint, production channel (`1.0.1_04bc288`) |
| `ota/limitless-pendant-1.0.1-dev-release-e42a2751.img` | 509,423 | `e42a27518a54324c52dc6f649e6fdf3c2411bedcfe2cf1761b088c514e4ad8f4` | vendor OTA endpoint, development channel (same payload; KEYHASH `60ae7f65…`) |
| `ota/limitless-pendant-1.1.0-production-release-44912b2e.img` | 522,827 | `44912b2ec5f6ac22474d796cd778ae8d8766be07213da639bba749608f532f09` | vendor OTA endpoint, production channel (`1.1.0_90a06ec`) |
| `ota/limitless-pendant-1.1.0-dev-release-a8da9f7a.img` | 522,827 | `a8da9f7ad2de098155f8bd0231c136584efe87bc01c95d27931418d21c3005e1` | vendor OTA endpoint, development channel (same payload; KEYHASH `60ae7f65…`) |
| `ota/limitless-pendant-1.1.5-production-release-94d38ea4.img` | 523,587 | `94d38ea4f7cc8a273081ec6f5b76c87ab8b12bb11af08dd50c7c0016cd146eeb` | vendor OTA endpoint, production channel (`1.1.5_0e21a76`); byte-identical to the USB-shell readback above |
| `ota/limitless-pendant-1.1.5-dev-release-0e6bd5b0.img` | 523,587 | `0e6bd5b0001194a92cc8ed6c9d5078f2d5961604679a1f9dcef6442a1aef712d` | vendor OTA endpoint, development channel (same payload; KEYHASH `60ae7f65…`) |
| `ota/limitless-pendant-1.1.9-dev-release-087cd34f.img` | 524,490 | `087cd34fbb7e8e6d756e9c426369c3dd7e078f6348bca07813c3ed3fef1ab4d7` | vendor OTA endpoint, development channel (`1.1.9_bd223cf`); pairs with the production image already listed |

`SHA256SUMS` at the root covers every file. The network-core artifacts
(B0N, provision, net app for 1.0.1 / 1.1.5 / 1.1.20) are in
[`net/`](net/README.md), which has its own inventory table.

## Why the 1.1.0 dump matters

The 1.1.0 slot dump is ~397 KB larger than the OTA images because it ships a
**complete nRF700x Wi-Fi stack** (driver, wpa_supplicant v2.11 with WPA3-SAE,
websocket upload path) that was compiled out from 1.1.9 onward. The Wi-Fi
hardware is present on every unit. On a stock 1.1.0 unit the USB shell exposes
`wifi_cred add/list`, `config set server_name/port/ingest_token`, and
`comm wifi_connect/server_connect` — an unauthenticated, configurable
audio-streaming endpoint over Wi-Fi, no exploit needed.

(Correction: the earlier "network-core child" files were app-image slices;
the Wi-Fi stack lives in the 1.1.0 app image itself.)

## Network core: resolved 2026-11-11

Two corrections and a result.

**1. The net core is in the vendor's own artifacts.** The earlier
`netcore-embedded-*.bin` files were not network-core firmware — they were
contiguous slices of the app images, and have been removed. But the firmware
endpoint also signs `merged_domains.hex`, the sysbuild multi-domain output,
which contains both cores. The B0N, provision and net app extracted from those
builds are in [`net/`](net/README.md). The B0N is byte-identical across 1.0.1,
1.1.5 and 1.1.20, and the net app payload is too, so the firmware has not
changed since 1.0.1. There is still no net OTA artifact in any manifest; the
vendor has never shipped a net-core update, but it did once ship the build
output.

**2. The net flasher does not authenticate.** The net B0N is the NCS default
for `SOC_NRF5340_CPUNET`: hash-only. No P-256 constants, no
`verify_public_keys`, and `0x55e0` bytes — smaller than the hash-only reference
build. The images do carry a valid ECDSA P-256 signature (over
`sha256(sha256(payload))`), and each build has its own key matching the
provision, but the net B0N never reads it. The hash it does check is stored
inside the image being flashed.

**3. Confirmed on hardware.** A retail unit booted a net image whose
`fw_info.version` was bumped and whose hash was recomputed, leaving the
signature stale — Bluetooth came up normally. PCD writes at `0x01008800` in
place, so there is no fallback image. Done entirely over the side-button USB
recovery port: no SWD, no opening the case.

Details, disassembly and boot logs: [`bootloader/NET-CORE-UPDATE.md`](bootloader/NET-CORE-UPDATE.md).
Client: [`net/upload-net.py`](net/upload-net.py).

Note that the `net_secondary` version strings (`88.89.8195+…`) are still an
uninitialized read (SRAM pointers): flash area 9 (NAND) is FTL-unmapped and
reads erased. That datum was real; only its interpretation was wrong.

## MCUboot reference facts

Header field offsets (validated across all artifacts): magic `0x96F3B83D` @0,
load @4, `hdr_size` @8, `img_size` @12, version @20–24.

Trust root (retail bootloader, single key slot):

```text
release SPKI sha256  95126e317331ae1921dbcb4338a4821d92e2d0bf9a1503c5dd524e2c222b4634
development SPKI     60ae7f65f255d3f90d7145fabb0bf84c00e4c351226f561478759f3d6e215e0c
```

The bootloader region dump lets anyone verify the SPKI location (`0x1125F`),
flash-area table, and boot strings themselves.

## Known gaps (contributions wanted)

- **Versions 1.1.1–1.1.4 and 1.1.6–1.1.8**. The OTA endpoint serves
  latest-only, and the bucket key uses a **7-character** short build ID while the
  manifest reports the full **12-character** one. Asking for the long form
  returns `{"message":"File does not exist"}`, which looks exactly like a
  deletion but is a path-shape error: `1.1.5_0e21a76/app_update.bin` still
  downloads and hashes to the archived copy, while `1.1.5_0e21a768aec0/…` does
  not. So older versions are reachable *if their short build ID is known*, and
  "deleted" should not be assumed — `1.1.9_bd223cf` and `1.1.0_90a06ec` both
  still resolve. A device readback remains the practical source for versions
  whose build ID is unknown. 1.1.5 is in the inventory above (device readback by
  @smanaton); its manifest records build `0e21a768aec0`, whole-image SHA-256
  `94d38ea4f7cc8a273081ec6f5b76c87ab8b12bb11af08dd50c7c0016cd146eeb`,
  and signed-content digest
  `5b47290074e9904fad0007e1d5aed49800adc0c7044538917afa924c9ab233ab`.
- **Net-flash resident region `0x0–0x36b54`** — now covered. The B0N
  (`0x0–0x55e0`), provision (`0x85a8–0x87b0`) and net app (`0x8800–0x32304`)
  are in [`net/`](net/README.md), extracted from the vendor's
  `merged_domains.hex`. Still missing: the UICR of the net core, and a
  *readback* from a device (the artifacts are build outputs, not dumps).
- Net-core UICR (never observed).
- Bootloader/UICR dumps + dev-key acceptance results across manufacture
  batches (batch variance is cheap and occasionally decisive).

## Getting the current OTA image yourself

No account needed: the stock Android app fetches manifests from
`api-internal.limitless.ai/v3/pendant/getSignedManifest` using a Firebase
anonymous-signup token; the Firebase web API key and project id are embedded
in the stock APK (`ai.limitless.mobile`). The response's `signedURL` points
at `storage.googleapis.com/firmware.limitless.ai/artifacts/pendant/…`. The
endpoint serves the **latest** image only — there is no history, which is why
this archive exists. Bucket keys use a 7-character short build ID
(`1.1.20_b312ca1`), not the 12-character string in the manifest
(`b312ca1efaaa`); the long form resolves to "File does not exist". Exact
tuples confirmed so far: `1.1.9_bd223cf`, `1.1.20_b312ca1` (plus the
dev-channel 1.1.20).

## Restoring a bricked unit (proven, no teardown)

Enter red-LED recovery (short press, then long hold until the LED turns red;
USB re-enumerates as `2fe3:0100`), then:

```bash
mcumgr --timeout 20 --tries 3 --conntype serial \
  --connstring 'dev=/dev/ttyACM0,baud=115200,mtu=512' \
  image upload -n 0 --maxwinsize 1 ota/limitless-pendant-1.1.20-production-release-e03aa55de923.img
mcumgr --conntype serial --connstring 'dev=/dev/ttyACM0,baud=115200,mtu=512' reset
```

Upload acceptance is transport-only; MCUboot still verifies the signature
before anything boots. These stock images carry the vendor signature, so
restore works on retail bootloaders.

## Ethics / scope

Interoperability and preservation research on hardware we own. Report
coordinate-disclosure-worthy bugs to the maintainers before publishing
exploit detail. If you hold rights to these binaries and object to
preservation hosting, open an issue and we will resolve it with you.

## Links

- [limitless-libre issue #1](https://github.com/shade-familiar/limitless-libre/issues/1) — the running research thread
- [Routes-to-unsigned-firmware catalog (gist)](https://gist.github.com/axAilotl/04cb12148f6c697e7720d77ef87fbc9e)
- [Recovery, signing & interop field report (gist)](https://gist.github.com/axAilotl/2b897e8ca193ea1af2c2a44669783d4a)
- [RePendant](https://github.com/COREkunas/RePendant) — working custom firmware + app for the Pendant (first flash via SWD)
