/*
 * Nikon D750 validation prototype machine.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * This is an *experimental validation prototype*, not a D750 emulator and
 * not a complete EXPEED 4 model.  It exists to answer a small, ordered set
 * of questions about a locally supplied, already decrypted D750 module:
 *
 *   M0  does the image load at the inferred base and start at the inferred
 *       entry with the inferred CPU state?
 *   M1  which MMIO windows does the first execution slice touch?
 *   M2  does the firmware emit bytes through the candidate serial block?
 *   M3  how far does it get once the first missing device is supplied?
 *
 * The machine therefore favours *diagnostics* over plausible-looking data:
 * an unmapped access is logged with PC/address/size/direction instead of
 * silently returning zero, and strict=on removes the catch-all window so
 * QEMU stops on the first access it does not model.
 *
 * Inputs (nothing is downloaded or embedded):
 *   -kernel  FILE   the decrypted main image, normally b1010_115a.bin
 *   -bios    FILE   the decrypted first-stage/flash image, a1010_011100.bin
 *   -machine nikon-d750,payload=FILE,flash=FILE,entry=ADDR,strict=on
 *
 * The payload is mapped at D750_RAM_BASE and the flash image at
 * D750_FLASH_BASE.  See nikon-d750-lab.h and ../docs/findings.md.
 */

#include "qemu/osdep.h"

#include "qapi/error.h"
#include "qapi/visitor.h"
#include "qemu/error-report.h"
#include "qemu/log.h"
#include "qemu/module.h"
#include "qemu/timer.h"
#include "qemu/units.h"

#include "chardev/char-fe.h"
#include "exec/cpu-common.h"
#include "hw/arm/machines-qom.h"
#include "hw/core/boards.h"
#include "hw/core/cpu.h"
#include "hw/core/loader.h"
#include "hw/core/qdev-properties.h"
#include "hw/core/sysbus.h"
#include "hw/cpu/a9mpcore.h"
#include "qom/object.h"
#include "system/cpus.h"
#include "system/memory.h"
#include "system/runstate.h"
#include "system/system.h"
#include "target/arm/cpu.h"
#include "target/arm/cpu-qom.h"

#include "nikon-d750-lab.h"

#define TYPE_NIKON_D750_MACHINE MACHINE_TYPE_NAME("nikon-d750")

/* qdev GPIO input order on every ARM CPU.  Kept local because the old
 * include/hw/arm/arm.h that carried this enum no longer exists. */
enum {
    D750_CPU_IRQ = 0,
    D750_CPU_FIQ,
    D750_CPU_VIRQ,
    D750_CPU_VFIQ,
};

typedef struct NikonD750MachineState {
    MachineState parent;

    MemoryRegion lowram;        /* vectors / boot globals at 0x0          */
    MemoryRegion halt;          /* return trampoline: fetch = clean exit   */
    MemoryRegion flash;         /* RAM-backed, read/write in this prototype */
    MemoryRegion probe;         /* catch-all diagnostic window             */
    MemoryRegion uart;          /* candidate byte-register serial block    */

    CharFrontend chr;

    char *payload;
    char *flash_path;
    uint64_t entry;             /* UINT64_MAX means "use the inferred one" */
    bool strict;
    uint32_t uart_status;

    uint64_t probe_events;
    uint64_t uart_events;

    /* Optional framebuffer dump path.  No address is guessed: the window is
     * inert until -machine lcd-base=... is supplied. */
    uint64_t lcd_base;
    uint32_t lcd_width;
    uint32_t lcd_height;
    uint32_t lcd_stride;
    char *lcd_format;
    char *lcd_out;
    QEMUTimer *lcd_timer;
} NikonD750MachineState;

DECLARE_INSTANCE_CHECKER(NikonD750MachineState, NIKON_D750_MACHINE,
                         TYPE_NIKON_D750_MACHINE)

/* ------------------------------------------------------------------ */
/* Diagnostics                                                         */
/* ------------------------------------------------------------------ */

static uint64_t d750_guest_pc(void)
{
    CPUState *cs = current_cpu;

    if (!cs) {
        return 0;
    }
    return ARM_CPU(cs)->env.regs[15];
}

