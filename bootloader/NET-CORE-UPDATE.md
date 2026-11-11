# Network-core update path: analysis and hardware result

Status: **verified on a retail unit, over USB, no SWD, case closed** (2026-11-11).

The question this answers: the app-core bootloader can hand network-core
firmware to the net core (`image 3` -> RAM -> PCD -> net flash `0x01008800`).
Does the resident net flasher authenticate what it receives?

It does not. The net core validates a SHA-256 hash that is stored inside the
image being flashed, so whoever supplies the image also supplies the hash. The
ECDSA signature the vendor puts in the image is never checked.

## Where the net-core firmware lives

`0x01000000`, one 256 KiB flash:

```
0x01000000..0x010055e0   B0N (net-core bootloader)        21,984 B
0x010055e0..0x010085a8   padding
0x010085a8..0x010087b0   provision (version + key hash)      520 B
0x01008800..0x01032304   net app (BT controller)        170,756 B
```

`0x01008800` is `PM_CPUNET_B0N_CONTAINER_SIZE`. The vendor never ships these
as a standalone file, but the firmware endpoint signs `merged_domains.hex`,
which contains both cores; see `../net/README.md`.

The B0N is byte-identical in 1.0.1, 1.1.5 and 1.1.20, and the net app payload
is too (`sha256 = 0d00cb8e…`). The firmware has not changed since 1.0.1.

## App core: the normal path skips validation

`candidate_serial_image_upload()` (`0x3bcc` in the 1.1.5 bootloader) is stock
MCUboot `img_mgmt_upload` with `MCUBOOT_SERIAL_DIRECT_IMAGE_UPLOAD`. It opens
`flash_area_id_from_direct_image(img_num)`, erases, writes chunks, and on the
last chunk calls a board hook. There is no `candidate_validate_slot`, no
`candidate_validate_image_crypto`, no TLVs; the whole upload is a byte copy.

The hook is NCS's `nrf53_hooks.c`, and the stock binary matches it exactly:

```c
int boot_serial_uploaded_hook(int img_index, const struct flash_area *area,
                              size_t size)
{
        if (img_index == NET_CORE_VIRTUAL_PRIMARY_SLOT) {   /* 3 */
                return network_core_update(false);
        }
        return 0;
}

int network_core_update(bool wait)
{
        mock_flash = flash_simulator_get_memory(NULL, &mock_size);
        hdr = (struct image_header *)mock_flash;
        if (hdr->ih_magic == IMAGE_MAGIC) {
                fw_size = hdr->ih_img_size;
                vtable  = (uint32_t *)hdr + hdr->ih_hdr_size;
                if (vtable[1] > PM_CPUNET_B0N_ADDRESS) {    /* 0x01000000 */
                        return pcd_network_core_update(vtable, fw_size);
                }
        }
        return -ENODATA;
}
```

Disassembly of `0xda96` (the stock hook):

```
0xda96  cmp r0, #3                     ; img_index
0xdab2  ldr r0, [flash_sim]            ; 0x200089f6 on this build
0xdabc  ldr r1, [r0]                   ; ih_magic
0xdac0  cmp r1, 0x96f3b83d
0xdac8  ldrh r2, [r0, #8]              ; ih_hdr_size
0xdacc  ldr r1, [r0, r2, +4]           ; vtable[1]
0xdad0  cmp r1, 0x01000000
0xdad4  bl 0x79ec                      ; pcd_network_core_update_initiate
```

`0x79ec` inlines `pcd_network_core_update_initiate()`: magic `0xb5b4b3b6` at
`0x20000000`, source pointer at `0x20000004`, length at `0x20000008`, offset
`0x8800` at `0x2000000c`, SPU extdomain at `0x50003000+0x440`, a 1 s
`k_busy_wait`, then `k_timer_start`.

So the only checks between a host and net flash are: `img_index == 3`, an
MCUboot magic, and a reset vector above `0x01000000`.

## Net core: B0N checks a hash, not a signature

NCS defaults to hash-only validation for `SOC_NRF5340_CPUNET`, on the
assumption that the app core did the signature check:

```kconfig
config SB_VALIDATE_FW_SIGNATURE
	default y if !SOC_NRF5340_CPUNET
config SB_VALIDATE_FW_HASH
	default y
	depends on SOC_NRF5340_CPUNET
	help
	  Hash validation (not secure). Only meant for nRF5340 network core
	  since the app core will do the signature validation.
```

The stock B0N is that default build. Three independent confirmations:

**1. Size.** The stock B0N is `0x55e0`. The Nordic hash-only reference build
is `0x58e6`; an ECDSA build does not fit.

**2. Constants.** P-256 constants in the stock B0N versus the app-core
bootloader (which does validate signatures):

| constant | net B0N | app bootloader |
|---|---|---|
| SHA-256 IV | present | present |
| P-256 b | absent | present |
| P-256 Gx | absent | present |
| P-256 Gy | absent | present |

