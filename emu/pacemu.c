/* pacemu: Midway Pac-Man without video or sound, for the pattern search.
 *
 * Runs the real program ROM on a Z80 core with the same memory map, interrupt and frame timing as
 * MAME 0.289's pacman driver (src/mame/pacman/pacman.cpp), so RAM matches MAME frame for frame.
 * A "frame" ends where MAME calls the Lua frame notifier; inputs are set between frames.
 * The whole machine state is one flat struct, so a savestate is a memcpy.
 *
 * Build: build.bat (MSVC) -> pacemu.dll, used from Python through emu.py. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "z80.h"

#define EXPORT __declspec(dllexport)

#define CYC_FRAME 50688u /* 3.072 MHz / 60.606 Hz: 384 x 264 pixels at 6.144 MHz, 2 per CPU cycle */
#define VBL_LINE 224     /* vblank starts at this line (192 cycles per line) */

typedef struct {
  z80 cpu;
  uint8_t ram[0x1000];    /* 0x4000-0x4FFF (0x4800-0x4BFF is unmapped and reads 0xBF) */
  uint8_t spr2[16];       /* 0x5060-0x506F sprite coordinates, write-only */
  uint8_t latch;          /* 74LS259 at 0x5000-0x5007: bit 0 = IRQ enable */
  uint8_t vector;         /* written to port 0, put on the bus when the IRQ is taken */
  uint8_t line;           /* IRQ line level */
  uint8_t in0, in1, dsw1, dsw2;
  uint8_t watchdog;       /* vblanks since the last write to 0x50C0 */
  uint32_t frame_end;     /* cycle of the next frame end (cpu.cyc wraps; compare as differences) */
  uint32_t vblank;        /* cycle of the next vblank */
  uint32_t frames;
  uint32_t resets;        /* watchdog resets (should stay 0) */
} pm_state;

typedef struct {
  pm_state s;
  uint8_t rom[0x4000];
  int32_t vbl_offset;     /* vblank minus frame end, in cycles (negative: vblank first) */
  int32_t idle;           /* skip the main loop's empty-queue spin (see pm_frame) */
  int32_t joy;            /* joystick direction held: -1 none, 0=R 1=D 2=L 3=U (not in savestates, like MAME) */
  uint8_t in0, in1;       /* the other input bits (coin, start); active low */
  int edge_on, edge_n;    /* see pm_edge */
  uint16_t edge_addr[8];
  uint8_t edge_old[8];
} pm;

/* debugging: log writes to one address */
static int32_t watch_addr = -1;
static uint32_t watch_log[256][4];
static int watch_n;
EXPORT void pm_watch(int addr) { watch_addr = addr; watch_n = 0; }
EXPORT int pm_watch_get(int i, uint32_t *out) { if (i >= watch_n) return 0; memcpy(out, watch_log[i], 16); return 1; }

/* Writes made by the instruction that crosses each frame end, oldest first, with the values they replaced.
   MAME's z80 can stop in the middle of an instruction, so at its frame notifier only the writes that
   instruction made before the frame end have happened; compare.py checks MAME's RAM against every
   prefix of these. Game state is unaffected: the rest of the instruction runs before anything reads it.
   Kept per machine (not global) so machines in different threads don't share them. */
EXPORT int pm_edge(pm *m, int i, int *addr, int *old) {
  if (i >= m->edge_n) return 0;
  *addr = m->edge_addr[i]; *old = m->edge_old[i]; return 1;
}

static uint8_t rd(void *u, uint16_t a) {
  pm *m = (pm *)u;
  a &= 0x7FFF;
  if (a < 0x4000) return m->rom[a];
  a &= ~0x2000;
  if (a < 0x4800) return m->s.ram[a - 0x4000];
  if (a < 0x4C00) return 0xBF;
  if (a < 0x5000) return m->s.ram[a - 0x4000];
  switch (a & 0xC0) {
  case 0x00: return m->s.in0;
  case 0x40: return m->s.in1;
  case 0x80: return m->s.dsw1;
  default: return m->s.dsw2;
  }
}

