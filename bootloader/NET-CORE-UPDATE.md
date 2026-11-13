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
0x010055e0..0x010085a8   not present in the build output
0x010085a8..0x010087b0   provision (version + key hash)      520 B
0x01008800..0x01032304   net app (BT controller)        170,756 B
```

`0x01008800` is `PM_CPUNET_B0N_CONTAINER_SIZE`. The vendor never ships these
as a standalone file, but the firmware endpoint signs `merged_domains.hex`,
which contains both cores; see `../net/README.md`.

The B0N is byte-identical in 1.0.1, 1.1.5 and 1.1.20, and the net app payload
is too (`sha256 = 0d00cb8e…`). The firmware has not changed since 1.0.1.

## App core: the normal path skips validation

`candidate_serial_image_upload()` (`0x3bcc` in the bootloader on observed retail
units) is stock MCUboot `img_mgmt_upload` with
`MCUBOOT_SERIAL_DIRECT_IMAGE_UPLOAD`. It opens
`flash_area_id_from_direct_image(img_num)`, erases, writes chunks, and on the
last chunk calls a board hook. There is no `candidate_validate_slot`, no
`candidate_validate_image_crypto`, no TLVs; the whole upload is a byte copy.

**Note on addresses:** the disassembly and all offsets below are from the
bootloader found on retail units observed here, which is the **1.0.1-era build**
(`sha256 bd35f61d…`, byte-identical to the 1.0.1 release build in
[`VERSIONS.md`](VERSIONS.md)). The 1.1.5/1.1.20 bundles ship a *different*
bootloader build (`dae019a2…`, `0x60` larger) that has not been observed in the
field; on such a unit these addresses will not line up.

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

Disassembly of the stock hook. `0xda96` is a thin wrapper; the body is
tail-called at `0x7ba0`:

```
0xda96  cmp     r0, #3
0xda9a  movs    r0, #0
0xda9c  bne     0xdaa2
0xda9e  b.w     0x7ba0
0xdaa2  bx      lr

