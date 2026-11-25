# GUI context startup: new direction (reference: z30-qemu)

> [中文](gui-context.md) | English

> Date: 2026-11-25 · Status: **direction change, not implemented yet**.
> Natural boot is paused; the goal is now "supply context → call original GUI/
> display functions → capture original pixels".

## 1. Why the change

D750's host-assisted A-core already reaches the SVC/A300 service loop at
`0x10025474`, but going further needs T-Kernel services, scheduling and the
cross-core handshake — a whole RTOS layer before any original GUI appears.

z30-qemu takes a different route: it explicitly **does not do natural boot**.
Instead, the host invokes original firmware functions at version-specific task
checkpoints and supplies explicit diagnostic state; original GPU commands then
render a 720×480 menu. That model fits the current stage better.

References (external):
- <https://github.com/WonderLantern/z30-qemu>
- Local README: `C:\Users\23795\Downloads\README.md`

## 2. Goal

Apply z30's assisted-GUI approach to D750:

1. locate D750 original **GUI/display init functions or task checkpoints**;
2. have the QEMU machine supply their context (stack, globals, task/queue,
   Display/GPU MMIO, framebuffer, diagnostic returns);
3. call those functions directly so original firmware draws the menu/LCD;
4. prove "original pixels" with the existing PPM dump (browser later).

**Natural full boot is not the acceptance criterion**; host fixtures are not a
boot ROM.

## 3. Current evidence and gaps

| Item | Status |
| --- | --- |
| A-core real reset → next stage | ✅ host-assisted to `0x1000E200`/SVC loop |
| M-core `a1010` | ✅ BE8 to idle `0xC04A` |
| GUI/Display/GPU strings | ✅ `Display/GPU/GDU/TFT/@APPMENU` present |
| GUI function/task entry | ❌ not located |
| Display/GPU MMIO contract | ❌ no accesses observed |
| Framebuffer address/format | ❌ not observed; existing `lcd-base` is host-config |
| Browser GUI | ❌ only host-side PPM dump |

## 4. Proposed architecture

### 4.1 Machine/mode

New diagnostic mode (name TBD, e.g. `nikon-d750-gui` or `gui-context=on`):

- still map b1010 at `0x90020000`;
- do not run the natural reset/SVC chain; the host sets initial PC/SP/registers;
- map candidate Display/GPU/GDU windows as **observable stubs** recording
  address/width/value;
- reuse `lcd-base/width/height/stride/format/out` dumping;
- all context comes from a version-specific checkpoint table, not the generic
  boot path.

### 4.2 Context contents

First milestone only needs "call one function and return":

- stack: a writable stack in IRAM/DRAM;
- globals: pointers/structs required by the signature, initially zero/diagnostic;
- task/queue: if the function consults T-Kernel tables, provide a minimal static
  table or fixed handle;
- Display/GPU: let init writes not crash first, then add semantics;
- diagnostics: log unmodelled accesses with PC/address; do not return fake
  plausible data.

### 4.3 Checkpoint table

Maintain per firmware version (`D750_0115`):

```text
checkpoint name | firmware addr | call convention | required context | evidence
```

Generate it manually/static first; fill it with plugin/GDB later.

## 5. Work order

1. **Static location**: xref `@APPMENU`, `Display`, `GPU`, `GDU`, `TFT` strings/
   pointers; find UI init, menu rendering, GPU submission functions; follow
   z30's `rom_xrefs.py` idea.
2. **Minimal call**: choose the function with the fewest dependencies (drawing/
   init), call it with a synthetic stack and zero context; record exception/MMIO.
3. **Fill context**: add structs/task/Display stubs from each failure until the
   function returns or starts writing framebuffer/GPU commands.
4. **Capture**: configure `lcd-base` or GPU target buffer, dump PPM; original
   font/menu pixels are the first GUI milestone.
5. **Interaction/browser**: input injection and HTTP GUI last, not in milestone 1.

## 6. Acceptance and boundaries

- Acceptance: original function executes, original GPU commands or framebuffer
  pixels appear; a repeatable checkpoint.
- Not acceptance: natural power-on boot, full T-Kernel, CMOS/ISP, recording.
- Risk: GUI may depend on scheduling/IPC/GPU firmware; a single function call
  may not work. If milestone 1 fails, record dependencies and extend context
  with the plugin instead of guessing SVC semantics.

## 7. Relation to existing work

- Keep A-core host-assisted/SVC evidence as a source of context;
- SVC service table is no longer the current main line;
- M-core remains independent and does not block the GUI direction;
- existing `tools/memtrace.c`/GDB scripts are used to find GUI access context.

## 8. First experiment (2026-11-25)

Candidate **task-name table** entries in b1010 (name followed by a Thumb entry):

| Task name | Name address | Entry (bit0=Thumb) |
| --- | --- | --- |
| `TFTSERV` | `0x900234FC` | `0x900231AD` |
| `TFTBACK` | `0x9003DFB8` | `0x9003DCA9` |
| `HDMSERV` | `0x90025628` | `0x900253A3` |
| `HDMIVD` | `0x90025634` | `0x9002521D` |
| `POSTSERV` | `0x901DDD20` | `0x901DD60B` |
| `APPMENU` (name in code pool) | `0x9012CDA0` | candidate `0x9012CD75` |

The host-assisted A-core run to `0x10025474` was used to `pmemsave` an 8 MiB
`0x10000000` flash context (SHA-256 `76261fb2…3bac91a5`); it was then passed as
`--flash` while calling the entries:

| Entry | Result |
| --- | --- |
| `0x900231AD` TFTSERV | clean return, `SP=0x97FFFF00`, 0 MMIO, 0 UART |
| `0x9003DCA9` TFTBACK | halt-suspicious, `SP=0` |
| `0x9012CD75` APPMENU | halt-suspicious, `SP=0` |
| `0x900253A3` HDMSERV | halt-suspicious, `SP=0` |

Conclusion: these are **T-Kernel task mains**, not standalone drawing functions.
A flash context is not enough — TFTSERV returns after service calls, while TFTBACK/
APPMENU/HDMSERV lose SP in the task/service context. The next "context" is
**T-Kernel task/global state and service return values**, not more Display MMIO
guesses.

Evidence: [`evidence/gui-context/summary.json`](../evidence/gui-context/summary.json).