static void wr(void *u, uint16_t a, uint8_t v) {
  pm *m = (pm *)u;
  if (watch_addr >= 0 && (a & ~0xA000) == watch_addr && watch_n < 256) {
    watch_log[watch_n][0] = m->s.cpu.pc; watch_log[watch_n][1] = v; watch_log[watch_n][2] = m->s.frames; watch_log[watch_n][3] = m->s.frame_end - (uint32_t)m->s.cpu.cyc; watch_n++;
  }
  a &= 0x7FFF;
  if (a < 0x4000) return;
  a &= ~0x2000;
  if (a < 0x4800 || (a >= 0x4C00 && a < 0x5000)) {
    if (m->edge_on && m->edge_n < 8) { m->edge_addr[m->edge_n] = a; m->edge_old[m->edge_n] = m->s.ram[a - 0x4000]; m->edge_n++; }
    m->s.ram[a - 0x4000] = v;
    return;
  }
  if (a < 0x5000) return;
  switch (a & 0xC0) {
  case 0x00:
    if ((a & 0x38) == 0) {
      int bit = a & 7;
      m->s.latch = (uint8_t)((m->s.latch & ~(1 << bit)) | ((v & 1) << bit));
      if (bit == 0 && !(v & 1)) m->s.line = 0;
    }
    return;
  case 0x40:
    if ((a & 0x30) == 0x20) m->s.spr2[a & 0xF] = v; /* 0x5060-0x506F; 0x5040-0x505F is sound */
    return;
  case 0x80: return;
  default: m->s.watchdog = 0; return;
  }
}

static uint8_t pin(z80 *z, uint8_t port) { (void)z; (void)port; return 0xFF; }
static void pout(z80 *z, uint8_t port, uint8_t v) {
  if (port == 0) ((pm *)z->userdata)->s.vector = v;
}

static void hook(pm *m) {
  m->s.cpu.read_byte = rd;
  m->s.cpu.write_byte = wr;
  m->s.cpu.port_in = pin;
  m->s.cpu.port_out = pout;
  m->s.cpu.userdata = m;
}

/* Power-on: MAME 0.289's z80 starts with every register 0 except IX and IY, which are 0xFFFF. */
static void cpu_power_on(pm *m) {
  z80 *z = &m->s.cpu;
  z80_init(z);
  z->a = z->a_ = z->b_ = z->c_ = z->d_ = z->e_ = z->h_ = z->l_ = z->f_ = 0;
  z->sf = z->zf = z->yf = z->hf = z->xf = z->pf = z->nf = z->cf = 0;
  z->sp = 0;
  z->ix = z->iy = 0xFFFF;
  hook(m);
}

/* Reset (watchdog): MAME's device_reset only sets PC, I, R and the interrupt flip-flops, and leaves halt.
   The latch is cleared by the board reset. */
static void cpu_reset(pm *m) {
  z80 *z = &m->s.cpu;
  z->pc = 0; z->i = 0; z->r = 0;
  z->iff1 = z->iff2 = 0; z->iff_delay = 0; z->halted = 0; z->int_pending = 0;
  m->s.latch = 0;
  m->s.line = 0;
}

EXPORT pm *pm_new(const uint8_t *rom16k, int32_t vbl_offset) {
  pm *m = (pm *)calloc(1, sizeof(pm));
  memcpy(m->rom, rom16k, 0x4000);
  m->vbl_offset = vbl_offset;
  memset(m->s.ram + 0x800, 0xBF, 0x400); /* so a RAM dump shows the unmapped area as MAME reads it */
  m->s.in0 = m->s.in1 = 0xFF;
  m->in0 = m->in1 = 0xFF;
  m->joy = -1;
  m->s.dsw1 = 0xC9; /* MAME defaults: 1 coin 1 credit, 3 lives, bonus at 10000, normal, normal names */
  m->s.dsw2 = 0xFF;
  cpu_power_on(m);
  m->s.cpu.cyc = 0;
  m->s.frame_end = CYC_FRAME;
  m->s.vblank = (uint32_t)(CYC_FRAME + vbl_offset);
  return m;
}

EXPORT void pm_free(pm *m) { free(m); }

EXPORT void pm_set_inputs(pm *m, int in0, int in1) {
  m->s.in0 = (uint8_t)in0;
  m->s.in1 = (uint8_t)in1;
}

