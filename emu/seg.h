/* The harness's segment runner (harness/server.lua seg/segb/hash), frame for frame, on pacemu.
 * Included at the end of pacemu.c. server.lua is the reference: keep the two in step.
 *
 * Frame rules taken from MAME + lib.lua:
 * - a joystick change made between frames is what the next frame reads;
 * - a save (msave) stores the machine as it is, then lets one frame run;
 * - a load (mload) sets the joystick, restores the state, then lets one frame run (lib.lua loads
 *   twice, which lands on the same state). */

#define MW 28
#define MH 31
static char maze[MH][MW]; /* 1 = open */

EXPORT void pm_set_maze(const char *rows) { /* MH rows of MW chars, '#' = wall */
  for (int r = 0; r < MH; r++)
    for (int c = 0; c < MW; c++) maze[r][c] = rows[r * MW + c] != '#';
}

static const int DC[4][2] = { { 1, 0 }, { 0, 1 }, { -1, 0 }, { 0, -1 } };

static int mopen(int c, int r) {
  if (r < 0 || r >= MH) return 0;
  if (c < 0 || c >= MW) return r == 14; /* tunnel */
  return maze[r][c];
}

static int is_node(int c, int r) {
  if (c < 0 || c >= MW || !mopen(c, r)) return 0;
  int n = 0, ex[4];
  for (int d = 0; d < 4; d++) { ex[d] = mopen(c + DC[d][0], r + DC[d][1]); n += ex[d]; }
  if (n >= 3) return 1;
  return n == 2 && !((ex[0] && ex[2]) || (ex[1] && ex[3]));
}

static int wrapc(int c) { return (((c + 2) % 32) + 32) % 32 - 2; }

#define RD(a) (m->s.ram[(a) - 0x4000])
static int pac_c(pm *m) { return 59 - RD(0x4D3A); }
static int pac_r(pm *m) { return RD(0x4D39) - 33; }

static int dist_to(pm *m, int c, int r, int d) {
  int x = RD(0x4D09), y = RD(0x4D08);
  int cx = (29 - c) * 8 + 4, cy = (r + 1) * 8 + 4;
  if (d == 1) return cy - y;
  if (d == 3) return y - cy;
  int v = ((d == 2) ? (cx - x) : (x - cx));
  v = ((v % 256) + 256) % 256;
  if (v > 248) v -= 256;
  return v;
}

static int ghost_min_dist(pm *m) {
  int x = RD(0x4D09), y = RD(0x4D08), best = 999;
  for (int g = 0; g < 4; g++) {
    int gy = RD(0x4D00 + g * 2), gx = RD(0x4D01 + g * 2);
    int dd = abs(gx - x) + abs(gy - y);
    if (dd < best) best = dd;
  }
  return best;
}

static int bcd(int v) { return (v >> 4) * 10 + (v & 15); }
static int score(pm *m) { return bcd(RD(0x4E80)) + bcd(RD(0x4E81)) * 100 + bcd(RD(0x4E82)) * 10000; }
static int fruit_points(int d) {
  return d == 100 || d == 300 || d == 500 || d == 700 || d == 1000 || d == 2000 || d == 3000 || d == 5000;
}

typedef struct {
  int want, pol_e, policy, lag, nxt, nxt_delay, d, mc, mr;
  int n, pressed, trigger, entered, mind, lastx, lasty, still, win, fruits, last_score, lead_at;
} seg_t;

#define NONE (-100000)

/* 0 if there is no node ahead */
static int seg_start(pm *m, seg_t *g, int want, int pol_e, int policy, int lag, int nxt, int nxt_delay) {
  int d = RD(0x4D30) & 3;
  int mc = pac_c(m), mr = pac_r(m), guard = 0;
  while (!is_node(mc, mr)) {
    mc = wrapc(mc + DC[d][0]); mr += DC[d][1];
    if (++guard > 40) return 0;
  }
  if (!pol_e && !mopen(mc + DC[d][0], mr + DC[d][1]) && policy < 0) policy = 0;
  memset(g, 0, sizeof *g);
  g->want = want; g->pol_e = pol_e; g->policy = policy; g->lag = lag; g->nxt = nxt; g->nxt_delay = nxt_delay;
  g->d = d; g->mc = mc; g->mr = mr;
  g->trigger = NONE; g->mind = 999; g->lastx = g->lasty = -1;
  g->win = (want == d) ? 99 : NONE;
  g->last_score = score(m); g->lead_at = NONE;
  return 1;
}

static void seg_before(pm *m, seg_t *g) {
  if (g->win == NONE && dist_to(m, g->mc, g->mr, g->d) <= 4) g->win = g->n;
  if (!g->pressed) {
    if (g->trigger == NONE && (g->pol_e || dist_to(m, g->mc, g->mr, g->d) <= g->policy)) g->trigger = g->n;
    if (g->trigger != NONE && g->n - g->trigger >= g->lag) { pm_joy(m, g->want); g->pressed = 1; }
  }
  if (g->pressed && g->lead_at == NONE && g->want != g->d && RD(0x4D30) == g->want) g->lead_at = g->n;
  if (g->nxt >= 0 && g->lead_at != NONE && g->n - g->lead_at == g->nxt_delay) { pm_joy(m, g->nxt); g->nxt = -1; }
}

enum { ST_NONE, ST_OK, ST_CLEAR, ST_DEAD, ST_MISS, ST_STUCK, ST_TIMEOUT, ST_NONODE };