**3. Code.** The stock B0N's validation path is:

```
validate_firmware          (0x1040ae)
  fw_info magic, address, valid == 0x9102ffff
  memcmp validation-info magic (12 bytes)
  FUN_0x104052(payload, fw_size, hash_ptr)
      FUN_0x104080 -> FUN_0x1031f0        ; SHA-256
      FUN_0x1023c(computed, stored, 0x20) ; memcmp
```

There is no `verify_public_keys`, no `root_of_trust_verify`, no P-256 code
anywhere in the image. The net core PCD copy handler is at `0x102608`
(`pcd_fw_copy`, `stream_flash_buffered_write`), and the status/idle loop is at
`0x1005cc`.

### The signature the images do carry

Each net app ends with a validation struct at `app + 0x29a54`:

```
+0x00  magic        0x281ee6de 0x8fcebb4c 0x00013502
+0x0c  address      0x01008800
+0x10  hash[32]     sha256(app[0:0x29a54])
+0x30  public_key[64]  raw x||y, big-endian
+0x70  signature[64]   raw r||s, big-endian
```

The signature is valid ECDSA P-256 over `sha256(sha256(app[0:size]))` —
Nordic's `bl_ecdsa_verify` hashes its input, so the message is the digest of
the digest. Each build has its own key, and `sha256(key)` equals the key hash
in that build's provision. So the vendor signs these images properly; the net
B0N just never looks.

`../net/verify-net.py` checks all six builds.

## Hardware result

Two uploads over the side-button serial recovery port (`2FE3:0100`, SMP
`image` group, `image = 3`), 171,268 B each. The stock bootloader's SMP receive
buffer is 128 bytes, so frames over ~127 base64 characters are dropped
silently; 40-byte chunks work and take about 15 minutes.

**Stage 1 — unmodified vendor net app.** Copy completed (`os reset` returned
`EBUSY` while `PCD_STATUS_COPY`, then 0), device booted, Bluetooth up:

```
bluetooth: Starting Bluetooth secure
bt_hci_core: HW Platform: Nordic Semiconductor (0x0002)
bt_hci_core: HW Variant: nRF53x (0x0003)
bt_hci_core: HCI: version 5.4 (0x0d) revision 0x218f, manufacturer 0x0059
bluetooth: Bluetooth initialized
bluetooth: Advertising successfully started
```

**Stage 2 — same payload, deliberately invalid signature.** Only
`fw_info.version` (1 -> 2 at `+0x214`) and the stored hash (`+0x29a64`) were
changed; the signature at `+0x29ac0` was left alone, so it is valid only for
the old hash. Identical result: device booted, Bluetooth up, same HCI banner.

PCD writes the net app in place at `0x01008800`, so there is no older copy to
fall back to. The image that booted is the one whose signature does not match
its hash.

**Restore.** Uploading the stock image again restores version 1, confirmed by
the same boot log. The path is repeatable.

## Side effects

The PCD copy starts at `0x01008800`, which is not sector-aligned, so the first
erased sector is `0x01008000`, which contains the provision at `0x010085a8`.
It is wiped. This is harmless here: `0x010085a8` appears nowhere in the B0N, it
never reads the provision, and every PCD update would erase it anyway. It does
mean a device that later needs ECDSA net validation would need its provision
restored by other means.

## Failure behaviour (do not test casually)

The net-side copy handler on error:

```c
iVar3 = FUN_010040ae(fdev, data);           /* pcd_fw_copy */
if (iVar3 != 0) {
        iVar3 = FUN_01002608(device);       /* buffered retry */
        if (iVar3 == 0) {
                iVar3 = FUN_010040ae(fdev, data);
                if (iVar3 != 0) {
                        FUN_01002680();     /* PCD_CMD_MAGIC_FAIL */
                        do { } while (true);  /* PCD polling never resumes */
                }
        }
}
```

A failed *copy* leaves the net core spinning, and `image 3` can no longer reach
it; recovery would need SWD, which is destructive on this part. An image with a
deliberately wrong hash was therefore **not** tested. It is also unnecessary:
the attack needs a hash that matches, not one that does not.

## Reproducing

```
# side button through a qualifying reset -> USB 2FE3:0100
python ../net/upload-net.py --port COM6 --state
python ../net/upload-net.py --port COM6 --file net-app-1.1.5-release.bin
python ../net/upload-net.py --port COM6 --reset
```

`upload-net.py --file` accepts either a raw `0x29b04` net app (it wraps it) or
an already wrapped image.

## Consequences

- A sealed retail unit accepts arbitrary network-core firmware over USB. No
  case opening, no SWD, no signing key: the net core is where the Bluetooth
  controller runs.
- The design assumption in NCS ("the app core will do the signature
  validation") is not upheld by `MCUBOOT_SERIAL_DIRECT_IMAGE_UPLOAD`, which is
  the path that exists specifically to write the net core.
- The stock app-core bootloader is otherwise intact and still validates app
  images; this is a network-core-only hole.
