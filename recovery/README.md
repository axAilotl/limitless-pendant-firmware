# USB recovery console: what it accepts and how to use it

Enter recovery by holding the side button while plugging in USB, until the LED
turns red. The device re-enumerates from `2fe3:0110` (app) to `2fe3:0100`
(MCUboot serial recovery). Leave by unplugging, or with `os reset`
(`python3 net/upload-net.py --port <dev> --reset`).

Everything below was measured on retail units carrying both loader builds
(`bd35f61d…` and `dae019a2…`).

## Command set

| group / id | effect |
|---|---|
| 1 / 0, read | image state |
| 1 / 0, write | test / confirm (writes the slot trailer) |
| 1 / 1, write | image upload |
| 0 / 1 | `rc 0` on any operation |
| 0 / 5 | `os reset`. It fires on a *read* as well, so never include it in a sweep |
| anything else | `rc 8` (ENOTSUP) |

Both loader builds answer identically: 380 requests over groups 0–8, 63, 64 and
60000, all answered, 376 of them `rc 8`.

## Framing

```
06 09 + base64( u16 length + SMP packet + CRC16-CCITT, residue 0 ) + 0a
```

Continuation frames start with `04 14`. Frames of 124 base64 characters are
accepted and frames of 128 or more are dropped without an error, so send at
most 48 data bytes per request. The request grows as the offset field grows, so
keep a margin. Data is written in 4-byte units: a 45-, 46- or 47-byte chunk is
acknowledged at 44. Continue from the acknowledged `off`, not from what you sent.

The stock app's USB port is not an SMP transport. Raw or bare-base64 frames get
no answer from either console, and that looks exactly like a dead console. Check
`lsusb -d 2fe3:0100` before sending anything.

## What each image number writes

| upload `image` | target |
|---|---|
| 0 or 1 | app primary slot, in place (966,656 B) |
| 2 | app secondary slot (NAND) |
| 3 | RAM staging, then handed to the network core through PCD. See `../bootloader/NET-CORE-UPDATE.md` |
| 4 | net secondary slot (NAND) |

The loader region is not reachable from recovery.

## Liveness probe (read-only)

```sh
python3 net/upload-net.py --port <dev> --state
```

## Speed

`net/upload-net.py` returns as soon as the reply frame arrives. Before
2026-11-23 it waited out a 200 ms port timeout on every reply, which made a
171 KB net image take 862 s. Measured on one unit since the change: net image
14–17 s, 921 KB app image 105 s.

## Move the app to any vendor-signed release

Upload as image 0 overwrites the only bootable app in place. At the next boot
the loader runs it only if the vendor signature verifies, and no stock image
carries a rollback counter, so downgrades work.

Proven on a sealed unit with the newer loader build: `pendant-1.1.0-vendor-signed.img`
here is the header + payload + TLV portion (921,952 B) of the 1.1.0 slot dump
in `../usb-shell-dumps/`, and `imgtool verify` validates it against the retail
key. After the upload the loader listed slot 0 as `1.1.0` with the expected
hash; after `os reset` the app booted as `1.1.0`.

```sh
python3 net/upload-net.py --port <dev> --state
python3 net/upload-net.py --port <dev> --image 0 --file recovery/pendant-1.1.0-vendor-signed.img
python3 net/upload-net.py --port <dev> --reset
```

- The upload erases page by page as it advances. If it is interrupted the unit
  has no valid app: put it back in recovery with the button and upload again.
- Going back is the same procedure with any stock OTA image, for example
  `ota/limitless-pendant-1.1.20-production-release-e03aa55de923.img`. Exercised
  the same day: factory 1.1.0 to 1.1.20 in 59 s, the loader listed slot 0 as
  `1.1.20` with the stock hash, and the app booted as `1.1.20`.
- Settings did not survive in either direction on our unit: each app fell back
  to defaults when it could not find its own. Expect to pair again.

## Wi-Fi on factory 1.1.0

The stack is present (`wifi_cred`, `comm wifi_connect`, `config`) and the Wi-Fi
device reports `READY`, but on two retail units the radio never joined an
access point that a phone joined, with WPA2 or open, and the battery gauge
showed no scan current during the attempt. Wi-Fi did not work on the retail
hardware we have, with this firmware.

## Audit tool

`../tools/recovery_console_audit.py` sweeps the command set and measures the
upload framing without writing flash: it refuses `os reset`, state writes and
completed uploads by construction.
