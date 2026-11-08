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
| `usb-shell-dumps/pendant-1.1.0-app-payload.bin` | 921,204 | `350787a28f7b66fc9100014fab7bb36b3879bdf5e24d0771606015fea3bd49c7` | payload split out of the slot dump above |
| `netcore/netcore-embedded-1.1.0.bin` | 771,408 | `7f0070501464f21e81de7c847f8227621a2189083e980796989cb9bd29c7b5de` | extracted from the 1.1.0 `app_update.bin` container |
| `netcore/netcore-embedded-1.1.9.bin` | 382,276 | `ac87f1ec951ebee116a1290fe5d4c4e59881892fdcc71c1fcc583ad76ba73f18` | extracted from the 1.1.9 `app_update.bin` container |
| `netcore/netcore-embedded-1.1.20.bin` | 382,260 | `a94242ac13e9befb688318e61c0136c89069e9967334951a18774540c8a54b6e` | extracted from the 1.1.20 `app_update.bin` container (dev-channel child is byte-identical) |
| `bootloader/nrf5340-appcore-boot-0x0-0x14000.bin` | 81,920 | `bd35f61d3be2e89d49d2c438603065d17854bb869c4f19262f3448c00e4c0e5a` | app-core internal flash `0x0–0x14000`, read from a retail unit |

`SHA256SUMS` at the root covers every file.

## Why the 1.1.0 dump matters

The 1.1.0 slot dump is ~397 KB larger than the OTA images because it ships a
**complete nRF700x Wi-Fi stack** (driver, wpa_supplicant v2.11 with WPA3-SAE,
websocket upload path) that was compiled out from 1.1.9 onward. The Wi-Fi
hardware is present on every unit. On a stock 1.1.0 unit the USB shell exposes
`wifi_cred add/list`, `config set server_name/port/ingest_token`, and
`comm wifi_connect/server_connect` — an unauthenticated, configurable
audio-streaming endpoint over Wi-Fi, no exploit needed.

The 1.1.0 network-core child (771 KB) also contains the Wi-Fi stack; custom
network-core firmware builders can lift the driver from it.

## Network-core child images

The network-core update image rides **inside** `app_update.bin` — there is no
separate bucket path. The extracted children are full Zephyr product apps
(PDM capture + beamforming, IMU/battery/LED, BLE host, an mcumgr/SMP server
that can write both cores' secondary slots), XIP-based at net-flash
`0x36b54`, linked against a resident library below that base. The
update-path verification inside these images is **SHA-256 only** — no
signature check on this path; whether the resident flasher authenticates is
the open question (see the gists).

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
  latest-only and has already deleted older tuples (1.1.7 returns a missing
  object error). A device readback is now the only source. 1.1.5 is now in the
  inventory above (device readback by @smanaton); its manifest records build
  `0e21a768aec0`, whole-image SHA-256
  `94d38ea4f7cc8a273081ec6f5b76c87ab8b12bb11af08dd50c7c0016cd146eeb`,
  and signed-content digest
  `5b47290074e9904fad0007e1d5aed49800adc0c7044538917afa924c9ab233ab`.
- **Net-flash resident region `0x0–0x36b54`** (resident boot chain + shared
  library + the RPC flasher at `0x8800`) — present in **no** extracted
  artifact anywhere. This is the single highest-value missing dump: it would
  settle whether the net-core update path authenticates images.
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
this archive exists. Exact tuples confirmed so far:
`1.1.9_bd223cf`, `1.1.20_b312ca1` (plus the dev-channel 1.1.20);
`1.1.7` is deleted.

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
