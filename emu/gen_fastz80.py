"""Generates fastz80.h: pacemu's fast Z80 loop.

The registers live in locals (so the compiler keeps them in CPU registers) and F is one byte with
lookup tables, instead of z80.c's struct fields and bitfield flags. The behaviour is z80.c's exactly,
undocumented flags, WZ and cycle counts included; opcodes Pac-Man doesn't use (HALT, I/O block ops,
odd DD/FD forms) fall back to z80.c for that one instruction.

Run: python gen_fastz80.py   (writes fastz80.h next to it)"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def table(name):
    src = open(os.path.join(HERE, 'z80.c')).read()
    body = re.search(r'%s\[256\] = \{(.*?)\};' % name, src, re.S).group(1)
    t = [int(x) for x in body.replace('\n', ' ').split(',')]
    assert len(t) == 256
    return t


CYC00, CYCED, CYCDD = table('cyc_00'), table('cyc_ed'), table('cyc_ddfd')

# 8-bit registers: get expression and setter
PAIR = {'B': 'bc', 'C': 'bc', 'D': 'de', 'E': 'de', 'H': 'hl', 'L': 'hl', 'IXH': 'ix', 'IXL': 'ix', 'IYH': 'iy', 'IYL': 'iy'}
HIGH = {'B', 'D', 'H', 'IXH', 'IYH'}


def G(r):
    if r == 'A':
        return 'a'
    return '(uint8_t)(%s >> 8)' % PAIR[r] if r in HIGH else '(uint8_t)%s' % PAIR[r]


def S(r, v):
    if r == 'A':
        return 'a = (uint8_t)(%s);' % v
    p = PAIR[r]
    if r in HIGH:
        return '%s = (uint16_t)((%s & 0x00FF) | (uint8_t)(%s) << 8);' % (p, p, v)
    return '%s = (uint16_t)((%s & 0xFF00) | (uint8_t)(%s));' % (p, p, v)


R8 = ['B', 'C', 'D', 'E', 'H', 'L', 'M', 'A']
RR = ['bc', 'de', 'hl', 'sp']
CC = ['!(f & F_Z)', '(f & F_Z)', '!(f & F_C)', '(f & F_C)', '!(f & F_P)', '(f & F_P)', '!(f & F_S)', '(f & F_S)']
ROT = ['rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', 'sll', 'srl']


def alu(k, v):
    return [
        'fz_add(&a, &f, %s, 0);', 'fz_add(&a, &f, %s, f & F_C);', 'fz_sub(&a, &f, %s, 0);', 'fz_sub(&a, &f, %s, f & F_C);',
        'a &= %s; f = (uint8_t)(SZP[a] | F_H);', 'a ^= %s; f = SZP[a];', 'a |= %s; f = SZP[a];', 'fz_cp(a, &f, %s);',
    ][k] % v


def main_cases():
    c = {}
    c[0x00] = ''
    for i, rr in enumerate(RR):
        c[0x01 + 16 * i] = '%s = FW();' % rr
        c[0x03 + 16 * i] = '%s++;' % rr
        c[0x0B + 16 * i] = '%s--;' % rr
        c[0x09 + 16 * i] = 'fz_addw(&hl, &f, &wz, %s);' % rr
    for i, r in enumerate(R8):
        if r == 'M':
            c[0x04 + 8 * i] = '{ uint8_t v = fz_inc(RD(hl), &f); WR(hl, v); }'
            c[0x05 + 8 * i] = '{ uint8_t v = fz_dec(RD(hl), &f); WR(hl, v); }'
            c[0x06 + 8 * i] = '{ uint8_t v = FB(); WR(hl, v); }'
        else:
            c[0x04 + 8 * i] = S(r, 'fz_inc(%s, &f)' % G(r))
            c[0x05 + 8 * i] = S(r, 'fz_dec(%s, &f)' % G(r))
            c[0x06 + 8 * i] = S(r, 'FB()')
    c[0x02] = 'WR(bc, a); wz = (uint16_t)(a << 8 | ((bc + 1) & 0xFF));'
    c[0x12] = 'WR(de, a); wz = (uint16_t)(a << 8 | ((de + 1) & 0xFF));'
    c[0x0A] = 'a = RD(bc); wz = (uint16_t)(bc + 1);'
    c[0x1A] = 'a = RD(de); wz = (uint16_t)(de + 1);'
    keep = '(f & (F_S | F_Z | F_P))'
    c[0x07] = '{ uint8_t cy = a >> 7; a = (uint8_t)(a << 1 | cy); f = (uint8_t)(%s | (a & (F_X | F_Y)) | cy); }' % keep
    c[0x0F] = '{ uint8_t cy = a & 1; a = (uint8_t)(a >> 1 | cy << 7); f = (uint8_t)(%s | (a & (F_X | F_Y)) | cy); }' % keep
    c[0x17] = '{ uint8_t cy = a >> 7; a = (uint8_t)(a << 1 | (f & F_C)); f = (uint8_t)(%s | (a & (F_X | F_Y)) | cy); }' % keep
    c[0x1F] = '{ uint8_t cy = a & 1; a = (uint8_t)(a >> 1 | (f & F_C) << 7); f = (uint8_t)(%s | (a & (F_X | F_Y)) | cy); }' % keep
    c[0x08] = '{ uint8_t t = z->a_; z->a_ = a; a = t; t = z->f_; z->f_ = f; f = t; }'
    c[0x10] = '{ int8_t d = (int8_t)FB(); bc = (uint16_t)(bc - 0x100); if (bc >> 8) { pc = (uint16_t)(pc + d); wz = pc; cyc += 5; } }'
    c[0x18] = '{ int8_t d = (int8_t)FB(); pc = (uint16_t)(pc + d); }'
    for i in range(4):
        c[0x20 + 8 * i] = '{ int8_t d = (int8_t)FB(); if (%s) { pc = (uint16_t)(pc + d); wz = pc; cyc += 5; } }' % CC[i]
    c[0x22] = '{ uint16_t ad = FW(); WW(ad, hl); wz = (uint16_t)(ad + 1); }'
    c[0x2A] = '{ uint16_t ad = FW(); hl = RW(ad); wz = (uint16_t)(ad + 1); }'
    c[0x27] = 'fz_daa(&a, &f);'
    c[0x2F] = 'a = (uint8_t)~a; f = (uint8_t)((f & (F_S | F_Z | F_P | F_C)) | F_H | F_N | (a & (F_X | F_Y)));'
    c[0x37] = 'f = (uint8_t)(%s | F_C | (a & (F_X | F_Y)));' % keep
    c[0x3F] = 'f = (uint8_t)(%s | (f & F_C) << 4 | ((f & F_C) ^ F_C) | (a & (F_X | F_Y)));' % keep
    c[0x32] = '{ uint16_t ad = FW(); WR(ad, a); wz = (uint16_t)(a << 8 | ((ad + 1) & 0xFF)); }'
    c[0x3A] = '{ uint16_t ad = FW(); a = RD(ad); wz = (uint16_t)(ad + 1); }'
    for op in range(0x40, 0x80):
        if op == 0x76:
            continue  # halt: fallback
        d, s = R8[(op >> 3) & 7], R8[op & 7]
        if s == 'M':
            c[op] = S(d, 'RD(hl)')
        elif d == 'M':
            c[op] = 'WR(hl, %s);' % G(s)
        else:
            c[op] = '' if d == s else S(d, G(s))
    for op in range(0x80, 0xC0):
        s = R8[op & 7]
        c[op] = alu((op >> 3) & 7, 'RD(hl)' if s == 'M' else G(s))
    for k in range(8):
        c[0xC6 + 8 * k] = alu(k, 'FB()')
        c[0xC0 + 8 * k] = 'if (%s) { pc = RW(sp); sp += 2; wz = pc; cyc += 6; }' % CC[k]
        c[0xC2 + 8 * k] = '{ uint16_t ad = FW(); if (%s) pc = ad; wz = ad; }' % CC[k]
        c[0xC4 + 8 * k] = '{ uint16_t ad = FW(); if (%s) { PUSH(pc); pc = ad; cyc += 7; } wz = ad; }' % CC[k]
        c[0xC7 + 8 * k] = 'PUSH(pc); pc = wz = 0x%02X;' % (8 * k)
    for i, rr in enumerate(['bc', 'de', 'hl']):
        c[0xC1 + 16 * i] = '%s = RW(sp); sp += 2;' % rr
        c[0xC5 + 16 * i] = 'PUSH(%s);' % rr
    c[0xF1] = '{ uint16_t v = RW(sp); sp += 2; a = (uint8_t)(v >> 8); f = (uint8_t)v; }'
    c[0xF5] = 'PUSH((uint16_t)(a << 8 | f));'
    c[0xC3] = 'pc = FW(); wz = pc;'
    c[0xC9] = 'pc = RW(sp); sp += 2; wz = pc;'
    c[0xCD] = '{ uint16_t ad = FW(); PUSH(pc); pc = ad; wz = ad; }'
    c[0xD3] = '{ uint8_t p = FB(); if (p == 0) m->s.vector = a; wz = (uint16_t)((p + 1) | a << 8); }'
    c[0xDB] = '(void)FB(); wz = (uint16_t)(a << 8 | 0x100); a = 0xFF;'
    c[0xD9] = ('{ uint16_t t = bc; bc = (uint16_t)(z->b_ << 8 | z->c_); z->b_ = (uint8_t)(t >> 8); z->c_ = (uint8_t)t;'
               ' t = de; de = (uint16_t)(z->d_ << 8 | z->e_); z->d_ = (uint8_t)(t >> 8); z->e_ = (uint8_t)t;'
               ' t = hl; hl = (uint16_t)(z->h_ << 8 | z->l_); z->h_ = (uint8_t)(t >> 8); z->l_ = (uint8_t)t; }')
    c[0xE3] = '{ uint16_t v = RW(sp); WW(sp, hl); hl = v; wz = v; }'
    c[0xE9] = 'pc = hl;'
    c[0xEB] = '{ uint16_t t = de; de = hl; hl = t; }'
    c[0xF3] = 'z->iff1 = 0; z->iff2 = 0;'
    c[0xFB] = 'z->iff_delay = 1; pend = 1;'
    c[0xF9] = 'sp = hl;'
    return c


def cb_cases():
    c = {}
    for op in range(256):
        x, y, r = op >> 6, (op >> 3) & 7, R8[op & 7]
        if x == 0:
            c[op] = ('{ uint8_t v = fz_%s(RD(hl), &f); WR(hl, v); cyc += 7; }' % ROT[y]) if r == 'M' else S(r, 'fz_%s(%s, &f)' % (ROT[y], G(r)))
        elif x == 1:
            c[op] = ('fz_bit(RD(hl), %d, (uint8_t)(wz >> 8), &f); cyc += 4;' % y) if r == 'M' else 'fz_bit(%s, %d, %s, &f);' % (G(r), y, G(r))
        else:
            e = ('& 0x%02X' % (0xFF ^ (1 << y))) if x == 2 else ('| 0x%02X' % (1 << y))
            c[op] = ('{ uint8_t v = (uint8_t)(RD(hl) %s); WR(hl, v); cyc += 7; }' % e) if r == 'M' else S(r, '%s %s' % (G(r), e))
    return c


def ed_cases():
    c = {}
    for i, rr in enumerate(RR):
        c[0x42 + 16 * i] = 'fz_sbcw(&hl, &f, &wz, %s);' % rr
        c[0x4A + 16 * i] = 'fz_adcw(&hl, &f, &wz, %s);' % rr
        c[0x43 + 16 * i] = '{ uint16_t ad = FW(); WW(ad, %s); wz = (uint16_t)(ad + 1); }' % rr
        c[0x4B + 16 * i] = '{ uint16_t ad = FW(); %s = RW(ad); wz = (uint16_t)(ad + 1); }' % rr
    for op in (0x44, 0x54, 0x64, 0x74, 0x4C, 0x5C, 0x6C, 0x7C):
        c[op] = '{ uint8_t t = a; a = 0; fz_sub(&a, &f, t, 0); }'
    for op, mode in ((0x46, 0), (0x66, 0), (0x56, 1), (0x76, 1), (0x5E, 2), (0x7E, 2)):
        c[op] = 'z->interrupt_mode = %d;' % mode
    c[0x47] = 'z->i = a;'
    c[0x4F] = 'r7 = a & 0x80; rc = a;'
    c[0x57] = 'a = z->i; f = (uint8_t)((f & (F_C | F_X | F_Y)) | (a & F_S) | (a ? 0 : F_Z) | (z->iff2 ? F_P : 0));'
    c[0x5F] = 'a = (uint8_t)(r7 | (rc & 0x7F)); f = (uint8_t)((f & (F_C | F_X | F_Y)) | (a & F_S) | (a ? 0 : F_Z) | (z->iff2 ? F_P : 0));'
    for op in (0x45, 0x55, 0x5D, 0x65, 0x6D, 0x75, 0x7D):
        c[op] = 'z->iff1 = z->iff2; pc = RW(sp); sp += 2; wz = pc;'
    c[0x4D] = 'pc = RW(sp); sp += 2; wz = pc;'
    c[0x67] = ('{ uint8_t v = RD(hl); uint8_t na = (uint8_t)((a & 0xF0) | (v & 0x0F)); WR(hl, (v >> 4) | (a << 4)); a = na;'
               ' f = (uint8_t)((f & F_C) | SZP[a]); wz = (uint16_t)(hl + 1); }')
    c[0x6F] = ('{ uint8_t v = RD(hl); uint8_t na = (uint8_t)((a & 0xF0) | (v >> 4)); WR(hl, (v << 4) | (a & 0x0F)); a = na;'
               ' f = (uint8_t)((f & F_C) | SZP[a]); wz = (uint16_t)(hl + 1); }')
    c[0xA0] = 'fz_ldi(m, &bc, &de, &hl, a, &f, 1, &pend);'
    c[0xA8] = 'fz_ldi(m, &bc, &de, &hl, a, &f, -1, &pend);'
    c[0xB0] = 'fz_ldi(m, &bc, &de, &hl, a, &f, 1, &pend); if (bc) { pc = (uint16_t)(pc - 2); cyc += 5; wz = (uint16_t)(pc + 1); }'
    c[0xB8] = 'fz_ldi(m, &bc, &de, &hl, a, &f, -1, &pend); if (bc) { pc = (uint16_t)(pc - 2); cyc += 5; wz = (uint16_t)(pc + 1); }'
    c[0xA1] = 'fz_cpi(m, &bc, &hl, a, &f); wz++;'
    c[0xB1] = 'fz_cpi(m, &bc, &hl, a, &f); wz++; if (bc && !(f & F_Z)) { pc = (uint16_t)(pc - 2); cyc += 5; wz = (uint16_t)(pc + 1); } else wz++;'
    return c


def ddfd_cases(iz):
    H, L = iz.upper() + 'H', iz.upper() + 'L'
    IZD = 'uint16_t ad = (uint16_t)(%s + (int8_t)FB()); wz = ad;' % iz
    c = {}
    c[0xE1] = '%s = RW(sp); sp += 2;' % iz
    c[0xE5] = 'PUSH(%s);' % iz
    c[0xE9] = 'pc = %s; wz = pc;' % iz
    for i, rr in enumerate(['bc', 'de', iz, 'sp']):
        c[0x09 + 16 * i] = 'fz_addw(&%s, &f, &wz, %s);' % (iz, rr)
    for k in range(8):
        c[0x84 + 8 * k] = alu(k, G(H))
        c[0x85 + 8 * k] = alu(k, G(L))
        c[0x86 + 8 * k] = '{ %s %s }' % (IZD, alu(k, 'RD(ad)'))
    c[0x23] = '%s++;' % iz
    c[0x2B] = '%s--;' % iz
    c[0x34] = '{ %s uint8_t v = fz_inc(RD(ad), &f); WR(ad, v); }' % IZD
    c[0x35] = '{ %s uint8_t v = fz_dec(RD(ad), &f); WR(ad, v); }' % IZD
    c[0x24] = S(H, 'fz_inc(%s, &f)' % G(H))
    c[0x25] = S(H, 'fz_dec(%s, &f)' % G(H))
    c[0x2C] = S(L, 'fz_inc(%s, &f)' % G(L))
    c[0x2D] = S(L, 'fz_dec(%s, &f)' % G(L))
    c[0x2A] = '{ uint16_t ad = FW(); %s = RW(ad); }' % iz
    c[0x22] = '{ uint16_t ad = FW(); WW(ad, %s); }' % iz
    c[0x21] = '%s = FW();' % iz
    c[0x36] = '{ %s uint8_t v = FB(); WR(ad, v); }' % IZD
    for i, r in enumerate(R8):
        if r == 'M':
            continue
        c[0x70 + i] = '{ %s WR(ad, %s); }' % (IZD, G(r))
        c[0x46 + 8 * i] = '{ %s %s }' % (IZD, S(r, 'RD(ad)'))
    for i, r in enumerate(['B', 'C', 'D', 'E']):
        c[0x44 + 8 * i] = S(r, G(H))
        c[0x45 + 8 * i] = S(r, G(L))
        c[0x60 + i] = S(H, G(r))
        c[0x68 + i] = S(L, G(r))
    c[0x7C] = S('A', G(H))
    c[0x7D] = S('A', G(L))
    c[0x67] = S(H, 'a')
    c[0x6F] = S(L, 'a')
    c[0x64] = ''
    c[0x6D] = ''
    c[0x65] = S(H, G(L))
    c[0x6C] = S(L, G(H))
    c[0x26] = S(H, 'FB()')
    c[0x2E] = S(L, 'FB()')
    c[0xF9] = 'sp = %s;' % iz
    c[0xE3] = '{ uint16_t v = RW(sp); WW(sp, %s); %s = v; wz = v; }' % (iz, iz)
    # DD CB d op
    lines = ['{', '  %s uint8_t op3 = FB();' % IZD, '  switch (op3) {']
    for op in range(256):
        x, y, r = op >> 6, (op >> 3) & 7, R8[op & 7]
        if x == 1:
            if op & 7:
                continue
            labels = ' '.join('case 0x%02X:' % (op | j) for j in range(8))
            lines.append('  %s fz_bit(RD(ad), %d, (uint8_t)(ad >> 8), &f); cyc += 20; break;' % (labels, y))
            continue
        if x == 0:
            v = 'fz_%s(RD(ad), &f)' % ROT[y]
        elif x == 2:
            v = '(uint8_t)(RD(ad) & 0x%02X)' % (0xFF ^ (1 << y))
        else:
            v = '(uint8_t)(RD(ad) | 0x%02X)' % (1 << y)
        setr = '' if r == 'M' else ' ' + S(r, 'v')
        lines.append('  case 0x%02X: { uint8_t v = %s;%s WR(ad, v); cyc += 23; } break;' % (op, v, setr))
    lines += ['  }', '}']
    c[0xCB] = '\n'.join(lines)
    return c


def emit_switch(cases, var, cyc, indent, default):
    out = ['%sswitch (%s) {' % (indent, var)]
    for op in sorted(cases):
        body = cases[op]
        cy = cyc[op] if cyc else 0
        pre = ('cyc += %d; ' % cy) if cy else ''
        if '\n' in body:
            out.append('%scase 0x%02X: %s' % (indent, op, pre))
            out += [indent + '  ' + ln for ln in body.split('\n')]
            out.append('%s  break;' % indent)
        else:
            out.append('%scase 0x%02X: %s%s break;' % (indent, op, pre, body))
    out.append('%sdefault: %s' % (indent, default))
    out.append('%s}' % indent)
    return out


def gen():
    main = main_cases()
    sub = {}
    cb = emit_switch(cb_cases(), 'op2', None, '    ', 'break;')
    sub[0xCB] = 'uint8_t op2 = FB(); cyc += 8; rc++;\n' + '\n'.join(x[4:] for x in cb)
    ed = emit_switch(ed_cases(), 'op2', CYCED, '    ', 'FALLBACK(2, %d, 2); break;' % CYC00[0xED])
    sub[0xED] = 'uint8_t op2 = FB(); rc++;\n' + '\n'.join(x[4:] for x in ed)
    for pfx, iz in ((0xDD, 'ix'), (0xFD, 'iy')):
        cs = ddfd_cases(iz)
        sw = emit_switch(cs, 'op2', CYCDD, '    ', 'FALLBACK(2, %d, 2); break;' % CYC00[pfx])
        sub[pfx] = 'uint8_t op2 = FB(); rc++;\n' + '\n'.join(x[4:] for x in sw)
    out = []
    out.append('    switch (op) {')
    for op in range(256):
        cy = CYC00[op]
        pre = ('cyc += %d; ' % cy) if cy else ''
        if op in sub:
            out.append('    case 0x%02X: { %s' % (op, pre))
            out += ['      ' + ln for ln in sub[op].split('\n')]
            out.append('    } break;')
        elif op in main:
            out.append('    case 0x%02X: %s%s break;' % (op, pre, main[op]))
    out.append('    default: FALLBACK(1, 0, 1); break; /* (cyc not yet added) */')
    out.append('    }')
    return '\n'.join(out)


def tables():
    sz = [(v & 0xA8) | (0x40 if v == 0 else 0) for v in range(256)]
    szp = [sz[v] | (4 if bin(v).count('1') % 2 == 0 else 0) for v in range(256)]
    inc = [sz[r] | (0x10 if (r & 0x0F) == 0 else 0) | (4 if r == 0x80 else 0) for r in range(256)]
    dec = [sz[r] | 2 | (0x10 if (r & 0x0F) == 0x0F else 0) | (4 if r == 0x7F else 0) for r in range(256)]

    def arr(name, t):
        rows = [', '.join('0x%02X' % x for x in t[i:i + 16]) for i in range(0, 256, 16)]
        return 'static const uint8_t %s[256] = {\n  %s};' % (name, ',\n  '.join(rows))
    return '\n'.join([arr('SZ', sz), arr('SZP', szp), arr('INCF', inc), arr('DECF', dec)])


HEAD = r'''/* fastz80.h: pacemu's fast Z80 loop. GENERATED by gen_fastz80.py; edit that, not this.
 *
 * Same behaviour as z80.c instruction for instruction (flags, WZ, R, cycles), but the registers are
 * locals and F is one byte, so the compiler keeps them in CPU registers. Included by pacemu.c after
 * z80.c, rd/wr and hook. Opcodes it doesn't have run on z80.c (FALLBACK). */

enum { F_C = 1, F_N = 2, F_P = 4, F_X = 8, F_H = 16, F_Y = 32, F_Z = 64, F_S = 128 };

%(tables)s

static __forceinline uint8_t fz_rd(pm *m, uint16_t a) { uint8_t *p = m->rp[a >> 8]; return p ? p[a & 255] : rd(m, a); }
static __forceinline uint16_t fz_rw(pm *m, uint16_t a) { return (uint16_t)(fz_rd(m, a) | fz_rd(m, (uint16_t)(a + 1)) << 8); }
static __forceinline uint8_t fz_fetch(pm *m, uint16_t a) { return a < 0x4000 ? m->rom[a] : fz_rd(m, a); }
static __forceinline void fz_wr(pm *m, uint16_t a, uint8_t v, unsigned *pend) {
  uint8_t *p = m->wp[a >> 8];
  if (p) p[a & 255] = v; else { wr(m, a, v); *pend = 1; } /* I/O can lower the IRQ line */
}
#define RD(a) fz_rd(m, (uint16_t)(a))
#define RW(a) fz_rw(m, (uint16_t)(a))
#define WR(a, v) fz_wr(m, (uint16_t)(a), (uint8_t)(v), &pend)
#define WW(a, v) do { uint16_t wa_ = (uint16_t)(a), wv_ = (uint16_t)(v); WR(wa_, wv_ & 0xFF); WR(wa_ + 1, wv_ >> 8); } while (0)
#define FB() fz_fetch(m, pc++)
#define FW() (pc += 2, (uint16_t)(fz_fetch(m, (uint16_t)(pc - 2)) | fz_fetch(m, (uint16_t)(pc - 1)) << 8))
#define PUSH(v) do { uint16_t pv_ = (uint16_t)(v); sp -= 2; WW(sp, pv_); } while (0)

static __forceinline void fz_add(uint8_t *a, uint8_t *f, uint8_t v, unsigned c) {
  unsigned r = *a + v + c;
  *f = (uint8_t)(SZ[r & 255] | ((*a ^ v ^ r) & F_H) | (((*a ^ r) & (v ^ r) & 0x80) >> 5) | ((r >> 8) & 1));
  *a = (uint8_t)r;
}
static __forceinline void fz_sub(uint8_t *a, uint8_t *f, uint8_t v, unsigned c) {
  unsigned r = *a - v - c;
  *f = (uint8_t)(SZ[r & 255] | ((*a ^ v ^ r) & F_H) | (((*a ^ v) & (*a ^ r) & 0x80) >> 5) | ((r >> 8) & 1) | F_N);
  *a = (uint8_t)r;
}
static __forceinline void fz_cp(uint8_t a, uint8_t *f, uint8_t v) { /* like sub, but X/Y come from the operand */
  unsigned r = a - v;
  *f = (uint8_t)((SZ[r & 255] & ~(F_X | F_Y)) | (v & (F_X | F_Y)) | ((a ^ v ^ r) & F_H) | (((a ^ v) & (a ^ r) & 0x80) >> 5) | ((r >> 8) & 1) | F_N);
}
static __forceinline uint8_t fz_inc(uint8_t v, uint8_t *f) { v++; *f = (uint8_t)((*f & F_C) | INCF[v]); return v; }
static __forceinline uint8_t fz_dec(uint8_t v, uint8_t *f) { v--; *f = (uint8_t)((*f & F_C) | DECF[v]); return v; }
static __forceinline void fz_addw(uint16_t *r, uint8_t *f, uint16_t *wz, uint16_t v) {
  unsigned x = *r, s = x + v;
  *f = (uint8_t)((*f & (F_S | F_Z | F_P)) | ((s >> 8) & (F_X | F_Y)) | (((x ^ v ^ s) >> 8) & F_H) | (s >> 16));
  *wz = (uint16_t)(x + 1); *r = (uint16_t)s;
}
static __forceinline void fz_adcw(uint16_t *r, uint8_t *f, uint16_t *wz, uint16_t v) {
  unsigned x = *r, s = x + v + (*f & F_C);
  *f = (uint8_t)(((s >> 8) & (F_S | F_X | F_Y)) | ((s & 0xFFFF) ? 0 : F_Z) | (((x ^ v ^ s) >> 8) & F_H) |
                 (((x ^ s) & (v ^ s) & 0x8000) >> 13) | ((s >> 16) & 1));
  *wz = (uint16_t)(x + 1); *r = (uint16_t)s;
}
static __forceinline void fz_sbcw(uint16_t *r, uint8_t *f, uint16_t *wz, uint16_t v) {
  unsigned x = *r, s = x - v - (*f & F_C);
  *f = (uint8_t)(((s >> 8) & (F_S | F_X | F_Y)) | ((s & 0xFFFF) ? 0 : F_Z) | (((x ^ v ^ s) >> 8) & F_H) |
                 (((x ^ v) & (x ^ s) & 0x8000) >> 13) | ((s >> 16) & 1) | F_N);
  *wz = (uint16_t)(x + 1); *r = (uint16_t)s;
}
static __forceinline void fz_daa(uint8_t *a, uint8_t *f) {
  unsigned corr = 0, cf = *f & F_C, hf = (*f >> 4) & 1, nf = *f & F_N;
  if ((*a & 0x0F) > 9 || hf) corr += 0x06;
  if (*a > 0x99 || cf) { corr += 0x60; cf = 1; }
  if (nf) { hf = hf && (*a & 0x0F) < 6; *a = (uint8_t)(*a - corr); }
  else { hf = (*a & 0x0F) > 9; *a = (uint8_t)(*a + corr); }
  *f = (uint8_t)(SZP[*a] | (hf ? F_H : 0) | nf | cf);
}
static __forceinline uint8_t fz_rlc(uint8_t v, uint8_t *f) { uint8_t c = v >> 7; v = (uint8_t)(v << 1 | c); *f = (uint8_t)(SZP[v] | c); return v; }
static __forceinline uint8_t fz_rrc(uint8_t v, uint8_t *f) { uint8_t c = v & 1; v = (uint8_t)(v >> 1 | c << 7); *f = (uint8_t)(SZP[v] | c); return v; }
static __forceinline uint8_t fz_rl(uint8_t v, uint8_t *f) { uint8_t c = v >> 7; v = (uint8_t)(v << 1 | (*f & F_C)); *f = (uint8_t)(SZP[v] | c); return v; }
static __forceinline uint8_t fz_rr(uint8_t v, uint8_t *f) { uint8_t c = v & 1; v = (uint8_t)(v >> 1 | (*f & F_C) << 7); *f = (uint8_t)(SZP[v] | c); return v; }
static __forceinline uint8_t fz_sla(uint8_t v, uint8_t *f) { uint8_t c = v >> 7; v = (uint8_t)(v << 1); *f = (uint8_t)(SZP[v] | c); return v; }
static __forceinline uint8_t fz_sra(uint8_t v, uint8_t *f) { uint8_t c = v & 1; v = (uint8_t)(v >> 1 | (v & 0x80)); *f = (uint8_t)(SZP[v] | c); return v; }
static __forceinline uint8_t fz_sll(uint8_t v, uint8_t *f) { uint8_t c = v >> 7; v = (uint8_t)(v << 1 | 1); *f = (uint8_t)(SZP[v] | c); return v; }
static __forceinline uint8_t fz_srl(uint8_t v, uint8_t *f) { uint8_t c = v & 1; v = (uint8_t)(v >> 1); *f = (uint8_t)(SZP[v] | c); return v; }
static __forceinline void fz_bit(uint8_t v, int n, uint8_t xy, uint8_t *f) {
  uint8_t res = (uint8_t)(v & (1 << n));
  *f = (uint8_t)((*f & F_C) | F_H | (res & F_S) | (res ? 0 : F_Z | F_P) | (xy & (F_X | F_Y)));
}
static __forceinline void fz_ldi(pm *m, uint16_t *bc, uint16_t *de, uint16_t *hl, uint8_t a, uint8_t *f, int step, unsigned *pend) {
  uint8_t v = fz_rd(m, *hl);
  fz_wr(m, *de, v, pend);
  *hl = (uint16_t)(*hl + step); *de = (uint16_t)(*de + step); (*bc)--;
  unsigned t = v + a;
  *f = (uint8_t)((*f & (F_S | F_Z | F_C)) | (t & F_X) | (t & 0x02) << 4 | (*bc ? F_P : 0));
}
static __forceinline void fz_cpi(pm *m, uint16_t *bc, uint16_t *hl, uint8_t a, uint8_t *f) {
  uint8_t v = fz_rd(m, *hl);
  unsigned r = a - v, hf = (a ^ v ^ r) & F_H;
  (*hl)++; (*bc)--;
  int t = (uint8_t)r - (hf ? 1 : 0);
  *f = (uint8_t)((SZ[r & 255] & (F_S | F_Z)) | hf | F_N | (*f & F_C) | (*bc ? F_P : 0) | (t & F_X) | (t & 0x02) << 4);
}

#define FZ_LOAD() do { \
  a = z->a; f = get_f(z); bc = (uint16_t)(z->b << 8 | z->c); de = (uint16_t)(z->d << 8 | z->e); \
  hl = (uint16_t)(z->h << 8 | z->l); sp = z->sp; pc = z->pc; ix = z->ix; iy = z->iy; wz = z->mem_ptr; \
  cyc = (uint32_t)z->cyc; r7 = z->r & 0x80; rc = z->r; } while (0)
#define FZ_SAVE() do { \
  z->a = a; set_f(z, f); z->b = (uint8_t)(bc >> 8); z->c = (uint8_t)bc; z->d = (uint8_t)(de >> 8); z->e = (uint8_t)de; \
  z->h = (uint8_t)(hl >> 8); z->l = (uint8_t)hl; z->sp = sp; z->pc = pc; z->ix = ix; z->iy = iy; z->mem_ptr = wz; \
  z->cyc = cyc; z->r = (uint8_t)(r7 | (rc & 0x7F)); } while (0)
/* not covered: undo this instruction's fetch, cycles and R, and run it on z80.c */
#ifdef FZ_VERIFY
static uint32_t fz_fallbacks[256][256]; /* [first byte][second byte, for ED/DD/FD] */
#define FZ_COUNT(nb) fz_fallbacks[fz_rd(m, pc)][(nb) > 1 ? fz_rd(m, (uint16_t)(pc + 1)) : 0]++
#else
#define FZ_COUNT(nb) ((void)0)
#endif
#define FALLBACK(nb, cy, rn) do { \
  pc = (uint16_t)(pc - (nb)); cyc -= (cy); rc -= (rn); FZ_COUNT(nb); \
  FZ_SAVE(); exec_opcode(z, nextb(z)); FZ_LOAD(); pend = 1; } while (0)

/* Runs instructions (each preceded by the interrupt check, as pm_frame's loop did) until cyc reaches ev
   or PC reaches the idle loop at 0x238D; with single, exactly one. */
static __forceinline void fz_run(pm *m, uint32_t ev, const int single) {
  z80 *z = &m->s.cpu;
  uint8_t a, f, r7;
  uint16_t bc, de, hl, sp, pc, ix, iy, wz;
  uint32_t cyc;
  unsigned rc, pend;
  FZ_LOAD();
  pend = m->s.line | z->iff_delay | z->nmi_pending | z->halted;
  do {
    if (pend) {
      if (m->s.line | z->iff_delay | z->nmi_pending) {
        z->int_pending = m->s.line;
        z->int_data = m->s.vector;
        if (z->iff_delay) {
          if (--z->iff_delay == 0) z->iff1 = z->iff2 = 1;
        } else if (z->nmi_pending || (z->int_pending && z->iff1 && z->interrupt_mode == 0)) {
          FZ_SAVE(); process_interrupts(z); FZ_LOAD();
        } else if (z->int_pending && z->iff1) {
          uint16_t ad;
          z->int_pending = 0; z->halted = 0; z->iff1 = z->iff2 = 0; rc++;
          if (z->interrupt_mode == 2) { cyc += 19; ad = RW(z->i << 8 | z->int_data); }
          else { cyc += 13; ad = 0x38; }
          PUSH(pc); pc = wz = ad;
        }
      }
      pend = m->s.line | z->iff_delay | z->nmi_pending | z->halted;
      if (z->halted) { cyc += 4; rc++; continue; }
    }
    uint8_t op = FB();
    rc++;
%(switch)s
  } while (!single && (int32_t)(cyc - ev) < 0 && pc != 0x238D);
  FZ_SAVE();
}
'''

if __name__ == '__main__':
    src = HEAD % {'tables': tables(), 'switch': gen()}
    with open(os.path.join(HERE, 'fastz80.h'), 'w', newline='\n') as fh:
        fh.write(src)
    print('wrote fastz80.h, %d lines' % src.count('\n'))