static uint64_t d750_probe_read(void *opaque, hwaddr addr, unsigned size)
{
    NikonD750MachineState *s = opaque;

    if (s->probe_events < 512 || (s->probe_events % 4096) == 0) {
        qemu_log_mask(LOG_GUEST_ERROR,
                      "d750-probe: pc=0x%08" PRIx64
                      " rd addr=0x%08" HWADDR_PRIx " size=%u"
                      " (unmodelled read, returning 0)\n",
                      d750_guest_pc(), addr, size);
    }
    s->probe_events++;
    return 0;
}

static void d750_probe_write(void *opaque, hwaddr addr, uint64_t value,
                             unsigned size)
{
    NikonD750MachineState *s = opaque;

    if (s->probe_events < 512 || (s->probe_events % 4096) == 0) {
        qemu_log_mask(LOG_GUEST_ERROR,
                      "d750-probe: pc=0x%08" PRIx64
                      " wr addr=0x%08" HWADDR_PRIx " size=%u value=0x%08" PRIx64
                      " (unmodelled write)\n",
                      d750_guest_pc(), addr, size, value);
    }
    s->probe_events++;
}

static const MemoryRegionOps d750_probe_ops = {
    .read = d750_probe_read,
    .write = d750_probe_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid.min_access_size = 1,
    .valid.max_access_size = 8,
    .impl.min_access_size = 1,
    .impl.max_access_size = 8,
};

/* ------------------------------------------------------------------ */
/* Optional framebuffer dump                                           */
/* ------------------------------------------------------------------ */
/*
 * A host-side observation tool, not a display model.  It reads the
 * configured window from guest RAM and writes a PPM.  The window is inert
 * until -machine lcd-base=... is supplied, so no framebuffer address is
 * guessed.  Once G1 of docs/gui-cmos.md observes the real address and
 * format, only the machine options change.
 */

static void d750_lcd_dump(NikonD750MachineState *s)
{
    MachineState *machine = MACHINE(s);
    uint32_t bpp, stride, x, y;
    uint64_t size;
    uint8_t *ram, *row;
    FILE *f;

    if (!s->lcd_base || !s->lcd_out || !s->lcd_format) {
        return;
    }
    if (s->lcd_width == 0 || s->lcd_height == 0 ||
        s->lcd_width > 4096 || s->lcd_height > 4096) {
        return;
    }

    if (!strcmp(s->lcd_format, "rgb565")) {
        bpp = 2;
    } else if (!strcmp(s->lcd_format, "rgb888")) {
        bpp = 3;
    } else {
        bpp = 4;
    }
    stride = s->lcd_stride ? s->lcd_stride : s->lcd_width * bpp;
    size = (uint64_t)stride * s->lcd_height;
    if (s->lcd_base < D750_RAM_BASE || size > machine->ram_size ||
        s->lcd_base - D750_RAM_BASE > machine->ram_size - size) {
        qemu_log_mask(LOG_GUEST_ERROR,
                      "d750-lcd: window 0x%08" PRIx64
                      " (%" PRIu64 " bytes) is outside the RAM window\n",
                      s->lcd_base, size);
        return;
    }

    ram = memory_region_get_ram_ptr(machine->ram) +
          (s->lcd_base - D750_RAM_BASE);
    f = fopen(s->lcd_out, "wb");
    if (!f) {
        qemu_log_mask(LOG_GUEST_ERROR, "d750-lcd: cannot open '%s'\n",
                      s->lcd_out);
        return;
    }
    fprintf(f, "P6\n%u %u\n255\n", s->lcd_width, s->lcd_height);
    for (y = 0; y < s->lcd_height; y++) {
        row = ram + (uint64_t)y * stride;
        for (x = 0; x < s->lcd_width; x++) {
            uint8_t rgb[3];

            if (bpp == 2) {
                uint16_t v = row[x * 2] | (row[x * 2 + 1] << 8);
                rgb[0] = (uint8_t)(((v >> 11) & 0x1f) * 255 / 31);
                rgb[1] = (uint8_t)(((v >> 5) & 0x3f) * 255 / 63);
                rgb[2] = (uint8_t)((v & 0x1f) * 255 / 31);
            } else if (bpp == 3) {
                const uint8_t *p = row + x * 3;
                rgb[0] = p[0];
                rgb[1] = p[1];
                rgb[2] = p[2];
            } else {
                /* little-endian ARGB8888: memory order B, G, R, A */
                const uint8_t *p = row + x * 4;
                rgb[0] = p[2];
                rgb[1] = p[1];
                rgb[2] = p[0];
            }
            fwrite(rgb, 1, 3, f);
        }
    }
    fclose(f);
    qemu_log_mask(LOG_GUEST_ERROR,
                  "d750-lcd: dumped %ux%u (%s, stride %u) from 0x%08" PRIx64
                  " to %s\n", s->lcd_width, s->lcd_height, s->lcd_format,
                  stride, s->lcd_base, s->lcd_out);
}