static int seg_after(pm *m, seg_t *g) {
  g->n++;
  int s = score(m);
  if (fruit_points(s - g->last_score)) g->fruits++;
  g->last_score = s;
  if (RD(0x4DA5) != 0) return ST_DEAD;
  if (RD(0x4E0E) >= 244) return ST_CLEAR;
  int md = ghost_min_dist(m);
  if (md < g->mind) g->mind = md;
  int tc = pac_c(m), tr = pac_r(m);
  if (tc == g->mc && tr == g->mr) g->entered = 1;
  else if (g->entered) return RD(0x4D30) == g->want ? ST_OK : ST_MISS;
  int x = RD(0x4D09), y = RD(0x4D08);
  if (x == g->lastx && y == g->lasty) g->still++; else g->still = 0;
  g->lastx = x; g->lasty = y;
  if (g->still > 200) return ST_STUCK;
  if (g->n > 3600) return ST_TIMEOUT;
  return ST_NONE;
}

static int fruits_gone(pm *m) {
  int n = (RD(0x4E0C) != 0) + (RD(0x4E0D) != 0);
  if (RD(0x4DD2) != 0 || RD(0x4DD3) != 0) n--;
  return n;
}

/* seg reply fields: st fr mc mr mind dots tc tr win fruits lead gone */
static void seg_out(pm *m, seg_t *g, int st, int32_t *o) {
  o[0] = st; o[1] = g->n; o[2] = g->mc; o[3] = g->mr; o[4] = g->mind; o[5] = RD(0x4E0E);
  o[6] = pac_c(m); o[7] = pac_r(m); o[8] = g->win == NONE ? 0 : g->win; o[9] = g->fruits;
  o[10] = g->lead_at == NONE ? 0 : g->n - g->lead_at; o[11] = fruits_gone(m);
}

/* run until the segment ends; with fork, return ST_NONE when the press is triggered but not made */
static int seg_run(pm *m, seg_t *g, int fork) {
  for (;;) {
    seg_before(m, g);
    if (fork && g->trigger != NONE && !g->pressed) return ST_NONE;
    pm_frame(m);
    int st = seg_after(m, g);
    if (st) return st;
  }
}

/* "seg": pol_e = policy "E"; nxt = -1 for none */
EXPORT void pm_seg(pm *m, int want, int pol_e, int policy, int lag, int nxt, int nxt_delay, int32_t *o) {
  seg_t g;
  if (!seg_start(m, &g, want, pol_e, policy, lag, nxt, nxt_delay)) {
    int32_t z[12] = { ST_NONODE, 0, 0, 0, 999, 0, 0, 0, 0, 0, 0, 0 };
    memcpy(o, z, sizeof z); return;
  }
  seg_out(m, &g, seg_run(m, &g, 0), o);
}

/* server.lua ram_hash: 0x4000-0x4F7F and 0x4FC0-0x4FEF, padded with NULs to 64 bytes, as
   little-endian int64s, h = h*31 + v wrapping, then floored mod 2147483647 */
EXPORT int64_t pm_hash(pm *m) {
  uint8_t buf[4032];
  memcpy(buf, m->s.ram, 0xF80);
  memcpy(buf + 0xF80, m->s.ram + 0xFC0, 0x30);
  memset(buf + 0xFB0, 0, sizeof buf - 0xFB0);
  uint64_t h = 0;
  for (int i = 0; i < (int)sizeof buf; i += 8) {
    uint64_t v; memcpy(&v, buf + i, 8);
    h = h * 31u + v;
  }
  int64_t r = (int64_t)h % 2147483647;
  if (r < 0) r += 2147483647;
  return r;
}

static void msave(pm *m, uint8_t *slot) { memcpy(slot, &m->s, sizeof(pm_state)); pm_frame(m); }
static void mload(pm *m, const uint8_t *slot, int held) {
  pm_joy(m, held); memcpy(&m->s, slot, sizeof(pm_state)); hook(m); apply_inputs(m); pm_frame(m);
}

/* "segb want policy name1..nameK": o gets 13 ints per k (seg fields + hash), slots K saved states */
EXPORT void pm_segb(pm *m, int want, int policy, int K, int32_t *o, int64_t *hashes, uint8_t *slots) {
  int held = m->joy;
  seg_t g, fork;
  size_t S = sizeof(pm_state);
  if (!seg_start(m, &g, want, 0, policy, 1, -1, 0)) {
    for (int k = 0; k < K; k++) {
      int32_t z[12] = { ST_NONODE, 0, 0, 0, 999, 0, 0, 0, 0, 0, 0, 0 };
      memcpy(o + 12 * k, z, sizeof z); hashes[k] = 0;
    }
    return;
  }
  int st = seg_run(m, &g, 1);
  if (st) { /* ended before the press point */
    int32_t line[12]; seg_out(m, &g, st, line);
    int64_t h = pm_hash(m);
    for (int k = 0; k < K; k++) { memcpy(o + 12 * k, line, sizeof line); hashes[k] = h; msave(m, slots + S * k); }
    return;
  }
  fork = g;
  uint8_t *fs = (uint8_t *)malloc(S);
  msave(m, fs);
  for (int k = 0; k < K; k++) {
    if (k > 0) mload(m, fs, held);
    g = fork;
    g.lag = k + 1;
    st = seg_after(m, &g);
    if (!st) st = seg_run(m, &g, 0);
    seg_out(m, &g, st, o + 12 * k);
    hashes[k] = pm_hash(m);
    msave(m, slots + S * k);
  }
  free(fs);
}

/* frames until the level is reached (server.lua to_level), poking the dot counter */
EXPORT void pm_to_level(pm *m, int n) {
  while (RD(0x4E13) + 1 < n) {
    int lv = RD(0x4E13);
    RD(0x4E0E) = 244;
    while (!(RD(0x4E13) == lv + 1 && RD(0x4E04) == 3)) pm_frame(m);
  }
}