/* IN0 joystick bits (active low): up 0, left 1, right 2, down 3 */
static const uint8_t JOYBIT[4] = { 0x04, 0x08, 0x02, 0x01 }; /* R D L U */
static void apply_inputs(pm *m) {
  uint8_t v = m->in0;
  if (m->joy >= 0) v &= (uint8_t)~JOYBIT[m->joy];
  m->s.in0 = v;
  m->s.in1 = m->in1;
}
/* pm_joy/pm_buttons act like MAME's Lua set_value at a frame end: the next frame still reads the
   old inputs (its interrupt comes right after the frame end), the one after reads the new ones. */
EXPORT void pm_joy(pm *m, int dir) { m->joy = dir; }
EXPORT int pm_get_joy(pm *m) { return m->joy; }
EXPORT void pm_buttons(pm *m, int in0, int in1) { m->in0 = (uint8_t)in0; m->in1 = (uint8_t)in1; }
EXPORT void pm_set_idle(pm *m, int on) { m->idle = on; }

static void vblank(pm *m) {
  if (m->s.latch & 1) m->s.line = 1;
  if (++m->s.watchdog >= 16) { /* MAME's watchdog: 16 vblanks without a write resets the machine */
    m->s.watchdog = 0;
    m->s.resets++;
    cpu_reset(m);
  }
}

/* Run up to the next frame end (where MAME's frame notifier runs). */
EXPORT void pm_frame(pm *m) {
  z80 *z = &m->s.cpu;
  for (;;) {
    uint32_t c = (uint32_t)z->cyc;
    if ((int32_t)(c - m->s.vblank) >= 0) {
      vblank(m);
      m->s.vblank += CYC_FRAME;
    }
    if ((int32_t)(c - m->s.frame_end) >= 0) break;
    /* Idle skip (like mame-patches/idleskip.patch): the main loop at 0x238D (LD HL,(4C82); LD A,(HL);
       AND A; JP M,238D) only spins while its task queue is empty, and only the interrupt changes
       anything, so jump straight to the next event. The ROM never reads R; only the return address
       the interrupt pushes (into stack below SP that nothing reads) can differ from a full run. */
    if (m->idle && z->pc == 0x238D && !m->s.line) {
      uint16_t task = (uint16_t)(m->s.ram[0xC82] | m->s.ram[0xC83] << 8);
      if (task >= 0x4CC0 && task <= 0x4CFF && (m->s.ram[task - 0x4000] & 0x80)) {
        uint32_t ev = ((int32_t)(m->s.vblank - m->s.frame_end) < 0) ? m->s.vblank : m->s.frame_end;
        if ((int32_t)(ev - c) > 0) z->cyc = ev;
        continue;
      }
    }
    z->int_pending = m->s.line;
    z->int_data = m->s.vector;
    m->edge_n = 0;
    m->edge_on = 1;
    z80_step(z);
    m->edge_on = 0;
    if ((int32_t)((uint32_t)z->cyc - m->s.frame_end) <= 0) m->edge_n = 0; /* ended by the frame end: not crossing */
  }
  m->s.frame_end += CYC_FRAME;
  m->s.frames++;
  apply_inputs(m);
}

EXPORT uint8_t *pm_ram(pm *m) { return m->s.ram; }
EXPORT int pm_state_size(void) { return (int)sizeof(pm_state); }
EXPORT void pm_save(pm *m, void *buf) { memcpy(buf, &m->s, sizeof(pm_state)); }
EXPORT void pm_load(pm *m, const void *buf) { memcpy(&m->s, buf, sizeof(pm_state)); hook(m); apply_inputs(m); }
EXPORT uint32_t pm_frames(pm *m) { return m->s.frames; }
EXPORT uint32_t pm_resets(pm *m) { return m->s.resets; }
EXPORT int pm_pc(pm *m) { return m->s.cpu.pc; }
/* AF BC DE HL IX IY SP PC */
EXPORT void pm_regs(pm *m, uint16_t *r) {
  z80 *z = &m->s.cpu;
  uint8_t f = (uint8_t)(z->sf << 7 | z->zf << 6 | z->yf << 5 | z->hf << 4 | z->xf << 3 | z->pf << 2 | z->nf << 1 | z->cf);
  r[0] = (uint16_t)(z->a << 8 | f); r[1] = (uint16_t)(z->b << 8 | z->c); r[2] = (uint16_t)(z->d << 8 | z->e);
  r[3] = (uint16_t)(z->h << 8 | z->l); r[4] = z->ix; r[5] = z->iy; r[6] = z->sp; r[7] = z->pc;
}

#include "seg.h"