static void d750_lcd_tick(void *opaque)
{
    NikonD750MachineState *s = opaque;

    d750_lcd_dump(s);
    timer_mod(s->lcd_timer,
              qemu_clock_get_ms(QEMU_CLOCK_REALTIME) + 2000);
}

/* ------------------------------------------------------------------ */
/* Return trampoline                                                   */
/* ------------------------------------------------------------------ */
/*
 * The inferred entry is a called function.  The assisted startup gives it
 * LR = D750_HALT_TRAMPOLINE; when it returns, the fetch from this
 * four-byte window is both the "entry finished" evidence and a clean
 * shutdown request, so a run terminates instead of spinning.
 */

static uint64_t d750_halt_read(void *opaque, hwaddr addr, unsigned size)
{
    NikonD750MachineState *s = opaque;

    d750_lcd_dump(s);
    if (current_cpu) {
        ARMCPU *cpu = ARM_CPU(current_cpu);

        qemu_log_mask(LOG_GUEST_ERROR,
                      "d750-halt: pc=0x%08" PRIx64
                      " r0=0x%08" PRIx32 " r1=0x%08" PRIx32
                      " sp=0x%08" PRIx32 " lr=0x%08" PRIx32
                      " firmware returned to the assisted trampoline\n",
                      d750_guest_pc(),
                      cpu->env.regs[0], cpu->env.regs[1],
                      cpu->env.regs[13], cpu->env.regs[14]);
    } else {
        qemu_log_mask(LOG_GUEST_ERROR,
                      "d750-halt: firmware returned to the assisted trampoline\n");
    }
    qemu_system_shutdown_request(SHUTDOWN_CAUSE_GUEST_SHUTDOWN);
    return 0;
}

static void d750_halt_write(void *opaque, hwaddr addr, uint64_t value,
                            unsigned size)
{
    d750_halt_read(opaque, addr, size);
}

static const MemoryRegionOps d750_halt_ops = {
    .read = d750_halt_read,
    .write = d750_halt_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid.min_access_size = 4,
    .valid.max_access_size = 4,
    .impl.min_access_size = 4,
    .impl.max_access_size = 4,
};

/* ------------------------------------------------------------------ */
/* Candidate serial block                                              */
/* ------------------------------------------------------------------ */
/*
 * The driver slice at file offset 0x27CC00..0x27D304 reaches a byte-wide
 * register block at 0x80005010..0x80005014.  We model the smallest useful
 * contract: a TX byte at +0x10, a status byte at +0x11, and a second
 * status/control byte at +0x14.  Everything else is logged and returns
 * zero.  A wrong decode shows up as a probe log line and a stalled poll,
 * which is exactly the information the next iteration needs.
 */

static uint64_t d750_uart_read(void *opaque, hwaddr addr, unsigned size)
{
    NikonD750MachineState *s = opaque;
    uint64_t value = 0;

    switch (addr) {
    case 0x11:
    case 0x14:
        value = s->uart_status;
        break;
    default:
        value = 0;
        break;
    }

    if (s->uart_events < 128) {
        qemu_log_mask(LOG_GUEST_ERROR,
                      "d750-uart: pc=0x%08" PRIx64
                      " rd +0x%02" HWADDR_PRIx " size=%u -> 0x%02" PRIx64 "\n",
                      d750_guest_pc(), addr, size, value);
    }
    s->uart_events++;
    return value;
}

