# Owner-key bootloaders (SWD once, then USB)

These replace the vendor's app-core bootloader so the unit boots images signed
with our key instead of the vendor's. Installing one needs the SWD pads and a
debug probe: the loader region is locked while firmware runs, the stock loader
boots only vendor-signed images, and no signing key exists on any device. There
is no USB or BLE path to this step.

After that everything is USB. Both loaders accept images over serial recovery
(`../../recovery/README.md`), and under rev2 the loader and app regions are
also writable from the stock app's USB shell.

| file | what it is | size | loader region after boot |
|---|---|---|---|
| `nrf5340-appcore-boot-rev2-ours.bin` | upstream MCUboot from the vendor's tree revision (`nRF Connect SDK 3758bcbfa5cd`, Zephyr 3.5), one app slot at `0x14000` (`0xEC000`), ECDSA-P256, serial recovery over CDC ACM | 56,276 B | unlocked, `SPU.FLASHREGION[0] = 0x17`, shell-writable |
| `nrf5340-appcore-boot-rev3-ours.bin` | the vendor's 1.1.5/1.1.20 release loader binary with our public key swapped in at `0x112BF`; exactly 64 bytes differ from `../nrf5340-appcore-boot-1.1.5-release.bin` | 73,396 B | stock lockdown, `0x115`, SWD only |
| `pendant-1.1.0-ourkey-signed.img` | the factory 1.1.0 app, payload byte-identical to the vendor's, re-signed with our key (`imgtool verify` passes) | 921,952 B | |
| `cissa-pendant-ec256-pub.pem` | the verification key both loaders embed | | |

The private half is not published, so the binaries here only boot images we
signed. To run your own images, generate your own key, build the loader with
`mcuboot-rev2.conf` and the overlay (point `CONFIG_BOOT_SIGNATURE_KEY_FILE` at
your public key), and sign with `imgtool sign --key your-key.pem`.

- Build: board `nrf5340dk_nrf5340_cpuapp`, Zephyr 3.5 tree, SDK 0.16.4. CMake 4.4
  does not build Zephyr 3.5; 3.31.6 does.
- rev2 is the second attempt. The first kept `WAIT_FOR_DFU` together with
  `NO_APPLICATION`, and its serial recovery never came up: the console is
  initialised twice on that path. rev2 drops `WAIT_FOR_DFU`.
- rev2 has no recovery-detect button wired (recovery only with an empty slot)
  and no PCD, so under rev2 the network core is updated over SWD. rev3 keeps
  the vendor machinery, including the button path and PCD.

rev2 is the tinkerer's loader: everything stays writable from the USB shell.
rev3 is the daily-driver loader: stock-identical posture under our key. The app
region stays shell-writable under both.

## Install once, over SWD

You need the SWD pads (see `hardware/`), a CMSIS-DAP probe and OpenOCD with
nRF53 support. A stock unit has APPROTECT armed at runtime. CTRL-AP ERASEALL
wipes the app core and opens debug until the next reset or until the OpenOCD
session detaches, so the whole install runs in one session with the chip held:

1. Trigger ERASEALL and examine the core (`nrferaseall.tcl`).
2. Write `0x50FA50FA` to UICR `APPROTECT` (`0xFF8000`) and `SECUREAPPROTECT`
   (`0xFF801C`) so debug stays open after reset.
3. Program the loader at `0x0`, then the app at `0x14000`, one word at a time.
4. Read both regions back. Only if every word matches does the script reset
   the core into the new firmware; otherwise it stays attached and halted.

Start with ERASEALL in the same session. Attaching to a running target gave
PPB write faults (`0xE000105C`, `0xE000EDF0`) here.

Writes are raw NVMC: `CONFIG` (`0x50039504`) = 1, wait for `READYNEXT`
(`0x50039408`) bit 0, then one `mww` per word. Our final run programmed
230,488 words with zero retries and read back byte-exact. The write loop
retries a word up to five times; one other run needed a single retry in 230k.

```sh
cd bootloader/ours/swd
python3 mkwords.py ../nrf5340-appcore-boot-rev2-ours.bin > loader-words.tcl   # or rev3
python3 mkwords.py ../pendant-1.1.0-ourkey-signed.img    > app-words.tcl
openocd -f swd.cfg -c init -c "source install-ours.tcl"
```

`swd/` holds the OpenOCD config, the ERASEALL procedure, the write loop and
`mkwords.py`. The word lists are generated and git-ignored.

The network core is untouched by this. rev3 can take a net image over USB
recovery afterwards (image 3, see `../../net/`). Under rev2 use SWD with the
artifacts in `../../net/`: B0N at `0x01000000`, provision at `0x010085A8`, net
app at `0x01008800`.

## Servicing over the USB shell

With our loader installed, the stock app's unauthenticated shell can rewrite
flash directly:

- `devmem <addr> 32 <value>` programs one word through NVMC.
- Page erase on nRF5340: set NVMC `CONFIG = 2` (erase mode) and write
  `0xFFFFFFFF` to the first word of the page. Return to `CONFIG = 1` for
  programming.
- Pace it. About 15 words per second, one command per line, with a read drain
  in between. A burst of 64 lines overflows the shell's receive ring silently:
  our first attempt lost 286 of 287 words with no error anywhere.

We replaced rev2 with rev3 entirely this way: 18 pages erased, 18,349 words
written, sampled readback 0/287 mismatches, boot-proved afterwards. A loader
write that goes wrong leaves the unit needing SWD, so change the loader only
with the probe attached.
