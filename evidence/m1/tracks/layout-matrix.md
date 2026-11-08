# Flash-layout matrix (2026-11-09)

Method: `nikon-d750` machine, `boot-mode=stub`, b1010 at `0x90000000`, each
candidate `-bios` image loaded at `0x10000000` (or at `a1010-base`), 2.5 s per
run, `-d int,guest_errors,in_asm`. "target" is the TB QEMU first executes at
`0x1002CB8C`.

| # | flash image @ base | thumb-fix | target bytes | execution after target | result |
|---|---|---|---|---|---|
| 1 | a1010 @ 0x10000000 | on | `20007924...` | 0x90020004 (data) | data, undefined loop |
| 2 | a1010 @ 0x10000000 | off | `20007924...` | 0x1002cb98, 0x90020008 | undefined loop |
| 3 | a1010 @ 0x10018000 | on | `10b51420...` | 0x10026b52 → 0x100240ac | M-profile `MRS/MSR BASEPRI`, undefined loop |
| 4 | a1010 @ 0x10018000 | off | `10b51420...` | 0x90020004 | Thumb code entered as ARM, undefined loop |
| 5 | a1010 @ 0x10018040 | on | `ae480860...` | 0x10026cfa → 0x10026d10 → 0 | A-profile-compatible, pops LR, returns to 0 |
| 6 | a1010 @ 0x10018040 | off | `ae480860...` | 0x90020004 | undefined loop |
| 7 | a1010 @ 0x10000090 | on | `48b1...` | 0x1002cba2 → 0x1002c4e4 → 0 | A-profile-compatible, returns to 0 |
| 8 | b1010 (960 KiB) @ 0x10000000 | on | `16e0` | 0x1002cbbc → 0x1002cada → 0x1002cb26 → 0x1003043e → 0x1014dff0 → … | runs into zero-filled flash (image truncated) |
| 9 | b1010 (1.5 MiB) @ 0x10000000 + MMU-off payload | on | `16e0` | veneer → 0x1003043e → 0x1014dff0 → 39 unique TBs → **SVC** | coherent A-core path; SVC vector at 0x90020000 is data |
| 10 | same as #9 + minimal SVC vector (`b`/`movs pc,lr`) | on | `16e0` | SVC returns at 0x1002ea68 → 0x0 | 303 TBs, 0 aborts, returns to LR=0 |
| 11 | update container (960 KiB) @ 0x10000000 | on | `48b1...` | 0x1002cba2 → 0x1002c4e4 → 0 | same as #7 (container starts with a1010) |
| 12 | update container (960 KiB) @ 0x10000000 | off | `48b1...` | 0x90020004 | undefined loop |

Notes:
- Runs 1/2/3/4/8/11/12 produce very large `in_asm` logs (50–120 MiB) because
  the undefined vector at `0x90020004` loops; the matrix only keeps counts.
- Run 8 needs the 960 KiB image to stay below the machine's config-slot blob at
  `0x100F48C0`; the overlap check rejects larger images unless `mmu-bringup=off`.
- Runs 9/10 use `mmu-bringup=off` and a payload whose `SCTLR` immediate is
  patched from `0x1C05` to `0x1C04` (MMU stays off) so the flash image can cover
  `0x100F48C0`; this is a diagnostic patch, not a firmware claim.

Raw logs: `b1010-flash-svc.log` (run 10), `mcore-boot.log` (track 3).