static void d750_uart_write(void *opaque, hwaddr addr, uint64_t value,
                            unsigned size)
{
    NikonD750MachineState *s = opaque;

    if (addr == 0x10) {
        uint8_t ch = value & 0xff;

        if (qemu_chr_fe_backend_connected(&s->chr)) {
            qemu_chr_fe_write_all(&s->chr, &ch, 1);
        }
        qemu_log_mask(LOG_TRACE, "d750-uart: tx 0x%02x ('%c')\n",
                      ch, (ch >= 0x20 && ch < 0x7f) ? ch : '.');
    } else {
        qemu_log_mask(LOG_GUEST_ERROR,
                      "d750-uart: pc=0x%08" PRIx64
                      " wr +0x%02" HWADDR_PRIx " size=%u value=0x%02" PRIx64 "\n",
                      d750_guest_pc(), addr, size, value & 0xff);
    }
    s->uart_events++;
}

static const MemoryRegionOps d750_uart_ops = {
    .read = d750_uart_read,
    .write = d750_uart_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid.min_access_size = 1,
    .valid.max_access_size = 4,
    .impl.min_access_size = 1,
    .impl.max_access_size = 4,
};

/* ------------------------------------------------------------------ */
/* Machine properties                                                  */
/* ------------------------------------------------------------------ */

static char *nikon_d750_get_payload(Object *obj, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    return g_strdup(s->payload);
}

static void nikon_d750_set_payload(Object *obj, const char *value, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    g_free(s->payload);
    s->payload = g_strdup(value);
}

static char *nikon_d750_get_flash(Object *obj, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    return g_strdup(s->flash_path);
}

static void nikon_d750_set_flash(Object *obj, const char *value, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    g_free(s->flash_path);
    s->flash_path = g_strdup(value);
}

static void nikon_d750_get_entry(Object *obj, Visitor *v, const char *name,
                                 void *opaque, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint64_t value = s->entry;

    visit_type_uint64(v, name, &value, errp);
}

static void nikon_d750_set_entry(Object *obj, Visitor *v, const char *name,
                                 void *opaque, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint64_t value;

    if (!visit_type_uint64(v, name, &value, errp)) {
        return;
    }
    s->entry = value;
}

static bool nikon_d750_get_strict(Object *obj, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    return s->strict;
}

static void nikon_d750_set_strict(Object *obj, bool value, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    s->strict = value;
}

static void nikon_d750_get_lcd_base(Object *obj, Visitor *v,
                                    const char *name, void *opaque,
                                    Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint64_t value = s->lcd_base;

    visit_type_uint64(v, name, &value, errp);
}

static void nikon_d750_set_lcd_base(Object *obj, Visitor *v,
                                    const char *name, void *opaque,
                                    Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint64_t value;

    if (!visit_type_uint64(v, name, &value, errp)) {
        return;
    }
    s->lcd_base = value;
}

static void nikon_d750_get_lcd_width(Object *obj, Visitor *v,
                                     const char *name, void *opaque,
                                     Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint32_t value = s->lcd_width;

    visit_type_uint32(v, name, &value, errp);
}

static void nikon_d750_set_lcd_width(Object *obj, Visitor *v,
                                     const char *name, void *opaque,
                                     Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint32_t value;

    if (!visit_type_uint32(v, name, &value, errp)) {
        return;
    }
    s->lcd_width = value;
}

static void nikon_d750_get_lcd_height(Object *obj, Visitor *v,
                                      const char *name, void *opaque,
                                      Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint32_t value = s->lcd_height;

    visit_type_uint32(v, name, &value, errp);
}

static void nikon_d750_set_lcd_height(Object *obj, Visitor *v,
                                      const char *name, void *opaque,
                                      Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint32_t value;

    if (!visit_type_uint32(v, name, &value, errp)) {
        return;
    }
    s->lcd_height = value;
}

