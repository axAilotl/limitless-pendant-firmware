# Pull data from your Pendant — 5 minutes, read-only

Helps the archive answer the last open questions before the service shuts
down. Everything here is **read-only**: no writes, no erase, no firmware
change, no teardown — just the stock USB shell. Requires Python 3 +
`pip install pyserial` and the Pendant on USB (normal mode, `2fe3:0110`).

```sh
python3 tools/pendant_ro_session.py /dev/ttyACM0 tools/census.txt > my-pendant.txt
```

(Windows: use the COM port, e.g. `COM5`. macOS: `/dev/cu.usbmodemXXXX`.)

Then paste `my-pendant.txt` into [limitless-libre issue #1](
https://github.com/shade-familiar/limitless-libre/issues/1). Redact the
`DEVICE ID` line if you prefer — everything else is device-state, not
personal data.

## What each part tells us

| Block | Why we want it |
|---|---|
| `mcuboot_info stored_images_info` | app version + the `net_secondary` value (uninitialized-memory study across units) |
| `devmem 0x1125F` / `0x112BF` | **which bootloader build your unit runs** (SPKI at 0x1125F = 1.0.1-era; at 0x112BF = 1.1.0+-era) — batch matrix |
| `devmem 0x50006…` (CTRL-AP) | debug-protection lock states across manufacture batches |
| `devmem 0x500034xx` (SPU) | flash-region permission/lock state (known to vary between units) |
| `devmem 0xFF8000…` (UICR) | APPROTECT/SECUREAPPROTECT words |
| `devmem 0x95000…0xD8000` | **stale bytes past the app image end** — on units with long update history these can contain unarchived firmware versions (see the 1.0.1 recovery in PR #2) |

Have more time? Two extra reads after `kernel reboot cold`:
`mcuboot_info stored_images_info` again (does `net_secondary` change
across reboots on your unit?) and re-run the whole census if you like —
every data point lands in the batch matrix.

The session driver refuses write-form `devmem`, erase, upload and reset
commands by design; the denylist is in the script.