0x7ba0  push    {r0, r1, r4, lr}
0x7ba2  mov     r4, r0                  ; the `wait` argument
0x7ba4  ldr     r0, [pc, #0x40]         ; 0x10498, flash device
0x7ba6  bl      0xfc34                  ; device_is_ready
0x7baa  cbz     r0, 0x7bda              ; -> -ENODEV (0xffffffed)
0x7bac  movs    r0, #0
0x7bae  add     r1, sp, #4
0x7bb0  bl      0x68c0                  ; flash_simulator_get_memory -> 0x200089f6
0x7bb4  ldr     r3, [pc, #0x34]         ; 0x96f3b83d
0x7bb6  ldr     r2, [r0]                ; ih_magic
0x7bb8  cmp     r2, r3
0x7bba  bne     0x7be0                  ; -> -ENODATA (0xffffffc3)
0x7bbc  ldrh    r3, [r0, #8]            ; ih_hdr_size
0x7bbe  ldr     r1, [r0, #0xc]          ; ih_img_size
0x7bc0  add     r0, r3                  ; vtable
0x7bc2  ldr     r3, [r0, #4]            ; vtable[1], the reset vector
0x7bc4  cmp.w   r3, #0x1000000
0x7bc8  bls     0x7be0                  ; -> -ENODATA
0x7bca  cbz     r4, 0x7bd4
0x7bcc  bl      0x7a34                  ; pcd_network_core_update(vtable, size)
0x7bd4  bl      0x79ec                  ; pcd_network_core_update_initiate(...)
```

`0x79ec` sets `0x50003000+0x440` (SPU extdomain), passes the COPY magic
`0xb5b4b3b6`, the vtable pointer and `ih_img_size` to `0x78f8`, which writes:

```
0x20000000  magic  0xb5b4b3b6
0x20000004  data   vtable (staged payload in the flash simulator)
0x20000008  len    ih_img_size
0x2000000c  offset 0x8800
```

then a 1 s `k_busy_wait` and a timer start. That is
`pcd_network_core_update_initiate()` with the arguments the hook read straight
out of the upload.

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

**1. Size.** The stock B0N is `0x55e0`, slightly smaller than the Nordic
hash-only reference build (`0x58e6`). That alone proves nothing — the B0N
container is `0x8800`, so there is headroom — but it is consistent with a build
that never enabled the signature path.

**2. Constants.** P-256 constants in the stock B0N versus the app-core
bootloader (which does validate signatures):

| constant | net B0N | app bootloader |
|---|---|---|
| SHA-256 IV | present | present |
| P-256 b | absent | present |
| P-256 Gx | absent | present |
| P-256 Gy | absent | present |

**3. Code.** The stock B0N contains exactly one crypto routine: SHA-256. The
validation routine (`0x1040ae`) takes an image address, walks its `fw_info`,
checks the magic, the address and `valid == 0x9102ffff`, finds the 12-byte
validation-info magic, then compares a SHA-256 of the payload against the hash
stored in that validation info:

```
0x1040ae(image_addr, ...)
  fw_info magic, address, valid == 0x9102ffff
  memcmp validation-info magic (12 bytes)
  0x104052(payload, fw_size, hash_ptr)
      0x104080 -> 0x1031f0            ; SHA-256
      0x1023c(computed, stored, 0x20) ; memcmp, no signature step
```

There is no public-key step, no `verify_public_keys`, no
`root_of_trust_verify`, and no P-256 code anywhere in the image. The two
SHA-256 call sites are this check and its caller. The PCD handling (status
dispatch, the hash check, the copy retry at `0x102608`) is in `0x1005cc` and
`0x102608`.

I could not map every B0N routine onto a current NCS symbol — the build is from
an older NCS than the one in the reference tree, and the decompiler mis-orders
some of the copy path's control flow. The conclusion does not depend on the
symbol names: the image contains no elliptic-curve code at all, and the only
verify routine compares a hash to a hash stored inside the image it is
checking.


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
`image` group, `image = 3`), 171,268 B each. Frame size is capped by the stock
bootloader's receive buffer: a 127-character base64 frame is accepted and a
135-character one is dropped without an error, so the buffer is about 128
bytes (the reference build uses 1024, and this one is much smaller). 40-byte
chunks fit even once `off` needs a five-byte CBOR encoding; at that rate an
upload takes about 15 minutes.

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
changed; the signature at `+0x29ac4` was left alone, so it is valid only for
the old hash. Identical result: device booted, Bluetooth up, same HCI banner.

PCD writes the net app in place at `0x01008800`, so there is no older copy to
fall back to. The image that booted is the one whose signature does not match
its hash.

**Restore.** Uploading the stock image again restores version 1, confirmed by
the same boot log. The path is repeatable.

## Side effects

The PCD copy starts at `0x01008800`, which is not sector-aligned. `pcd_fw_copy`
writes through `stream_flash`, which erases whole pages, so the first sector it
erases is `0x01008000` — and that sector contains the provision at
`0x010085a8`. On a normal part it is erased along with the net app's first
page. This is harmless here: `0x010085a8` appears nowhere in the B0N, it never
reads the provision, and every PCD update would erase it anyway. It does mean a
device that later needs ECDSA net validation would need its provision restored
by other means.

This is inference from `pcd_fw_copy` plus the flash geometry, not an
observation — the app core cannot read net flash, and the net core has no
readback path.

## Failure behaviour (do not test casually)

The net-side loop that services PCD is `0x1005cc`. It dispatches on the magic
(COPY / DONE / FAILED / READ_VERSION) and, on its error path, writes the FAIL
magic:

```
0x102680:  *0x20000000 = 0x25bafc15      ; PCD_CMD_MAGIC_FAIL
           do { } while (true)           ; PCD polling never resumes
```

I am deliberately not asserting more than that: the build is from an older NCS
than the reference tree, and the decompiler mis-orders this function's control
flow (`Type propagation algorithm not settling`, a dozen removed unreachable
blocks), so I can't say which call in which branch leads to the spin. What is
clear is that a PCD error ends in `MAGIC_FAIL` plus an infinite loop in which
the top-of-loop PCD poll is never reached again.

That is why an image with a deliberately wrong hash was **not** tested: if it
lands on that path, `image 3` can no longer reach the net core, and recovery
would need SWD, which is destructive on this part. The test is also
unnecessary — the attack needs a hash that matches, not one that does not.

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