static void nikon_d750_get_lcd_stride(Object *obj, Visitor *v,
                                      const char *name, void *opaque,
                                      Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint32_t value = s->lcd_stride;

    visit_type_uint32(v, name, &value, errp);
}

static void nikon_d750_set_lcd_stride(Object *obj, Visitor *v,
                                      const char *name, void *opaque,
                                      Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);
    uint32_t value;

    if (!visit_type_uint32(v, name, &value, errp)) {
        return;
    }
    s->lcd_stride = value;
}

static char *nikon_d750_get_lcd_format(Object *obj, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    return g_strdup(s->lcd_format);
}

static void nikon_d750_set_lcd_format(Object *obj, const char *value,
                                      Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    g_free(s->lcd_format);
    s->lcd_format = g_strdup(value);
}

static char *nikon_d750_get_lcd_out(Object *obj, Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    return g_strdup(s->lcd_out);
}

static void nikon_d750_set_lcd_out(Object *obj, const char *value,
                                   Error **errp)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    g_free(s->lcd_out);
    s->lcd_out = g_strdup(value);
}

/* ------------------------------------------------------------------ */
/* Machine                                                             */
/* ------------------------------------------------------------------ */

static void nikon_d750_init(MachineState *machine)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(machine);
    MemoryRegion *sysmem = get_system_memory();
    const char *payload = s->payload ? s->payload : machine->kernel_filename;
    const char *flash = s->flash_path ? s->flash_path : machine->firmware;
    DeviceState *mpcore;
    SysBusDevice *busdev;
    uint64_t entry;
    int i;

    if (!payload) {
        error_report("nikon-d750: a decrypted main payload is required; "
                     "pass -kernel FILE or -machine nikon-d750,payload=FILE");
        exit(1);
    }
    if (machine->ram_size < D750_RAM_MIN ||
        machine->ram_size > D750_RAM_MAX) {
        error_report("nikon-d750: RAM size must be between %" PRIu64
                     " and %" PRIu64 " bytes",
                     (uint64_t)D750_RAM_MIN, (uint64_t)D750_RAM_MAX);
        exit(1);
    }

    /* Main DRAM window. */
    memory_region_add_subregion(sysmem, D750_RAM_BASE, machine->ram);

    /* First-stage / flash window.  RAM-backed so the prototype can load a
     * module into it; the production model should become a real ROM. */
    memory_region_init_ram(&s->flash, NULL, "nikon-d750.flash",
                           D750_FLASH_SIZE, &error_fatal);
    memory_region_add_subregion(sysmem, D750_FLASH_BASE, &s->flash);
    if (flash) {
        if (load_image_targphys(flash, D750_FLASH_BASE, D750_FLASH_SIZE,
                                &error_fatal) < 0) {
            error_report("nikon-d750: cannot load flash image '%s'", flash);
            exit(1);
        }
    }

    /* Catch-all diagnostics.  Real regions above win by priority; strict
     * mode leaves the holes empty so an unexpected access traps in QEMU. */
    if (!s->strict) {
        memory_region_init_io(&s->probe, OBJECT(s), &d750_probe_ops, s,
                              "nikon-d750.probe", D750_PROBE_SIZE);
        memory_region_add_subregion_overlap(sysmem, 0, &s->probe,
                                            D750_PROBE_PRIORITY);
    }

    /* Low memory: the entry stores a word at address 0 and reads it back,
     * so the first 64 KiB must be writable RAM.  A four-byte halt window
     * sits at the assisted return address: fetching it ends the run. */
    memory_region_init_ram(&s->lowram, NULL, "nikon-d750.lowram",
                           D750_LOWRAM_SIZE, &error_fatal);
    memory_region_add_subregion(sysmem, D750_LOWRAM_BASE, &s->lowram);
    memory_region_init_io(&s->halt, NULL, &d750_halt_ops, s,
                          "nikon-d750.halt", 4);
    memory_region_add_subregion_overlap(sysmem, D750_HALT_TRAMPOLINE,
                                        &s->halt, 1);

    /* CPUs.  The firmware is ARMv7-A Thumb-2 with VFP/NEON; Cortex-A9 is
     * the working hypothesis for EXPEED 4.  -cpu overrides it. */
    for (i = 0; i < machine->smp.cpus; i++) {
        Object *cpuobj = object_new(machine->cpu_type);

        qdev_realize(DEVICE(cpuobj), NULL, &error_fatal);
    }

    /* Cortex-A9 MPCore private block (GIC + timers + watchdog). */
    mpcore = qdev_new(TYPE_A9MPCORE_PRIV);
    qdev_prop_set_uint32(mpcore, "num-cpu", machine->smp.cpus);
    qdev_prop_set_uint32(mpcore, "num-irq", D750_GIC_NUM_IRQ);
    busdev = SYS_BUS_DEVICE(mpcore);
    sysbus_realize_and_unref(busdev, &error_fatal);
    sysbus_mmio_map(busdev, 0, D750_MPCORE_BASE);
    for (i = 0; i < machine->smp.cpus; i++) {
        DeviceState *cpudev = DEVICE(qemu_get_cpu(i));

        sysbus_connect_irq(busdev, i,
                           qdev_get_gpio_in(cpudev, D750_CPU_IRQ));
        sysbus_connect_irq(busdev, i + machine->smp.cpus,
                           qdev_get_gpio_in(cpudev, D750_CPU_FIQ));
        sysbus_connect_irq(busdev, i + 2 * machine->smp.cpus,
                           qdev_get_gpio_in(cpudev, D750_CPU_VIRQ));
        sysbus_connect_irq(busdev, i + 3 * machine->smp.cpus,
                           qdev_get_gpio_in(cpudev, D750_CPU_VFIQ));
    }

    /* Candidate serial block. */
    memory_region_init_io(&s->uart, OBJECT(s), &d750_uart_ops, s,
                          "nikon-d750.uart", D750_UART_SIZE);
    memory_region_add_subregion(sysmem, D750_UART_BASE, &s->uart);
    if (serial_hd(0)) {
        qemu_chr_fe_init(&s->chr, serial_hd(0), &error_abort);
    }

    /* Payload goes in last, after the RAM window exists. */
    if (load_image_targphys(payload, D750_RAM_BASE, machine->ram_size,
                            &error_fatal) < 0) {
        error_report("nikon-d750: cannot load payload '%s'", payload);
        exit(1);
    }

    entry = s->entry == UINT64_MAX ? D750_RAM_BASE + D750_ENTRY_OFFSET
                                   : s->entry;
    for (i = 0; i < machine->smp.cpus; i++) {
        CPUState *cs = qemu_get_cpu(i);
        ARMCPU *cpu = ARM_CPU(cs);

        /* Assisted startup: the inferred entry is a called function, so
         * supply a stack and a return trampoline instead of reset values. */
        cpu->env.regs[13] = D750_RAM_BASE + machine->ram_size - 0x100;
        cpu->env.regs[14] = D750_HALT_TRAMPOLINE;
        cpu->env.regs[0] = 0;
        cpu_set_pc(cs, entry);
    }

    if (s->lcd_base) {
        s->lcd_timer = timer_new_ms(QEMU_CLOCK_REALTIME, d750_lcd_tick, s);
        timer_mod(s->lcd_timer,
                  qemu_clock_get_ms(QEMU_CLOCK_REALTIME) + 2000);
    }

    info_report("nikon-d750: payload=%s @ 0x%08" PRIx64
                ", flash=%s @ 0x%08" PRIx64
                ", entry=0x%08" PRIx64 ", ram=%" PRIu64 " MiB, cpus=%u%s",
                payload, (uint64_t)D750_RAM_BASE,
                flash ? flash : "(none)", (uint64_t)D750_FLASH_BASE,
                entry, machine->ram_size / MiB, machine->smp.cpus,
                s->strict ? ", strict" : "");
}

