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
- a later unit may carry the 1.1.5/1.1.20 build. One has been seen since: its
  loader shows the newer layout (SPKI header at `0x112BF`, nothing at
  `0x1125F`), but only single words were read, not a full dump.

The vendor cannot patch the bootloader OTA, and it does not appear to reflash it in the
field, so the population is probably split by manufacture date. Dumping `0x0–0x14000`
over the shell and comparing the first 32-bit words is enough to classify a unit.

## Owner-key rebuilds (not vendor builds)

Two more loaders live in [`ours/`](ours/README.md). They are not vendor
artifacts and never ship on a retail unit; they are what we flash over SWD so
a unit boots our own signed images.

| file | sha256 | key | loader region after boot |
|---|---|---|---|
| `ours/nrf5340-appcore-boot-rev2-ours.bin` | `62fc2e1b98a362e377ba8dbbf65a64fc043aae2f3c26b94d2ca364a751714645` | ours, SPKI at `0xD470` | unlocked (`0x17`) |
| `ours/nrf5340-appcore-boot-rev3-ours.bin` | `98be37076802d94a562657a7b1ffcb1c73fe5614d5cb89e0eb7adff0231f70ce` | ours, SPKI at `0x112BF` (64 bytes changed from the 1.1.5 release loader) | stock lockdown (`0x115`) |
