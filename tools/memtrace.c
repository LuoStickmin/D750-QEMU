/*
 * Minimal filtered memory tracer for the D750 QEMU prototype.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * It instruments every translated instruction and logs data accesses that
 * fall into a small set of diagnostic windows.  Output is one JSON object per
 * line through qemu_plugin_outs(); run QEMU with "-d plugin -D qemu.log" so it
 * lands in the log file.
 */

#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>

#include <qemu-plugin.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

struct trace_range {
    uint64_t lo;
    uint64_t hi;
    const char *name;
    bool stores_only;
    unsigned long cap;
    unsigned long seen;
};

static struct trace_range ranges[] = {
    { 0x100A6700ULL, 0x100A6800ULL, "flag", false, 512, 0 },
    { 0xB801F000ULL, 0xB8020000ULL, "pt", true, 4096, 0 },
    { 0x10000000ULL, 0x10030000ULL, "img", true, 4096, 0 },
    { 0x90020000ULL, 0x90020200ULL, "vec", false, 512, 0 },
    { 0x10600000ULL, 0x10610000ULL, "stack", true, 1024, 0 },
    { 0x80005000ULL, 0x80005020ULL, "uart-a", false, 128, 0 },
    { 0x440C4000ULL, 0x440C5000ULL, "uart-m", false, 128, 0 },
};

static const char *range_name(uint64_t addr, bool is_store, unsigned long *idx)
{
    size_t i;

    for (i = 0; i < sizeof(ranges) / sizeof(ranges[0]); i++) {
        if (addr >= ranges[i].lo && addr < ranges[i].hi &&
            (!ranges[i].stores_only || is_store)) {
            *idx = i;
            return ranges[i].name;
        }
    }
    return NULL;
}

static const char *value_str(qemu_plugin_mem_value v, char *buf, size_t len)
{
    switch (v.type) {
    case QEMU_PLUGIN_MEM_VALUE_U8:
        snprintf(buf, len, "0x%02" PRIx8, v.data.u8);
        break;
    case QEMU_PLUGIN_MEM_VALUE_U16:
        snprintf(buf, len, "0x%04" PRIx16, v.data.u16);
        break;
    case QEMU_PLUGIN_MEM_VALUE_U32:
        snprintf(buf, len, "0x%08" PRIx32, v.data.u32);
        break;
    case QEMU_PLUGIN_MEM_VALUE_U64:
        snprintf(buf, len, "0x%016" PRIx64, v.data.u64);
        break;
    default:
        snprintf(buf, len, "?");
        break;
    }
    return buf;
}

static void mem_cb(unsigned int vcpu, qemu_plugin_meminfo_t info,
                   uint64_t vaddr, void *userdata)
{
    bool is_store = qemu_plugin_mem_is_store(info);
    unsigned int shift = qemu_plugin_mem_size_shift(info);
    unsigned long idx;
    const char *name = range_name(vaddr, is_store, &idx);
    char valbuf[32];
    char line[256];
    uint64_t pc = (uint64_t)(uintptr_t)userdata;

    if (!name) {
        return;
    }
    if (ranges[idx].seen++ >= ranges[idx].cap) {
        return;
    }

    qemu_plugin_mem_value v = qemu_plugin_mem_get_value(info);
    snprintf(line, sizeof(line),
             "MEMTRACE {\"vcpu\":%u,\"pc\":\"0x%08" PRIx64 "\","
             "\"addr\":\"0x%08" PRIx64 "\",\"size\":%u,\"rw\":\"%s\","
             "\"value\":\"%s\",\"range\":\"%s\"}\n",
             vcpu, pc, vaddr, 1u << shift, is_store ? "w" : "r",
             value_str(v, valbuf, sizeof(valbuf)), name);
    qemu_plugin_outs(line);
}

static void vcpu_tb_trans(struct qemu_plugin_tb *tb, void *userdata)
{
    size_t n = qemu_plugin_tb_n_insns(tb);
    size_t i;

    (void)userdata;
    for (i = 0; i < n; i++) {
        struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
        uint64_t pc = qemu_plugin_insn_vaddr(insn);

        qemu_plugin_register_vcpu_mem_cb(
            insn, mem_cb, QEMU_PLUGIN_CB_NO_REGS, QEMU_PLUGIN_MEM_RW,
            (void *)(uintptr_t)pc);
    }
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
                                           const qemu_info_t *info,
                                           int argc, char **argv)
{
    (void)argc;
    (void)argv;
    if (!info->system_emulation) {
        fprintf(stderr, "memtrace: system emulation only\n");
        return -1;
    }
    qemu_plugin_outs("MEMTRACE ready\n");
    qemu_plugin_register_vcpu_tb_trans_cb(id, vcpu_tb_trans, NULL);
    return 0;
}