static void nikon_d750_instance_init(Object *obj)
{
    NikonD750MachineState *s = NIKON_D750_MACHINE(obj);

    s->entry = UINT64_MAX;
    s->uart_status = 0x03;
    s->lcd_width = 640;
    s->lcd_height = 480;
    s->lcd_format = g_strdup("argb8888");
    s->lcd_out = g_strdup("lcd.ppm");
}

static void nikon_d750_class_init(ObjectClass *oc, const void *data)
{
    MachineClass *mc = MACHINE_CLASS(oc);
    static const char *const valid_cpu_types[] = {
        ARM_CPU_TYPE_NAME("cortex-a9"),
        NULL
    };

    mc->desc = "Nikon D750 validation prototype (EXPEED 4, experimental)";
    mc->init = nikon_d750_init;
    mc->default_cpu_type = ARM_CPU_TYPE_NAME("cortex-a9");
    mc->valid_cpu_types = valid_cpu_types;
    mc->max_cpus = 2;
    mc->min_cpus = 1;
    mc->default_ram_size = 128 * MiB;
    mc->default_ram_id = "nikon-d750.ram";

    object_class_property_add_str(oc, "payload",
                                  nikon_d750_get_payload,
                                  nikon_d750_set_payload);
    object_class_property_set_description(oc, "payload",
        "Path to the decrypted main payload (normally b1010_<ver>.bin)");
    object_class_property_add_str(oc, "flash",
                                  nikon_d750_get_flash,
                                  nikon_d750_set_flash);
    object_class_property_set_description(oc, "flash",
        "Path to the decrypted first-stage/flash image (normally a1010_<ver>.bin)");
    object_class_property_add(oc, "entry", "uint64",
                              nikon_d750_get_entry, nikon_d750_set_entry,
                              NULL, NULL);
    object_class_property_set_description(oc, "entry",
        "Initial PC; default is the inferred payload entry (0x9027D52C)");
    object_class_property_add_bool(oc, "strict",
                                   nikon_d750_get_strict,
                                   nikon_d750_set_strict);
    object_class_property_set_description(oc, "strict",
        "Abort on unmodelled MMIO instead of logging and returning 0");

    object_class_property_add(oc, "lcd-base", "uint64",
                              nikon_d750_get_lcd_base,
                              nikon_d750_set_lcd_base, NULL, NULL);
    object_class_property_set_description(oc, "lcd-base",
        "Guest framebuffer base for the optional PPM dump (0 = disabled)");
    object_class_property_add(oc, "lcd-width", "uint32",
                              nikon_d750_get_lcd_width,
                              nikon_d750_set_lcd_width, NULL, NULL);
    object_class_property_set_description(oc, "lcd-width",
        "Framebuffer width in pixels (default 640)");
    object_class_property_add(oc, "lcd-height", "uint32",
                              nikon_d750_get_lcd_height,
                              nikon_d750_set_lcd_height, NULL, NULL);
    object_class_property_set_description(oc, "lcd-height",
        "Framebuffer height in pixels (default 480)");
    object_class_property_add(oc, "lcd-stride", "uint32",
                              nikon_d750_get_lcd_stride,
                              nikon_d750_set_lcd_stride, NULL, NULL);
    object_class_property_set_description(oc, "lcd-stride",
        "Framebuffer stride in bytes (0 = width * bytes-per-pixel)");
    object_class_property_add_str(oc, "lcd-format",
                                  nikon_d750_get_lcd_format,
                                  nikon_d750_set_lcd_format);
    object_class_property_set_description(oc, "lcd-format",
        "argb8888 (default), rgb888 or rgb565");
    object_class_property_add_str(oc, "lcd-out",
                                  nikon_d750_get_lcd_out,
                                  nikon_d750_set_lcd_out);
    object_class_property_set_description(oc, "lcd-out",
        "PPM output path (default lcd.ppm)");
}

static const TypeInfo nikon_d750_info = {
    .name = TYPE_NIKON_D750_MACHINE,
    .parent = TYPE_MACHINE,
    .instance_size = sizeof(NikonD750MachineState),
    .instance_init = nikon_d750_instance_init,
    .class_init = nikon_d750_class_init,
    .interfaces = arm_machine_interfaces,
};

static void nikon_d750_register_types(void)
{
    type_register_static(&nikon_d750_info);
}

type_init(nikon_d750_register_types);
