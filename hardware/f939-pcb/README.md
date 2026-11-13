# Retail Pendant PCB photographs (unit F939, opened for research)

EXIF stripped. Taken 2026-10-16/22 during teardown and SWD bring-up of a
sacrificial retail unit. Hardware documentation for anyone wiring debug
or building on the platform.

| File | Content |
|---|---|
| `f939-adboard-v32-nrf5340-top-20261022.jpg` | AD-Board V3.2 top: **nRF5340 QKAA** (N5340 QKAA, lot 2425BM), USB-C with gasket collar, **`SWO`/`GND`/`BUTTON` silkscreen pads** (the SWD debug surface), gold test-pad grid, FFC connector. Ruler for scale. |
| `f939-mainboard-v37-label-1FD5C3-20261016.jpg` | Main board macro: factory label `C1-X0525 / MainV1.0.1 / 1FD5C3` (QR), 40 MHz crystal, silkscreen `Main Board 24-0927 V3.7`, DM/DP points, shielded charge/board-to-board connector. |
| `f939-mainboard-v32-in-case-20261016.jpg` | Board in case ring: `Main Board P24-0827 V3.2`. |
| `f939-pcb-detail-20261016.jpg` | Component detail. |

Notes: two board revisions (V3.2, 24-0827 and V3.7, 24-0927) appear in
this one unit's photo set; SoC is nRF5340 QKAA (aQFN94). The `SWO` pad
cluster is the confirmed-working SWD attach point (DPIDR verified with an
MCU-Link at 1.8 V VTref, 2026-11-13).
