# App-core bootloader versions

The bootloader is **not OTA-updated** — it is flashed at manufacture and stays. App
updates advance, the bootloader does not follow. So which bootloader a unit runs
depends on when it was made, not which app version it reports.

The files here are the app-core bootloader region (`0x0–0x14000`) extracted from the
vendor's `merged_domains.hex` builds, plus one retail readback.

| file | sha256 | last used | key |
|---|---|---|---|
| `nrf5340-appcore-boot-0x0-0x14000.bin` (retail readback) | `bd35f61d3be2e89d49d2c438603065d17854bb869c4f19262f3448c00e4c0e5a` | `0x11E54` | release `95126e31…` @`0x1125F` |
| `nrf5340-appcore-boot-1.0.1-dev.bin` | `af047450548b0c50…` | `0x11E54` | dev `60ae7f65…` |
| `nrf5340-appcore-boot-1.1.5-release.bin` | `dae019a28a141052…` | `0x11EB4` | release `95126e31…` @`0x112BF` |
| `nrf5340-appcore-boot-1.1.5-dev.bin` | `e30252e4136ea473…` | `0x11EB4` | dev `60ae7f65…` |

1.1.20 release and development are byte-identical to the corresponding 1.1.5 builds, so
they are not duplicated here. The 1.0.1 release build is also not duplicated: it is
byte-for-byte the retail readback already in this directory.

## What this establishes

- **The retail readback is vendor-confirmed.** It matches the 1.0.1 release build
  exactly, so it is no longer just a dump we trust.
- **A unit reporting app 1.1.5 can be running the 1.0.1-era bootloader.** Ours is. The
  1.1.5 bundle rebuilds the bootloader (`0x60` larger, signing key moved from
  `0x1125F` to `0x112BF`), but no unit updated over the air receives it.
- **Four distinct bootloaders exist** across the six archived builds, differing by
  version and by signing key. Development builds embed the development key, so a
  release unit and a development unit do not share a bootloader.

## Restore implication

Restoring from the newest bundle installs a bootloader the unit never ran. For a
mass-erase restore, match the bootloader to the unit's manufacture batch:

- a unit like ours (1.0.1-era bootloader) should be restored with
  `nrf5340-appcore-boot-0x0-0x14000.bin` — the retail readback, identical to the
  1.0.1 release build;
- a later unit may carry the 1.1.5/1.1.20 build, but this is unverified: no unit with
  that bootloader has been observed here.

The vendor cannot patch the bootloader OTA, and it does not appear to reflash it in the
field, so the population is probably split by manufacture date. Dumping `0x0–0x14000`
over the shell and comparing the first 32-bit words is enough to classify a unit.
