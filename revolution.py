"""
REVOLUTION — No Electricity. No Mercy.
A 2D stickman combat game based on NBC's Revolution.

Features:
  * Native 720p HD (1280×720); F11 fullscreen; [ / ] master volume; ESC/P pause menu
  * Sword, Bow, Crossbow weapons
  * 6 waves + Monroe Militia Boss fight (3 phases)
  * World campaign map — pick any unlocked sector or Monroe’s citadel, then fight
  * Level checkpoints (auto-saved every 2 waves)
  * Combat feel: sword wind-up / active / recovery, hitstop & screen shake, hitstun, one hit per swing
  * Fight choreography: phased sword poses, combo chain, enemy telegraphs, hit reactions
  * Shadow Fight combat: block / dodge / parry, distinct weapon move sets, enemy archetypes
  * Depth lanes (W axis): FAR / BACK / MID / FORE / NEAR — Q/E step, lane hits, W ghosts
  * Time dimension: Grid Stutter slow-mo (hold T / parry), echo strike telegraphs, boss pattern preview
  * Blackout rewind: ring-buffer memory (R), death rescue window, Armory Rewind Cell perk
  * Learnable Monroe boss patterns; hybrid meta (sector tiers + scrap Armory upgrades)
  * Campaign story: play as Ash Trace (ex-Militia scout hunting Mira) — briefings, clears, Monroe taunts
  * Sound effects (procedurally generated, no audio files needed)
  * High score saved to disk (revolution_save.json)
  * Blood particles, fire ambience, animated stickmen
  * Enemy commanders shoot arrows
  * Boss: Sebastian Monroe with charge/slam/shoot AI
  * Cinematic trailer: trailer.html (press T on title screen to open in browser)
"""

import pygame, sys, math, random, os, json, struct, wave, io, webbrowser
from collections import deque
from pathlib import Path

pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()

# ── Constants ──────────────────────────────────────────────────────────────────
# Reference design was 960×560; HD is 1280×720 (16∶9). SX/SY keep timing & proportions.
REF_W, REF_H   = 960, 560
WIDTH, HEIGHT  = 1280, 720
SX             = WIDTH  / REF_W
SY             = HEIGHT / REF_H
FPS            = 60
GRAVITY        = 0.55 * SY
GROUND_Y       = HEIGHT - int(80 * SY)
SAVE_FILE      = "revolution_save.json"
LW             = max(1, round(2 * SY))   # default vector stroke for HD clarity

# ── Depth lanes (W axis) — Phase B discrete 4D combat ──────────────────────────
W_LANE_FAR  = 0
W_LANE_BACK = 1
W_LANE_MID  = 2
W_LANE_FORE = 3
W_LANE_NEAR = 4
W_LANE_COUNT = 5
W_LANE_STEP_CD = 20
W_LANE_LABELS = ("FAR", "BACK", "MID", "FORE", "NEAR")
# Depth-step strike: brief damage mult after Q/E onto a target's lane
W_STEP_STRIKE_MULT = 1.18


def w_depth_scale(w):
    """Near lane = larger on screen; tuned for 5-lane 720p extremes."""
    w = max(W_LANE_FAR, min(W_LANE_NEAR, int(w)))
    t = w / max(1, W_LANE_NEAR)
    return 0.72 + 0.36 * t  # FAR ~0.72 → NEAR ~1.08


def w_ground_y(w):
    """Far lane sits higher (deeper into the field)."""
    w = max(W_LANE_FAR, min(W_LANE_NEAR, int(w)))
    lift = int((W_LANE_NEAR - w) * 9 * SY)  # 4 steps × 9 — readable without crowding sky
    return GROUND_Y - lift


def w_lane_tint(w):
    w = max(W_LANE_FAR, min(W_LANE_NEAR, int(w)))
    t = w / max(1, W_LANE_NEAR)
    return 0.68 + 0.32 * t  # FAR dimmer, NEAR full


def w_lane_gap(a_w, b_w):
    return abs(int(a_w) - int(b_w))


def w_can_hit(attacker_w, target_w, all_lanes=False, max_gap=1):
    if all_lanes:
        return True
    return w_lane_gap(attacker_w, target_w) <= max_gap


def w_melee_all_lanes(style):
    return style == "cleave"

WHITE       = (255, 255, 255)
GROUND_COL  = (42,  34,  24)
GROUND_LINE = (60,  50,  35)
PLAYER_COL  = (220, 210, 190)
ENEMY_COL   = (180,  60,  40)
CMD_COL     = (140,  40, 150)
BOSS_COL    = (220,  30,  20)
SWORD_COL   = (190, 190, 210)
ARROW_COL   = (200, 160,  80)
BOLT_COL    = (160, 220, 160)
BLOOD_COL   = (160,  30,  20)
HUD_COL     = (200, 170, 100)
HUD_DIM     = ( 80,  65,  40)
FIRE_COLS   = [(255,200,0),(255,140,0),(200,60,0),(255,80,0)]
SPARK_COLS  = [(255,255,180),(255,220,80),(220,180,40)]

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("REVOLUTION — Coming Soon (43 Industries)")
clock  = pygame.time.Clock()

def _sys_ui_font(size, bold=True):
    for name in ("Segoe UI Semibold", "Segoe UI", "Calibri", "Franklin Gothic Medium", "Arial"):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f.get_height() > 0:
                return f
        except Exception:
            continue
    return pygame.font.SysFont(None, size, bold=bold)

FONT_TITLE = _sys_ui_font(max(40, int(round(48 * SY))), bold=True)
FONT_BIG   = _sys_ui_font(max(26, int(round(34 * SY))), bold=True)
FONT_MED   = _sys_ui_font(max(17, int(round(21 * SY))), bold=True)
FONT_SMALL = _sys_ui_font(max(12, int(round(14 * SY))), bold=True)
FONT_TINY  = _sys_ui_font(max(11, int(round(12 * SY))), bold=False)

_INTRO_BG_CACHE = None

def _make_intro_background():
    """One-time cinematic backdrop: depth, warm ember glow, subtle vignette."""
    base = pygame.Surface((WIDTH, HEIGHT))
    base.fill((6, 5, 10))
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    # Floor ember pool
    pygame.draw.ellipse(
        glow, (140, 45, 25, 100),
        (int(-80 * SX), int(HEIGHT - 280 * SY), int(WIDTH + 160 * SX), int(360 * SY)),
    )
    pygame.draw.ellipse(
        glow, (80, 35, 60, 55),
        (int(WIDTH * 0.15), int(-120 * SY), int(520 * SX), int(420 * SY)),
    )
    pygame.draw.ellipse(
        glow, (212, 160, 70, 28),
        (int(WIDTH // 2 - 200 * SX), int(40 * SY), int(400 * SX), int(200 * SY)),
    )
    base.blit(glow, (0, 0))
    vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    c = (0, 0, 0, 115)
    ww, hh = WIDTH, HEIGHT
    pygame.draw.polygon(vig, c, [(0, 0), (int(ww * 0.55), 0), (0, int(hh * 0.5))])
    pygame.draw.polygon(vig, c, [(ww, 0), (int(ww * 0.45), 0), (ww, int(hh * 0.5))])
    pygame.draw.polygon(vig, c, [(0, hh), (int(ww * 0.55), hh), (0, int(hh * 0.5))])
    pygame.draw.polygon(vig, c, [(ww, hh), (int(ww * 0.45), hh), (ww, int(hh * 0.5))])
    base.blit(vig, (0, 0))
    return base

def _blit_shadow_text(surf, font, text, color, center_x, y, off=3, shadow_rgb=(0, 0, 0)):
    s = font.render(text, True, color)
    sh = font.render(text, True, shadow_rgb)
    x = center_x - s.get_width() // 2
    surf.blit(sh, (x + off, y + off))
    surf.blit(s, (x, y))
    return s.get_height()

# ── Procedural Sound ───────────────────────────────────────────────────────────
def _make_sound(samples):
    data = bytes(struct.pack('<' + 'h'*len(samples),
                 *[max(-32767, min(32767, int(s*32767))) for s in samples]))
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100)
        wf.writeframes(data)
    buf.seek(0)
    return pygame.mixer.Sound(buf)

def _swing():
    n=int(44100*0.18)
    return [math.sin(2*math.pi*t/n*800*(1-t/n))*(1-t/n)*0.6+random.uniform(-.05,.05) for t in range(n)]

def _hit():
    n=int(44100*0.11)
    out=[]
    for t in range(n):
        thump=math.sin(2*math.pi*t/n*140)*math.exp(-t/(n*0.12))*0.55
        crack=random.uniform(-1,1)*math.exp(-t/(n*0.18))*0.65
        out.append(thump+crack)
    return out

def _arrow():
    n=int(44100*0.10)
    return [math.sin(2*math.pi*t/n*200)*math.exp(-t/(n*0.3))*0.4+random.uniform(-.03,.03) for t in range(n)]

def _roar():
    n=int(44100*0.5)
    return [math.sin(2*math.pi*t/44100*(80+40*math.sin(t/1000)))*math.exp(-t/(n*0.7))*0.9 for t in range(n)]

def _death():
    n=int(44100*0.3)
    return [random.uniform(-1,1)*math.exp(-t/(n*0.25))*0.7 for t in range(n)]

def _checkpoint():
    out=[]
    for f in [440,550,660,880]:
        seg=int(44100*0.08)
        out+=[math.sin(2*math.pi*i/44100*f)*(1-i/seg)*0.5 for i in range(seg)]
    return out

def _wave_clear():
    n=int(44100*0.4)
    return [math.sin(2*math.pi*t/44100*(440+220*t/n))*(1-t/n)*0.5 for t in range(n)]

def _block_snd():
    n=int(44100*0.08)
    return [math.sin(2*math.pi*t/n*320)*math.exp(-t/(n*0.2))*0.5+random.uniform(-.04,.04) for t in range(n)]

def _dodge_snd():
    n=int(44100*0.06)
    return [math.sin(2*math.pi*t/n*(600-t/n*400))*math.exp(-t/(n*0.3))*0.35 for t in range(n)]

def _parry_snd():
    n=int(44100*0.09)
    return [math.sin(2*math.pi*t/n*880)*math.exp(-t/(n*0.15))*0.55+math.sin(2*math.pi*t/n*440)*0.2 for t in range(n)]

SFX = {}
SFX_BASE_VOLUME = {}
MASTER_VOLUME = 1.0

def _apply_all_sfx_volumes():
    for name, base in SFX_BASE_VOLUME.items():
        if name in SFX:
            try: SFX[name].set_volume(max(0, min(1, base * MASTER_VOLUME)))
            except Exception: pass

def set_master_volume(v):
    global MASTER_VOLUME
    MASTER_VOLUME = max(0.0, min(1.0, float(v)))
    _apply_all_sfx_volumes()

def load_sounds():
    try:
        def _reg(key, snd, base):
            SFX[key] = snd
            SFX_BASE_VOLUME[key] = base
        _reg('swing',     _make_sound(_swing()),     0.4)
        _reg('hit',       _make_sound(_hit()),       0.58)
        _reg('arrow',     _make_sound(_arrow()),     0.35)
        _reg('bolt',      _make_sound(_arrow()),     0.45)
        _reg('boss_roar', _make_sound(_roar()),      0.7)
        _reg('death',     _make_sound(_death()),     0.4)
        _reg('checkpoint',_make_sound(_checkpoint()),0.5)
        _reg('wave_clear',_make_sound(_wave_clear()),0.5)
        _reg('block',     _make_sound(_block_snd()),    0.45)
        _reg('dodge',     _make_sound(_dodge_snd()),    0.35)
        _reg('parry',     _make_sound(_parry_snd()),    0.55)
        _apply_all_sfx_volumes()
    except Exception:
        pass

def play(name):
    if name in SFX:
        try:
            b = SFX_BASE_VOLUME.get(name, 1.0)
            SFX[name].set_volume(max(0, min(1, b * MASTER_VOLUME)))
            SFX[name].play()
        except Exception: pass

# ── Combat juice (Shadow Fight–style weight: hitstop, shake, commitment) ───────
COMBAT_HITSTOP = 0
COMBAT_SHAKE_FRAMES = 0
COMBAT_SHAKE_MAG = 0
TIME_SLOW_FRAMES = 0
TIME_SLOW_SCALE = 0.35
TIME_SIM_ACCUM = 0.0

TIME_SPEC = {
    "slow_scale": 0.35,
    "parry_slow_frames": 42,
    "hold_extend_frames": 3,
    "meter_drain": 0.55,
    "meter_regen": 0.22,
    "meter_max": 100.0,
    "echo_lead_frames": 22,
    "echo_flash_frames": 28,
    "boss_echo_frames": 36,
}

REWIND_SPEC = {
    "buffer_frames": 90,
    "rewind_frames": 90,
    "flash_frames": 15,
    "death_window": 60,
    "charges_base": 1,
    "perk_charge_bonus": 1,
}

REWIND_FLASH_FRAMES = 0


def combat_freeze(frames=3):
    global COMBAT_HITSTOP
    COMBAT_HITSTOP = max(COMBAT_HITSTOP, int(frames))


def combat_shake(magnitude=6, frames=10):
    global COMBAT_SHAKE_FRAMES, COMBAT_SHAKE_MAG
    COMBAT_SHAKE_FRAMES = max(COMBAT_SHAKE_FRAMES, int(frames))
    COMBAT_SHAKE_MAG = max(COMBAT_SHAKE_MAG, int(magnitude))


def combat_shake_tick():
    global COMBAT_SHAKE_FRAMES, COMBAT_SHAKE_MAG
    if COMBAT_SHAKE_FRAMES > 0:
        COMBAT_SHAKE_FRAMES -= 1
        if COMBAT_SHAKE_FRAMES <= 0:
            COMBAT_SHAKE_MAG = 0


def combat_shake_offset():
    if COMBAT_SHAKE_FRAMES <= 0 or COMBAT_SHAKE_MAG <= 0:
        return 0, 0
    m = max(2, COMBAT_SHAKE_MAG * COMBAT_SHAKE_FRAMES // max(1, COMBAT_SHAKE_FRAMES + 6))
    return random.randint(-m, m), random.randint(-m, m)


def combat_trigger_slowmo(frames=40, scale=None):
    global TIME_SLOW_FRAMES, TIME_SLOW_SCALE
    TIME_SLOW_FRAMES = max(TIME_SLOW_FRAMES, int(frames))
    if scale is not None:
        TIME_SLOW_SCALE = float(scale)


def combat_time_step_ready():
    """Return True when combat simulation should advance this display frame."""
    global TIME_SLOW_FRAMES, TIME_SIM_ACCUM
    if COMBAT_HITSTOP > 0:
        return False
    if TIME_SLOW_FRAMES <= 0:
        TIME_SIM_ACCUM = 0.0
        return True
    TIME_SIM_ACCUM += TIME_SLOW_SCALE
    if TIME_SIM_ACCUM >= 1.0:
        TIME_SIM_ACCUM -= 1.0
        TIME_SLOW_FRAMES -= 1
        return True
    return False


def combat_time_active():
    return TIME_SLOW_FRAMES > 0 or COMBAT_HITSTOP > 0


def _pattern_action_label(spec):
    if spec == "walk":
        return "WALK"
    if spec == "slam":
        return "SLAM"
    if spec == "charge":
        return "CHARGE"
    if spec.startswith("shoot:"):
        return "SHOOT"
    return spec.upper()


def _echo_lead_frames(player=None):
    bonus = getattr(player, "echo_bonus", 0) if player else 0
    return TIME_SPEC["echo_lead_frames"] + bonus


def rewind_flash_tick():
    global REWIND_FLASH_FRAMES
    if REWIND_FLASH_FRAMES > 0:
        REWIND_FLASH_FRAMES -= 1


def _snap_arrow(a):
    return {
        "x": a.x, "y": a.y, "dir": a.dir, "damage": a.damage, "speed": abs(a.vx) / max(SX, 0.001),
        "col": a.col, "tip_col": a.tip_col, "pierce": a.pierce, "max_pierce": a.max_pierce,
        "w": a.w, "hit_count": a.hit_count, "alive": a.alive,
    }


def _restore_arrow(d):
    a = Arrow(d["x"], d["y"], d["dir"], damage=d["damage"], speed=d["speed"],
              col=d["col"], tip_col=d["tip_col"], pierce=d["pierce"],
              max_pierce=d["max_pierce"], lane=d["w"])
    a.hit_count = d.get("hit_count", 0)
    a.alive = d.get("alive", True)
    return a


def _snap_enemy_arrow(a):
    return {"x": a.x, "y": a.y, "dir": a.dir, "w": a.w, "alive": a.alive}


def _restore_enemy_arrow(d):
    a = EnemyArrow(d["x"], d["y"], d["dir"], lane=d["w"])
    a.alive = d.get("alive", True)
    return a


PLAYER_SNAP_KEYS = (
    "x", "y", "w", "vx", "vy", "on_ground", "hp", "max_hp", "facing", "col", "s",
    "sword_anim", "sword_cd", "swing_id", "combo_step", "combo_timer", "attack_style",
    "melee_anim", "melee_cd", "melee_active_lo", "melee_active_hi",
    "bow_charge", "bow_timer", "xbow_timer", "xbow_cock", "fan_cd", "weapon", "kills",
    "blocking", "dodge_timer", "dodge_cd", "parry_active", "parry_cooldown",
    "parry_counter", "parry_vuln", "hitstun", "lane_cd", "w_step_anim", "slow_meter",
    "hurt_flash", "hit_react", "anim_tick",
)

ENEMY_SNAP_KEYS = (
    "x", "y", "w", "vx", "vy", "on_ground", "hp", "max_hp", "facing", "alive", "etype",
    "atk_timer", "atk_active", "atk_style", "telegraph", "aim_draw", "patrol_dir",
    "patrol_tick", "aggro", "counted", "shoot_timer", "hitstun", "dash_timer",
    "shield_broken", "echo_flash", "echo_ap", "echo_bow", "echo_style",
    "hurt_flash", "hit_react", "anim_tick", "lane_cd", "w_step_anim",
)

BOSS_SNAP_KEYS = (
    "x", "y", "w", "vx", "vy", "on_ground", "hp", "max_hp", "facing", "alive", "phase",
    "action", "action_timer", "slam_progress", "slam_active", "charge_windup",
    "shoot_timer", "roar_done", "enrage_flash", "intro_timer", "pattern_idx",
    "telegraph_label", "boss_echo_label", "hitstun", "atk_active", "atk_hit_frame",
    "echo_flash", "echo_kind", "counted", "hurt_flash", "hit_react", "anim_tick",
)


def _snap_player(p):
    d = {k: getattr(p, k) for k in PLAYER_SNAP_KEYS}
    d["arrows"] = [_snap_arrow(a) for a in p.arrows]
    d["melee_style"] = p.attack_style if p.melee_profile else None
    return d


def _restore_player(p, d):
    for k in PLAYER_SNAP_KEYS:
        setattr(p, k, d[k])
    p.arrows = [_restore_arrow(a) for a in d.get("arrows", [])]
    style = d.get("melee_style")
    if style and p.weapon == "bow":
        p.melee_profile = WEAPON_PROFILES["bow"]["melee"].get(style)
    elif style and p.weapon == "crossbow":
        p.melee_profile = WEAPON_PROFILES["crossbow"]["melee"].get(style)
    else:
        p.melee_profile = None


def _snap_enemy(e):
    d = {k: getattr(e, k) for k in ENEMY_SNAP_KEYS}
    d["e_arrows"] = [_snap_enemy_arrow(a) for a in e.e_arrows]
    return d


def _restore_enemy(d):
    e = Enemy(d["x"], d["y"], d["etype"])
    for k in ENEMY_SNAP_KEYS:
        if k != "etype":
            setattr(e, k, d[k])
    e.e_arrows = [_restore_enemy_arrow(a) for a in d.get("e_arrows", [])]
    return e


def _snap_boss(b):
    if b is None:
        return None
    d = {k: getattr(b, k) for k in BOSS_SNAP_KEYS}
    d["pattern_queue"] = list(b.pattern_queue)
    d["e_arrows"] = [_snap_enemy_arrow(a) for a in b.e_arrows]
    d["pending_taunt"] = b.pending_taunt
    d["_last_phase"] = b._last_phase
    return d


def _restore_boss(b, d):
    if d is None:
        return None
    if b is None:
        b = Boss(d["x"], d["y"])
    for k in BOSS_SNAP_KEYS:
        setattr(b, k, d[k])
    b.pattern_queue = list(d.get("pattern_queue", []))
    b.e_arrows = [_restore_enemy_arrow(a) for a in d.get("e_arrows", [])]
    b.pending_taunt = d.get("pending_taunt")
    b._last_phase = d.get("_last_phase", b.phase)
    return b


def capture_combat_snapshot(player, enemies, boss, wave, wave_clear_timer):
    return {
        "player": _snap_player(player),
        "enemies": [_snap_enemy(e) for e in enemies],
        "boss": _snap_boss(boss) if boss is not None else None,
        "wave": wave,
        "wave_clear_timer": wave_clear_timer,
    }


def restore_combat_snapshot(snap, player, boss):
    _restore_player(player, snap["player"])
    enemies = [_restore_enemy(d) for d in snap["enemies"]]
    boss = _restore_boss(boss, snap["boss"])
    return enemies, boss, snap["wave"], snap["wave_clear_timer"]


class RewindBuffer:
    def __init__(self, maxlen=None):
        self._buf = deque(maxlen=maxlen or REWIND_SPEC["buffer_frames"])

    def clear(self):
        self._buf.clear()

    def push(self, snap):
        self._buf.append(snap)

    def __len__(self):
        return len(self._buf)

    def snapshot_at(self, frames_back):
        if not self._buf:
            return None
        idx = max(0, len(self._buf) - 1 - int(frames_back))
        return self._buf[idx]


def try_combat_rewind(buffer, player, enemies, boss, wave_clear_timer, particles):
    """Consume a rewind charge and restore combat state from the ring buffer."""
    global COMBAT_HITSTOP, TIME_SLOW_FRAMES, TIME_SIM_ACCUM, REWIND_FLASH_FRAMES
    if not getattr(player, "can_rewind", False) or player.rewind_charges <= 0:
        return None
    back = min(REWIND_SPEC["rewind_frames"], len(buffer) - 1)
    if back < 12:
        return None
    snap = buffer.snapshot_at(back)
    if snap is None:
        return None
    player.rewind_charges -= 1
    new_enemies, new_boss, wave, wct = restore_combat_snapshot(snap, player, boss)
    COMBAT_HITSTOP = 0
    TIME_SLOW_FRAMES = 0
    TIME_SIM_ACCUM = 0.0
    REWIND_FLASH_FRAMES = REWIND_SPEC["flash_frames"]
    particles.clear()
    for _ in range(20):
        particles.append(Particle(
            player.x + random.uniform(-30, 30) * SX, w_ground_y(player.w) - random.uniform(10, 50) * SY,
            (180, 90, 255), vx=random.uniform(-3, 3) * SX, vy=random.uniform(-4, -1) * SY,
            life=random.randint(10, 22), size=random.randint(2, 4),
        ))
    play("dodge")
    return new_enemies, new_boss, wave, wct


def rewind_charges_for_loadout(owned, perks):
    if "rewind" not in owned:
        return 0
    n = REWIND_SPEC["charges_base"]
    if "rewind_cell" in perks:
        n += REWIND_SPEC["perk_charge_bonus"]
    return n


# ── Meta progression & combat config ───────────────────────────────────────────
SCRAP_PER_KILL = 1
SCRAP_SECTOR_CLEAR = 25
SCRAP_BOSS_WIN = 100
MAX_COMBAT_TIER = 6
DEFAULT_OWNED = ["block"]
DEFAULT_GEAR = {"blade": "standard", "quiver": "standard", "frame": "standard"}

DEFENSE_SPEC = {
    "block_reduction": 0.65,
    "block_move_mult": 0.50,
    "dodge_iframes": 14,
    "dodge_cd": 40,
    "dodge_backstep": 7.0,
    "parry_frames": 6,
    "parry_cd": 25,
    "parry_range": 50,
    "parry_counter_frames": 30,
    "parry_counter_mult": 1.75,
    "parry_counter_mult_riposte": 2.0,
    "guard_break_stun": 12,
    "parry_whiff_vuln": 8,
    "shift_tap_frames": 10,
}

WEAPON_PROFILES = {
    "sword": {
        "combo": ("jab", "slash", "finisher"),
        "combo_window": 48,
        "anim_len": 22,
        "cd_max": 36,
        "active_lo": 9,
        "active_hi": 13,
        "moves": {
            "jab":      {"reach": 42, "dmg": (16, 24), "kb": 5.2, "freeze": 3, "shake": (7, 9),  "lunge": 0.85},
            "slash":    {"reach": 48, "dmg": (22, 34), "kb": 6.8, "freeze": 3, "shake": (7, 9),  "lunge": 1.05},
            "finisher": {"reach": 54, "dmg": (28, 42), "kb": 8.5, "freeze": 5, "shake": (10, 12), "lunge": 1.35},
            "cleave":   {"reach": 58, "dmg": (32, 48), "kb": 9.0, "freeze": 5, "shake": (10, 12), "lunge": 1.20, "multi": 2},
        },
    },
    "bow": {
        "melee": {
            "pommel": {"reach": 32, "dmg": (10, 16), "kb": 4.0, "freeze": 2, "shake": (4, 6), "anim_len": 16, "active_lo": 6, "active_hi": 9},
            "sweep":  {"reach": 40, "dmg": (14, 20), "kb": 3.0, "freeze": 2, "shake": (5, 7), "anim_len": 20, "active_lo": 8, "active_hi": 11, "trip": True},
        },
        "quick_shot_dmg": (12, 18),
        "charge_dmg": (22, 35),
        "bow_cd": 45,
        "charge_max": 40,
    },
    "crossbow": {
        "melee": {
            "bash": {"reach": 36, "dmg": (18, 26), "kb": 6.0, "freeze": 3, "shake": (6, 8), "anim_len": 18, "active_lo": 7, "active_hi": 10, "break_block": True},
        },
        "bolt_dmg": (30, 45),
        "bolt_cd": 30,
        "fan_cd": 60,
        "pierce": 2,
    },
}

ENEMY_ARCHETYPES = {
    "soldier":    {"col": ENEMY_COL, "size": 1.0,  "hp": 60,  "speed": 2.2, "atk_style": "chop",  "atk_total": 20, "atk_hit": 10, "dmg": (8, 16),  "label": ""},
    "commander":  {"col": CMD_COL,   "size": 1.3,  "hp": 130, "speed": 1.6, "atk_style": "slash", "atk_total": 20, "atk_hit": 10, "dmg": (10, 18), "label": "CMD", "ranged": True},
    "shielder":   {"col": (100, 90, 70), "size": 1.15, "hp": 100, "speed": 1.4, "atk_style": "bash", "atk_total": 26, "atk_hit": 12, "dmg": (12, 20), "label": "SHD", "blocks": True, "guard_break": True},
    "skirmisher": {"col": (200, 120, 50), "size": 0.95, "hp": 45,  "speed": 3.4, "atk_style": "jab",  "atk_total": 16, "atk_hit": 8,  "dmg": (6, 12),  "label": "SKM", "dash": True},
    "bruiser":    {"col": (120, 50, 30),  "size": 1.45, "hp": 180, "speed": 1.2, "atk_style": "chop", "atk_total": 28, "atk_hit": 14, "dmg": (16, 28), "label": "BRU", "guard_break": True},
}

SECTOR_SPAWNS = [
    {"soldier": 3},
    {"soldier": 4, "skirmisher": 1},
    {"soldier": 4, "commander": 1, "skirmisher": 1},
    {"soldier": 3, "shielder": 2, "commander": 1},
    {"soldier": 4, "bruiser": 1, "commander": 2},
    {"soldier": 4, "shielder": 2, "bruiser": 1, "commander": 2},
]

MONROE_PATTERNS = {
    0: ["walk", "slam", "shoot:2", "slam", "walk"],
    1: ["charge", "slam", "shoot:3", "charge", "slam"],
    2: ["charge", "slam", "slam", "shoot:5", "charge", "slam"],
}

TIER_GRANTS = {
    0: ["block"],
    1: ["dodge"],
    2: ["parry", "bow_sweep"],
    3: ["sword_cleave"],
    4: ["crossbow_fan", "rewind"],
    5: ["perk_slot"],
    6: ["veteran_title"],
}

UPGRADE_CATALOG = [
    {"id": "hp_10",        "name": "+10 Max HP",           "tier": 1, "cost": 15, "type": "stat", "effect": "hp_10", "max_stacks": 3},
    {"id": "blade_sharp",  "name": "Sharpened Blade (+8% sword)", "tier": 2, "cost": 30, "type": "gear", "slot": "blade", "gear_id": "sharp"},
    {"id": "quiver_fast",  "name": "Fast Quiver (-15% bow charge)", "tier": 2, "cost": 25, "type": "gear", "slot": "quiver", "gear_id": "fast"},
    {"id": "frame_pierce", "name": "Piercing Frame (3 pierce)", "tier": 3, "cost": 35, "type": "gear", "slot": "frame", "gear_id": "pierce"},
    {"id": "double_nock",  "name": "Double Nock (2 arrows charged)", "tier": 3, "cost": 40, "type": "move", "move": "double_nock"},
    {"id": "perk_bloodlust","name": "Perk: Bloodlust (+1 scrap/kill)", "tier": 2, "cost": 50, "type": "perk", "perk": "bloodlust"},
    {"id": "perk_iron_guard","name": "Perk: Iron Guard (+10% block)", "tier": 3, "cost": 45, "type": "perk", "perk": "iron_guard"},
    {"id": "perk_riposte", "name": "Perk: Riposte (2x parry counter)", "tier": 4, "cost": 60, "type": "perk", "perk": "riposte"},
    {"id": "perk_chronoscope", "name": "Perk: Chronoscope (+echo time)", "tier": 3, "cost": 48, "type": "perk", "perk": "chronoscope"},
    {"id": "perk_overclock", "name": "Perk: Overclock (+parry slow-mo)", "tier": 3, "cost": 52, "type": "perk", "perk": "overclock"},
    {"id": "perk_rewind_cell", "name": "Perk: Rewind Cell (+1 rewind)", "tier": 4, "cost": 65, "type": "perk", "perk": "rewind_cell"},
    {"id": "blade_heavy",  "name": "Heavy Blade (+12% sword, slower)", "tier": 4, "cost": 55, "type": "gear", "slot": "blade", "gear_id": "heavy"},
    {"id": "frame_heavy",  "name": "Heavy Frame (+15% bolt dmg)", "tier": 5, "cost": 70, "type": "gear", "slot": "frame", "gear_id": "heavy"},
]

GEAR_CATALOG = {
    "blade": {
        "standard": {"sword_mult": 1.0, "cd_mult": 1.0},
        "sharp":    {"sword_mult": 1.08, "cd_mult": 1.0},
        "heavy":    {"sword_mult": 1.12, "cd_mult": 1.15},
    },
    "quiver": {
        "standard": {"charge_mult": 1.0},
        "fast":     {"charge_mult": 0.85},
    },
    "frame": {
        "standard": {"bolt_mult": 1.0, "pierce": 2},
        "pierce":   {"bolt_mult": 1.0, "pierce": 3},
        "heavy":    {"bolt_mult": 1.15, "pierce": 2},
    },
}


def combat_tier(sectors_cleared):
    return min(len(sectors_cleared), MAX_COMBAT_TIER)


def tier_granted_moves(tier):
    owned = set(DEFAULT_OWNED)
    for t in range(tier + 1):
        for item in TIER_GRANTS.get(t, []):
            owned.add(item)
    return owned


def load_combat_meta():
    d = _read_save_dict()
    owned = list(d.get("owned_upgrades", DEFAULT_OWNED[:]))
    if "block" not in owned:
        owned.insert(0, "block")
    gear = dict(DEFAULT_GEAR)
    gear.update(d.get("equipped_gear", {}))
    return {
        "scrap": int(d.get("scrap", 0)),
        "owned_upgrades": owned,
        "equipped_perks": list(d.get("equipped_perks", []))[:2],
        "equipped_gear": gear,
    }


def write_combat_meta(scrap=None, owned_upgrades=None, equipped_perks=None, equipped_gear=None):
    d = _read_save_dict()
    if scrap is not None:
        d["scrap"] = int(scrap)
    if owned_upgrades is not None:
        d["owned_upgrades"] = list(owned_upgrades)
    if equipped_perks is not None:
        d["equipped_perks"] = list(equipped_perks)[:2]
    if equipped_gear is not None:
        g = dict(DEFAULT_GEAR)
        g.update(equipped_gear)
        d["equipped_gear"] = g
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(d, f)
    except Exception:
        pass


def apply_loadout(player, meta, sectors_cleared):
    tier = combat_tier(sectors_cleared)
    granted = tier_granted_moves(tier)
    owned = set(meta.get("owned_upgrades", [])) | granted
    perks = set(meta.get("equipped_perks", []))
    gear = meta.get("equipped_gear", DEFAULT_GEAR)

    player.loadout_tier = tier
    player.owned_moves = owned
    player.equipped_perks = perks
    player.gear = gear

    blade = GEAR_CATALOG["blade"].get(gear.get("blade", "standard"), GEAR_CATALOG["blade"]["standard"])
    quiver = GEAR_CATALOG["quiver"].get(gear.get("quiver", "standard"), GEAR_CATALOG["quiver"]["standard"])
    frame = GEAR_CATALOG["frame"].get(gear.get("frame", "standard"), GEAR_CATALOG["frame"]["standard"])

    player.sword_dmg_mult = blade["sword_mult"]
    player.sword_cd_mult = blade.get("cd_mult", 1.0)
    player.bow_charge_mult = quiver["charge_mult"]
    player.bolt_dmg_mult = frame["bolt_mult"]
    player.bolt_pierce = frame["pierce"]

    hp_stacks = sum(1 for oid in meta.get("owned_upgrades", []) if oid == "hp_10")
    player.max_hp = 100 + hp_stacks * 10
    player.hp = player.max_hp

    block_red = DEFENSE_SPEC["block_reduction"]
    if "perk_iron_guard" in perks:
        block_red = min(0.90, block_red + 0.10)
    player.block_reduction = block_red

    player.parry_counter_mult = (
        DEFENSE_SPEC["parry_counter_mult_riposte"] if "perk_riposte" in perks
        else DEFENSE_SPEC["parry_counter_mult"]
    )
    player.scrap_per_kill_bonus = 1 if "perk_bloodlust" in perks else 0

    player.can_dodge = "dodge" in owned
    player.can_parry = "parry" in owned
    player.has_cleave = "sword_cleave" in owned
    player.has_bow_sweep = "bow_sweep" in owned
    player.has_double_nock = "double_nock" in owned
    player.has_crossbow_fan = "crossbow_fan" in owned

    player.echo_bonus = 10 if "chronoscope" in perks else 0
    player.slow_parry_bonus = 18 if "overclock" in perks else 0
    player.slow_meter_max = TIME_SPEC["meter_max"]
    if player.slow_meter_max > getattr(player, "slow_meter", 0):
        player.slow_meter = player.slow_meter_max

    player.can_rewind = "rewind" in owned
    player.rewind_max = rewind_charges_for_loadout(owned, perks)


def apply_damage_to_player(player, dmg, attacker_facing, particles, source="melee",
                           guard_break=False, attacker=None, all_lanes=False, source_w=None):
    """Central damage gate: dodge i-frames, parry, block, depth lane."""
    if player.is_invulnerable():
        return False

    if not all_lanes:
        aw = source_w
        if aw is None and attacker is not None:
            aw = getattr(attacker, "w", W_LANE_MID)
            if getattr(attacker, "slam_active", False):
                all_lanes = True
        if aw is None:
            aw = W_LANE_MID
        if not all_lanes and not w_can_hit(aw, player.w):
            return False

    # Active parry window from player tap
    if player.parry_active > 0 and attacker is not None:
        dist = abs(player.x - attacker.x)
        facing_ok = (player.facing == 1 and attacker.x > player.x) or (player.facing == -1 and attacker.x < player.x)
        hit_frame = False
        if hasattr(attacker, "atk_active") and attacker.atk_active > 0:
            ah = getattr(attacker, "atk_hit_frame", getattr(attacker, "ATK_HIT_FRAME", 10))
            hit_frame = attacker.atk_active == ah
        if hasattr(attacker, "slam_active") and attacker.slam_active and attacker.slam_progress >= 0.95:
            hit_frame = True
        if dist < DEFENSE_SPEC["parry_range"] * SX and facing_ok and hit_frame:
            player.parry_active = 0
            player.parry_counter = DEFENSE_SPEC["parry_counter_frames"]
            player.parry_cooldown = DEFENSE_SPEC["parry_cd"]
            if hasattr(attacker, "hitstun"):
                attacker.hitstun = max(getattr(attacker, "hitstun", 0), 12)
            elif hasattr(attacker, "atk_active"):
                attacker.atk_active = 0
            play("parry")
            combat_freeze(6)
            combat_shake(8, 10)
            combat_trigger_slowmo(
                TIME_SPEC["parry_slow_frames"] + getattr(player, "slow_parry_bonus", 0),
                TIME_SPEC["slow_scale"],
            )
            for _ in range(8):
                particles.append(Particle(player.x, player.y - 25 * SY, (255, 240, 180),
                                            vx=random.uniform(-4, 4) * SX, vy=random.uniform(-3, 0) * SY, life=12, size=3))
            return False

    if player.blocking and player.on_ground and not guard_break:
        facing_ok = (player.facing == 1 and attacker_facing == -1) or (player.facing == -1 and attacker_facing == 1)
        if facing_ok or source == "projectile":
            reduced = max(1, int(dmg * (1.0 - player.block_reduction)))
            player.hp -= reduced
            player.hurt_flash = 6
            play("block")
            combat_freeze(1)
            combat_shake(3, 4)
            return True

    if player.blocking and guard_break:
        player.blocking = False
        player.hitstun = max(player.hitstun, DEFENSE_SPEC["guard_break_stun"])
        play("hit")

    player.hp -= dmg
    player.hurt_flash = 12 if source == "melee" else 10
    player.hitstun = max(player.hitstun, 12 if source == "melee" else 8)
    player.hit_react = 14 if source == "melee" else 10
    player.vx = -attacker_facing * (5.2 if source == "melee" else 2.8) * SX
    if source == "melee":
        player.vy = -3.4 * SY
    play("hit")
    combat_freeze(2 if source == "projectile" else 2)
    combat_shake(5 if source == "melee" else 3, 7 if source == "melee" else 5)
    for _ in range(5):
        particles.append(Particle(player.x, player.y - 20 * SY, BLOOD_COL))
    return True


# ── Combat choreography (phased poses, telegraphs, reactions) ─────────────────
def choreo_attack_phase(t):
    """0..1 progress: slow wind-up, fast strike, follow-through, recovery."""
    t = max(0.0, min(1.0, float(t)))
    if t < 0.28:
        return 0.10 * (t / 0.28) ** 1.7
    if t < 0.52:
        u = (t - 0.28) / 0.24
        return 0.10 + 0.74 * (u ** 0.50)
    if t < 0.82:
        u = (t - 0.52) / 0.30
        return 0.84 + 0.13 * u
    u = (t - 0.82) / 0.18
    return 0.97 + 0.03 * u


def choreo_sword_degrees(phase, style):
    """Sword arm angle keyframes (degrees, facing applied at draw time)."""
    if style == "chop":
        return -115 + phase * 155
    if style == "jab":
        return -15 + phase * 88
    if style == "finisher":
        if phase < 0.48:
            return -125 + phase * 70
        return -91 + (phase - 0.48) * 210
    if style == "pommel":
        return 20 + phase * 55
    if style == "sweep":
        return 60 + phase * 70
    if style == "bash":
        return -40 + phase * 120
    if style == "cleave":
        return -100 + phase * 175
    return -78 + phase * 148


def choreo_attack_legs(phase):
    """Leg angles during sword commitment: plant → lunge → recover."""
    if phase < 0.30:
        return (22, -18, 38, -48)
    if phase < 0.55:
        return (48, -28, 58, -38)
    return (12, -8, 22, -18)


def choreo_enemy_attack_progress(atk_active, atk_total):
    if atk_active <= 0:
        return 0.0
    raw = 1.0 - (atk_active - 1) / max(1, atk_total)
    return choreo_attack_phase(raw)


def toggle_window_fullscreen():
    try: pygame.display.toggle_fullscreen()
    except Exception: pass

def _app_dir():
    """Project folder when running from source; PyInstaller extract dir when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

def open_trailer_in_browser():
    p = _app_dir() / "trailer.html"
    if not p.is_file():
        return False
    try:
        webbrowser.open(p.as_uri())
        return True
    except Exception:
        return False

# ── Save / High Score ──────────────────────────────────────────────────────────
def _read_save_dict():
    try:
        with open(SAVE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def load_save():
    d = _read_save_dict()
    hs = d.get("high_score", 0)
    ck = d.get("checkpoint_wave", None)
    mu = d.get("map_unlock")
    if mu is None:
        mu = 0 if ck is None else max(0, int(ck))
    story_seen = list(d.get("story_seen", []))
    sectors_cleared = list(d.get("sectors_cleared", []))
    return hs, ck, int(mu), story_seen, sectors_cleared

def write_save(score, checkpoint_wave, map_unlock, story_seen=None, sectors_cleared=None):
    d = _read_save_dict()
    d["high_score"] = int(score)
    d["checkpoint_wave"] = checkpoint_wave
    d["map_unlock"] = int(map_unlock)
    if story_seen is not None:
        d["story_seen"] = list(story_seen)
    else:
        d.setdefault("story_seen", [])
    if sectors_cleared is not None:
        d["sectors_cleared"] = list(sectors_cleared)
    else:
        d.setdefault("sectors_cleared", [])
    try:
        with open(SAVE_FILE, 'w') as f:
            json.dump(d, f)
    except Exception:
        pass

def save_checkpoint(wave_idx, score):
    hs, ck, mu, ss, sc = load_save()
    mu = max(mu, int(wave_idx))
    write_save(max(score, hs), wave_idx, mu, story_seen=ss, sectors_cleared=sc)

def update_high_score(score):
    hs, ck, mu, ss, sc = load_save()
    new_hs = max(score, hs)
    write_save(new_hs, ck, mu, story_seen=ss, sectors_cleared=sc)
    return new_hs

def clear_checkpoint():
    hs, ck, mu, ss, sc = load_save()
    write_save(hs, None, mu, story_seen=ss, sectors_cleared=sc)

# ── Particle ───────────────────────────────────────────────────────────────────
class Particle:
    __slots__=('x','y','vx','vy','col','life','max_life','size')
    def __init__(self,x,y,col,vx=None,vy=None,life=None,size=None):
        self.x,self.y=float(x),float(y); self.col=col
        self.vx  = vx   if vx   is not None else random.uniform(-3,3)*SX
        self.vy  = vy   if vy   is not None else random.uniform(-4,-1)*SY
        self.life= life if life is not None else random.randint(15,35)
        self.max_life=self.life
        self.size= size if size is not None else random.randint(2,5)
    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.vy+=0.15*SY; self.life-=1
    def draw(self,surf):
        if self.life>0:
            pygame.draw.circle(surf,self.col,(int(self.x),int(self.y)),max(1,self.size))

# ── Projectiles ────────────────────────────────────────────────────────────────
class Arrow:
    def __init__(self,x,y,direction,damage=(22,35),speed=10,
                 col=ARROW_COL,tip_col=(220,180,80),pierce=False,max_pierce=2,lane=W_LANE_MID):
        self.x,self.y=float(x),float(y)
        self.vx=speed*SX*direction; self.vy=-1.0*SY
        self.alive=True; self.dir=direction
        self.damage=damage; self.col=col
        self.tip_col=tip_col; self.pierce=pierce
        self.hit_count=0; self.max_pierce=max_pierce
        self.w=int(lane)
    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.vy+=0.08*SY
        m=30*SX
        if self.x<-m or self.x>WIDTH+m or self.y>GROUND_Y: self.alive=False
    def draw(self,surf):
        tip=(int(self.x+14*SY*self.dir),int(self.y))
        tail=(int(self.x-14*SY*self.dir),int(self.y+4*SY))
        w=max(LW+1, round(3*SY)) if self.pierce else LW
        pygame.draw.line(surf,self.col,tail,tip,w)
        pygame.draw.circle(surf,self.tip_col,tip,max(2, round(2*SY)))
        if self.pierce:
            pygame.draw.line(surf,(200,255,200),tail,(int(self.x-6*SY*self.dir),int(self.y)),max(1,LW-1))

class EnemyArrow:
    def __init__(self,x,y,direction,lane=W_LANE_MID):
        self.x,self.y=float(x),float(y)
        self.vx=5.5*SX*direction; self.vy=0.0
        self.alive=True; self.dir=direction
        self.w=int(lane)
    def update(self):
        self.x+=self.vx; self.vy+=0.06*SY; self.y+=self.vy
        m=30*SX
        if self.x<-m or self.x>WIDTH+m or self.y>GROUND_Y: self.alive=False
    def draw(self,surf):
        tip=(int(self.x+10*SY*self.dir),int(self.y))
        tail=(int(self.x-10*SY*self.dir),int(self.y+3*SY))
        pygame.draw.line(surf,(180,120,60),tail,tip,LW)

# ── Stickman Base ──────────────────────────────────────────────────────────────
class Stickman:
    def __init__(self,x,y,col,size=1.0,lane=W_LANE_MID):
        self.x,self.y=float(x),float(y); self.col=col; self.s=size
        self.vx,self.vy=0.0,0.0; self.on_ground=False
        self.hp=100; self.max_hp=100
        self.facing=1; self.anim_tick=0; self.hurt_flash=0
        self.hit_react=0
        self.last_player_swing=-1
        self.w=int(lane)
        self.lane_cd=0
        self.w_step_anim=0

    def _draw_shadow(self, surf):
        py = w_ground_y(self.w)
        sc = w_depth_scale(self.w) * self.s
        rw = max(8, int(16 * sc * SX))
        rh = max(3, int(5 * SY * sc))
        sx = int(self.x) - rw
        sy = int(py) - int(3 * SY)
        pygame.draw.ellipse(surf, (18, 14, 10), (sx, sy, rw * 2, rh))

    def _with_projection(self, surf, draw_fn):
        saved = (self.y, self.s, self.col)
        self.y = float(w_ground_y(self.w))
        self.s = self.s * w_depth_scale(self.w)
        tint = w_lane_tint(self.w)
        if tint < 0.99:
            self.col = tuple(min(255, int(c * tint)) for c in self.col)
        self._draw_shadow(surf)
        draw_fn(surf)
        self.y, self.s, self.col = saved

    def _limb_angles(self):
        t=self.anim_tick
        if abs(self.vx)>0.5:
            l1=math.sin(t*0.25)*35; l2=-l1
            a1=math.sin(t*0.25+1)*25; a2=-a1
        else:
            l1=l2=a1=a2=0
        return l1,l2,a1,a2

    def _draw_legs(self, surf, cx, hip, ll, col, l1, l2):
        for angle in (l1, l2):
            rad = math.radians(angle)
            kx = cx + int(math.sin(rad) * ll)
            ky = hip + int(math.cos(rad) * ll)
            fx = kx + int(math.sin(rad * 0.5) * ll * self.facing)
            fy = ky + int(ll * 0.8)
            pygame.draw.line(surf, col, (cx, hip), (kx, ky), LW)
            pygame.draw.line(surf, col, (kx, ky), (fx, fy), LW)

    def _draw_arms_idle(self, surf, cx, shy, ll, col, a1, a2):
        for angle in (a1, a2):
            rad = math.radians(angle + 15 * self.facing)
            ex = cx + int(math.sin(rad) * ll * self.facing)
            ey = shy + int(math.cos(rad) * ll)
            pygame.draw.line(surf, col, (cx, shy), (ex, ey), LW)

    def _draw_sword_swing(self, surf, cx, shy, ll, col, s, phase, style, telegraph=0):
        swing = choreo_sword_degrees(phase, style) * self.facing
        ax = cx + int(math.cos(math.radians(swing)) * ll * 1.25 * self.facing)
        ay = shy + int(math.sin(math.radians(swing)) * ll * 0.85)
        arm_col = (255, 220, 100) if telegraph else col
        pygame.draw.line(surf, arm_col, (cx, shy), (ax, ay), LW)
        tx = ax + int(20 * s * SY * self.facing)
        ty = ay - int(6 * s * SY)
        sw = max(LW + 1, round(3 * SY))
        pygame.draw.line(surf, SWORD_COL, (ax, ay), (tx, ty), sw)
        hl = max(1, LW - 1)
        pygame.draw.line(surf, (240, 240, 255), (ax, ay - hl), (tx, ty - hl), hl)
        if phase >= 0.28 and phase < 0.58:
            for i, alpha in enumerate((55, 35, 18)):
                ox = int(-10 * i * self.facing)
                trail = pygame.Surface((int(50 * SX), int(40 * SY)), pygame.SRCALPHA)
                pygame.draw.line(
                    trail, (*SWORD_COL, alpha),
                    (8, 20), (40 + ox, 8), max(1, LW),
                )
                surf.blit(trail, (min(ax, tx) - 8, min(ay, ty) - 16))
        bkx = cx - int(12 * s * SY * self.facing)
        bpy = shy + int(8 * s * SY)
        pygame.draw.line(surf, col, (cx, shy), (bkx, bpy), LW)

    def _draw_hit_react(self, surf, cx, shy, hip, ll, col, s, intensity):
        lean = int(9 * SY * intensity) * (-self.facing)
        cx2 = cx + lean
        pygame.draw.line(surf, col, (cx2, shy - int(4 * SY)), (cx2, hip), LW)
        guard = 35 + int(25 * intensity)
        for sign in (-1, 1):
            rad = math.radians(guard * sign)
            ex = cx2 + int(math.sin(rad) * ll * 0.9 * self.facing)
            ey = shy + int(math.cos(rad) * ll * 0.7) - int(6 * SY * intensity)
            pygame.draw.line(surf, col, (cx2, shy), (ex, ey), LW)
        l1, l2 = 30 + int(15 * intensity), -22
        self._draw_legs(surf, cx2, hip, ll, col, l1, l2)

    def _draw_charge_crouch(self, surf, cx, shy, hip, ll, col, s, amount):
        cx2 = cx + int(6 * SY * self.facing * amount)
        shy2 = shy + int(5 * SY * amount)
        pygame.draw.line(surf, col, (cx2, shy2), (cx2, hip), LW)
        self._draw_legs(surf, cx2, hip, ll, col, 55 * amount, -40 * amount)
        ax = cx2 + int(22 * s * SY * self.facing)
        ay = shy2 + int(4 * SY)
        pygame.draw.line(surf, col, (cx2, shy2), (ax, ay), LW + 1)

    def _draw_block_pose(self, surf, cx, shy, hip, ll, col):
        cx2 = cx + int(4 * SY * self.facing)
        pygame.draw.line(surf, col, (cx2, shy), (cx2, hip), LW)
        for ang in (55, 125):
            rad = math.radians(ang * self.facing)
            ex = cx2 + int(math.sin(rad) * ll * 0.95)
            ey = shy + int(math.cos(rad) * ll * 0.6)
            pygame.draw.line(surf, col, (cx2, shy), (ex, ey), LW + 1)
        self._draw_legs(surf, cx2, hip, ll, col, 18, -12)

    def draw_body(self, surf, attack_progress=0, bow_draw=0,
                  crossbow_aim=0, boss_slam=0.0, attack_style="slash",
                  leg_override=None, hit_react_amt=0.0, charge_pose=0.0,
                  telegraph=0, block_amt=0.0):
        s = self.s; cx, cy = int(self.x), int(self.y)
        col = WHITE if self.hurt_flash > 0 else self.col
        hr = int(9 * s * SY); tl = int(22 * s * SY); ll = int(18 * s * SY)
        hy = cy - tl - hr; ny = cy - tl; hip = cy; shy = cy - int(tl * 0.75)

        l1, l2, a1, a2 = self._limb_angles()
        if leg_override is not None:
            l1, l2, a1, a2 = leg_override[0], leg_override[1], leg_override[2], leg_override[3]

        if hit_react_amt > 0.05 and attack_progress <= 0 and boss_slam <= 0 and block_amt <= 0:
            pygame.draw.circle(surf, col, (cx + int(4 * SY * (-self.facing) * hit_react_amt), hy), hr, LW)
            self._draw_hit_react(surf, cx, shy, hip, ll, col, s, hit_react_amt)
            return

        if block_amt > 0.05 and attack_progress <= 0 and boss_slam <= 0:
            pygame.draw.circle(surf, col, (cx, hy), hr, LW)
            self._draw_block_pose(surf, cx, shy, hip, ll, col)
            return

        pygame.draw.circle(surf, col, (cx, hy), hr, LW)
        torso_lean = 0
        if attack_progress > 0:
            ph = choreo_attack_phase(attack_progress)
            if ph < 0.30:
                torso_lean = int(-5 * SY * self.facing)
            elif ph < 0.55:
                torso_lean = int(4 * SY * self.facing)
        elif charge_pose > 0:
            torso_lean = int(5 * SY * self.facing * charge_pose)
        cx_t = cx + torso_lean
        pygame.draw.line(surf, col, (cx_t, ny), (cx_t, hip), LW)

        if boss_slam > 0:
            slam_ease = boss_slam ** 0.65 if boss_slam < 0.6 else boss_slam
            up = math.sin(slam_ease * math.pi)
            ax1 = cx_t + int(ll * 1.4 * self.facing)
            ay1 = shy - int(ll * up)
            ax2 = cx_t - int(ll * 1.4 * self.facing)
            ay2 = ay1
            sw = max(LW + 1, round(3 * SY))
            pygame.draw.line(surf, col, (cx_t, shy), (ax1, ay1), sw)
            pygame.draw.line(surf, col, (cx_t, shy), (ax2, ay2), sw)
            club = (ax1 + int(18 * s * SY * self.facing), ay1 + int(8 * s * SY))
            pygame.draw.line(surf, (120, 80, 40), (ax1, ay1), club, max(3, round(5 * SY)))
            pygame.draw.circle(surf, (100, 65, 30), club, int(7 * s * SY))
            self._draw_legs(surf, cx_t, hip, ll, col, 38, -32)

        elif charge_pose > 0:
            self._draw_charge_crouch(surf, cx, shy, hip, ll, col, s, charge_pose)

        elif attack_progress > 0:
            ph = choreo_attack_phase(attack_progress)
            legs = choreo_attack_legs(ph)
            self._draw_legs(surf, cx_t, hip, ll, col, legs[0], legs[1])
            self._draw_sword_swing(surf, cx_t, shy, ll, col, s, ph, attack_style, telegraph)

        elif crossbow_aim > 0:
            self._draw_legs(surf, cx, hip, ll, col, l1, l2)
            bx = cx + int(ll * self.facing * 1.2); by_ = shy
            pygame.draw.line(surf, col, (cx, shy), (bx, by_), LW)
            pygame.draw.line(surf, (100, 70, 30),
                             (bx - int(8 * SY * self.facing), by_),
                             (bx + int(8 * SY * self.facing), by_), max(3, round(4 * SY)))
            pygame.draw.line(surf, (80, 50, 20), (bx, by_ - int(10 * SY)), (bx, by_ + int(4 * SY)),
                             max(LW + 1, round(3 * SY)))
            if crossbow_aim > 0.3:
                btx = bx + int(14 * SY * self.facing)
                pygame.draw.line(surf, BOLT_COL, (bx, by_), (btx, by_), LW)
            pull = cx - int(8 * s * SY * self.facing)
            pygame.draw.line(surf, col, (cx, shy), (pull, shy + int(12 * s * SY)), LW)

        elif bow_draw > 0:
            self._draw_legs(surf, cx, hip, ll, col, l1, l2)
            bx = cx + int(ll * self.facing * 1.1); by_ = shy
            pygame.draw.line(surf, col, (cx, shy), (bx, by_), LW)
            aw, ah = int(14 * SY), int(28 * SY)
            pygame.draw.arc(surf, (120, 80, 30), (bx - int(8 * SY), by_ - int(14 * SY), aw, ah),
                            math.radians(-60), math.radians(60), LW)
            pull = bx - int(bow_draw * 8 * SY * self.facing)
            hl = max(1, LW - 1)
            pygame.draw.line(surf, (200, 200, 200), (bx, by_ - int(14 * SY)), (pull, by_), hl)
            pygame.draw.line(surf, (200, 200, 200), (bx, by_ + int(14 * SY)), (pull, by_), hl)
            pygame.draw.line(surf, col, (cx, shy), (pull, by_), LW)

        else:
            self._draw_legs(surf, cx, hip, ll, col, l1, l2)
            self._draw_arms_idle(surf, cx, shy, ll, col, a1, a2)

    def draw_echo_pose(self, surf, attack_progress=0, bow_draw=0, attack_style="slash",
                       boss_slam=0.0, charge_pose=0.0, alpha=72):
        """Cyan ghost preview of an imminent strike (time-dimension tell)."""
        pad = int(72 * SX)
        gx = int(self.x)
        gy = int(w_ground_y(self.w))
        w, h = pad * 2, int(100 * SY)
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        lx = pad
        ly = h - int(18 * SY)
        saved = (self.x, self.y, self.col, self.s)
        self.x = lx
        self.y = ly
        self.col = (55, 205, 245)
        self.s = self.s * w_depth_scale(self.w)
        self._draw_shadow(layer)
        self.draw_body(
            layer, attack_progress=attack_progress, bow_draw=bow_draw,
            attack_style=attack_style, boss_slam=boss_slam, charge_pose=charge_pose,
        )
        self.x, self.y, self.col, self.s = saved
        layer.set_alpha(max(0, min(255, int(alpha))))
        surf.blit(layer, (gx - pad, gy - h + int(22 * SY)))

    def draw_w_slice_ghost(self, surf, ghost_w, alpha=38, body_kwargs=None):
        """Faded copy on an adjacent depth lane (spatial W tell — not time echo)."""
        gw = int(ghost_w)
        if gw < W_LANE_FAR or gw > W_LANE_NEAR or gw == int(self.w):
            return
        pad = int(72 * SX)
        gx = int(self.x)
        gy = int(w_ground_y(gw))
        w, h = pad * 2, int(100 * SY)
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        lx = pad
        ly = h - int(18 * SY)
        saved = (self.x, self.y, self.col, self.s, self.w)
        self.x = lx
        self.y = ly
        self.w = gw
        tint = w_lane_tint(gw)
        base = (95, 88, 78)
        self.col = tuple(min(255, int(c * tint)) for c in base)
        self.s = self.s * w_depth_scale(gw)
        self._draw_shadow(layer)
        kwargs = body_kwargs or {}
        self.draw_body(layer, **kwargs)
        self.x, self.y, self.col, self.s, self.w = saved
        layer.set_alpha(max(0, min(255, int(alpha))))
        surf.blit(layer, (gx - pad, gy - h + int(22 * SY)))

    def physics(self):
        self.vy+=GRAVITY; self.x+=self.vx; self.y+=self.vy
        if self.y>=GROUND_Y: self.y=GROUND_Y; self.vy=0; self.on_ground=True
        else: self.on_ground=False
        pad=10*SX
        self.x=max(pad,min(WIDTH-pad,self.x))
        self.anim_tick+=1
        if self.hurt_flash>0: self.hurt_flash-=1
        if self.hit_react>0: self.hit_react-=1

    def rect(self):
        s = self.s * w_depth_scale(self.w)
        py = w_ground_y(self.w)
        return pygame.Rect(self.x - 12 * s * SY, py - 50 * s * SY, 24 * s * SY, 55 * s * SY)

# ── Player ─────────────────────────────────────────────────────────────────────
class Player(Stickman):
    """Sword timing + block/dodge/parry + per-weapon move sets."""
    SPEED=4.2*SX; JUMP_V=-13*SY

    def __init__(self,x,y,kills=0):
        super().__init__(x,y,PLAYER_COL,size=1.15)
        self.sword_anim=0; self.sword_cd=0; self.swing_id=0
        self.hitstun=0; self.combo_step=0; self.combo_timer=0
        self.attack_style="slash"; self.melee_anim=0; self.melee_cd=0
        self.melee_active_lo=0; self.melee_active_hi=0; self.melee_profile=None
        self.bow_charge=0; self.bow_timer=0; self.bow_held_last=False
        self.xbow_timer=0; self.xbow_cock=0; self.fan_cd=0
        self.arrows=[]; self.weapon="sword"; self.kills=kills
        self.blocking=False; self.dodge_timer=0; self.dodge_cd=0
        self.parry_active=0; self.parry_cooldown=0; self.parry_counter=0
        self.parry_vuln=0; self.shift_hold_frames=0
        self.shift_armed=False
        self.loadout_tier=0; self.owned_moves=set(DEFAULT_OWNED)
        self.equipped_perks=set(); self.gear=dict(DEFAULT_GEAR)
        self.sword_dmg_mult=1.0; self.sword_cd_mult=1.0
        self.bow_charge_mult=1.0; self.bolt_dmg_mult=1.0; self.bolt_pierce=2
        self.block_reduction=DEFENSE_SPEC["block_reduction"]
        self.parry_counter_mult=DEFENSE_SPEC["parry_counter_mult"]
        self.scrap_per_kill_bonus=0
        self.can_dodge=False; self.can_parry=False
        self.has_cleave=False; self.has_bow_sweep=False
        self.has_double_nock=False; self.has_crossbow_fan=False
        self.w=W_LANE_MID
        self.slow_meter=TIME_SPEC["meter_max"]
        self.slow_meter_max=TIME_SPEC["meter_max"]
        self.echo_bonus=0
        self.slow_parry_bonus=0
        self.can_rewind=False
        self.rewind_charges=0
        self.rewind_max=0

    def try_time_slow(self, holding):
        """Hold T to spend meter and extend Grid Stutter slow-mo."""
        if not holding or self.hitstun > 0:
            return False
        if self.slow_meter <= 2:
            return False
        self.slow_meter = max(0.0, self.slow_meter - TIME_SPEC["meter_drain"])
        combat_trigger_slowmo(TIME_SPEC["hold_extend_frames"], TIME_SPEC["slow_scale"])
        return True

    def regen_slow_meter(self):
        if TIME_SLOW_FRAMES <= 0 and COMBAT_HITSTOP <= 0:
            cap = getattr(self, "slow_meter_max", TIME_SPEC["meter_max"])
            if self.slow_meter < cap:
                self.slow_meter = min(cap, self.slow_meter + TIME_SPEC["meter_regen"])

    def try_lane_step(self, direction):
        """direction -1 = toward FAR (Q), +1 = toward NEAR (E)."""
        if self.lane_cd > 0 or self.hitstun > 0 or self.blocking:
            return False
        if self._in_melee_attack() or self.dodge_timer > 0:
            return False
        nw = int(self.w) + int(direction)
        if nw < W_LANE_FAR or nw > W_LANE_NEAR:
            return False
        self.w = nw
        self.lane_cd = W_LANE_STEP_CD
        self.w_step_anim = 12
        play("dodge")
        return True

    def _sword_raw_phase(self):
        anim = self.sword_anim if self.weapon == "sword" else self.melee_anim
        alen = self._anim_len()
        if anim <= 0:
            return 0.0
        return (alen - anim) / max(1, alen - 1)

    def _anim_len(self):
        if self.weapon == "sword":
            return WEAPON_PROFILES["sword"]["anim_len"]
        if self.melee_profile:
            return self.melee_profile.get("anim_len", 18)
        return 18

    def _sword_commitment_lock(self):
        ph = self._sword_raw_phase()
        return ph < 0.32 or ph > 0.76

    def _in_melee_attack(self):
        return (self.weapon == "sword" and self.sword_anim > 0) or self.melee_anim > 0

    def try_dodge(self):
        if not self.can_dodge or self.dodge_cd > 0 or self.hitstun > 0:
            return False
        if not self.on_ground or self._in_melee_attack():
            return False
        self.dodge_timer = DEFENSE_SPEC["dodge_iframes"]
        self.dodge_cd = DEFENSE_SPEC["dodge_cd"]
        self.vx = -self.facing * DEFENSE_SPEC["dodge_backstep"] * SX
        self.blocking = False
        play("dodge")
        return True

    def try_parry_tap(self):
        if not self.can_parry or self.parry_cooldown > 0 or self.hitstun > 0:
            return False
        if self._in_melee_attack() or self.blocking:
            return False
        self.parry_active = DEFENSE_SPEC["parry_frames"]
        self.blocking = False
        return True

    def arm_shift(self):
        """Begin tracking Shift for tap-parry vs hold-block."""
        self.shift_armed = True
        self.shift_hold_frames = 0

    def release_shift_parry(self):
        """On Shift release: quick tap becomes a parry."""
        armed = self.shift_armed
        held = self.shift_hold_frames
        self.shift_armed = False
        tap_max = DEFENSE_SPEC.get("shift_tap_frames", 10)
        if armed and held <= tap_max:
            self.blocking = False
            return self.try_parry_tap()
        return False

    def handle_input(self, keys, shift_held=False):
        if self.parry_vuln > 0:
            self.parry_vuln -= 1
        if self.parry_active > 0:
            self.parry_active -= 1
            if self.parry_active <= 0 and not shift_held:
                self.parry_vuln = DEFENSE_SPEC["parry_whiff_vuln"]
        if self.dodge_timer > 0:
            self.dodge_timer -= 1
        if self.dodge_cd > 0:
            self.dodge_cd -= 1
        if self.parry_cooldown > 0:
            self.parry_cooldown -= 1
        if self.parry_counter > 0:
            self.parry_counter -= 1
        if self.lane_cd > 0:
            self.lane_cd -= 1
        if self.w_step_anim > 0:
            self.w_step_anim -= 1

        if shift_held:
            self.shift_hold_frames += 1
        elif not self.shift_armed:
            self.shift_hold_frames = 0

        if self.hitstun > 0:
            return

        anim_busy = self._in_melee_attack()
        locked = self.weapon == "sword" and self.sword_anim > 0 and self._sword_commitment_lock()
        locked = locked or (self.melee_anim > 0 and self._sword_commitment_lock())

        # Hold Shift = block immediately; quick release (KEYUP) = parry
        want_block = (
            shift_held and self.on_ground and not anim_busy and self.bow_charge <= 0
            and self.parry_active <= 0
        )
        if want_block:
            self.blocking = True
        else:
            self.blocking = False

        spd = self.SPEED * (DEFENSE_SPEC["block_move_mult"] if self.blocking else 1.0)
        if not locked and not self.blocking:
            self.vx = 0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                self.vx = -spd; self.facing = -1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                self.vx = spd; self.facing = 1
        elif self.blocking and not locked:
            self.vx = 0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                self.vx = -spd; self.facing = -1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                self.vx = spd; self.facing = 1
        elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.facing = -1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.facing = 1

        if (keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_SPACE]) and self.on_ground:
            if not locked and not self.blocking:
                self.vy = self.JUMP_V
        if not self.blocking:
            if keys[pygame.K_1]: self.weapon = "sword"
            if keys[pygame.K_2]: self.weapon = "bow"
            if keys[pygame.K_3]: self.weapon = "crossbow"

    def is_invulnerable(self):
        return self.dodge_timer > 0

    def try_attack(self):
        if self.hitstun > 0 or self.blocking:
            return False
        if self.weapon == "sword":
            return self._try_sword_attack()
        if self.weapon == "bow":
            return self._try_bow_melee()
        if self.weapon == "crossbow":
            return self._try_crossbow_melee()
        return False

    def _try_sword_attack(self):
        wp = WEAPON_PROFILES["sword"]
        if self.sword_cd > 0 or self.sword_anim > 0:
            return False
        combo = list(wp["combo"])
        if self.has_cleave and self.combo_step >= len(combo) - 1:
            self.attack_style = "cleave"
        else:
            if self.combo_timer > 0 and self.combo_step < len(combo) - 1:
                self.combo_step += 1
            else:
                self.combo_step = 0
            self.attack_style = combo[self.combo_step]
        self.combo_timer = wp["combo_window"]
        self.sword_anim = wp["anim_len"]
        self.sword_cd = int(wp["cd_max"] * self.sword_cd_mult)
        self.swing_id += 1
        play("swing")
        return True

    def _try_bow_melee(self):
        if self.melee_cd > 0 or self.melee_anim > 0 or self.bow_charge > 0:
            return False
        if self.has_bow_sweep and self.combo_timer > 0:
            self.attack_style = "sweep"
            self.melee_profile = WEAPON_PROFILES["bow"]["melee"]["sweep"]
        else:
            self.attack_style = "pommel"
            self.melee_profile = WEAPON_PROFILES["bow"]["melee"]["pommel"]
        self.melee_anim = self.melee_profile["anim_len"]
        self.melee_active_lo = self.melee_profile["active_lo"]
        self.melee_active_hi = self.melee_profile["active_hi"]
        self.melee_cd = 28
        self.combo_timer = 36
        self.swing_id += 1
        play("swing")
        return True

    def _try_crossbow_melee(self):
        if self.melee_cd > 0 or self.melee_anim > 0:
            return False
        self.attack_style = "bash"
        self.melee_profile = WEAPON_PROFILES["crossbow"]["melee"]["bash"]
        self.melee_anim = self.melee_profile["anim_len"]
        self.melee_active_lo = self.melee_profile["active_lo"]
        self.melee_active_hi = self.melee_profile["active_hi"]
        self.melee_cd = 32
        self.swing_id += 1
        play("swing")
        return True

    def try_bow(self, charging):
        if self.hitstun > 0 or self.blocking:
            return
        if self.weapon != "bow":
            return
        cmax = int(WEAPON_PROFILES["bow"]["charge_max"] * self.bow_charge_mult)
        if charging:
            self.bow_charge = min(self.bow_charge + 1, cmax)
        else:
            if self.bow_timer <= 0:
                if self.bow_charge > 8:
                    dmg = WEAPON_PROFILES["bow"]["charge_dmg"]
                    spd = 10 + self.bow_charge // 8
                    gy = w_ground_y(self.w)
                    self.arrows.append(Arrow(self.x + 15 * SX * self.facing, gy - 30 * SY,
                                             self.facing, damage=dmg, speed=spd, lane=self.w))
                    if self.has_double_nock:
                        self.arrows.append(Arrow(self.x + 15 * SX * self.facing, gy - 34 * SY,
                                                 self.facing, damage=dmg, speed=spd - 1, lane=self.w))
                    self.bow_timer = WEAPON_PROFILES["bow"]["bow_cd"]
                    play("arrow")
                elif self.bow_held_last and self.bow_charge <= 2:
                    dmg = WEAPON_PROFILES["bow"]["quick_shot_dmg"]
                    gy = w_ground_y(self.w)
                    self.arrows.append(Arrow(self.x + 15 * SX * self.facing, gy - 30 * SY,
                                             self.facing, damage=dmg, speed=12, lane=self.w))
                    self.bow_timer = WEAPON_PROFILES["bow"]["bow_cd"] // 2
                    play("arrow")
            self.bow_charge = 0
        self.bow_held_last = charging

    def try_crossbow(self, fan=False):
        if self.hitstun > 0 or self.blocking:
            return
        if self.weapon != "crossbow":
            return
        wp = WEAPON_PROFILES["crossbow"]
        if fan and self.has_crossbow_fan:
            if self.fan_cd > 0:
                return
            self.fan_cd = wp["fan_cd"]
            for spread in (-0.15, 0, 0.15):
                gy = w_ground_y(self.w)
                a = Arrow(self.x + 15 * SX * self.facing, gy - 28 * SY + spread * 20 * SY,
                          self.facing, damage=wp["bolt_dmg"], speed=12,
                          col=BOLT_COL, tip_col=(180, 255, 180), pierce=True, lane=self.w)
                a.vy = spread * 3 * SY
                self.arrows.append(a)
            play("bolt")
            return
        if self.xbow_timer > 0:
            return
        lo, hi = wp["bolt_dmg"]
        dmg = (int(lo * self.bolt_dmg_mult), int(hi * self.bolt_dmg_mult))
        self.xbow_timer = wp["bolt_cd"]
        self.xbow_cock = 12
        pierce_n = self.bolt_pierce
        gy = w_ground_y(self.w)
        self.arrows.append(Arrow(self.x + 15 * SX * self.facing, gy - 28 * SY, self.facing,
                                 damage=dmg, speed=14, col=BOLT_COL, tip_col=(180, 255, 180),
                                 pierce=True, max_pierce=pierce_n, lane=self.w))
        play("bolt")

    def _deal_melee_hit(self, enemies, particles, profile, style, swing_id, multi=1):
        reach = profile["reach"]
        ox = 12 * SX if self.facing == 1 else -(reach + 4) * SX
        r = pygame.Rect(self.x + ox, self.y - 50 * SY, reach * SX, 52 * SY)
        lo, hi = profile["dmg"]
        if self.parry_counter > 0:
            lo = int(lo * self.parry_counter_mult)
            hi = int(hi * self.parry_counter_mult)
            self.parry_counter = 0
        if self.weapon == "sword":
            lo = int(lo * self.sword_dmg_mult)
            hi = int(hi * self.sword_dmg_mult)
        hits = 0
        max_hits = profile.get("multi", multi)
        all_lanes = w_melee_all_lanes(style)
        whiffed = False
        for e in enemies:
            if not e.alive:
                continue
            if getattr(e, "last_player_swing", -1) == swing_id:
                continue
            if hasattr(e, "blocks_hit") and e.blocks_hit(self):
                continue
            if not w_can_hit(self.w, e.w, all_lanes=all_lanes):
                if r.colliderect(e.rect()):
                    whiffed = True
                continue
            if r.colliderect(e.rect()):
                e.last_player_swing = swing_id
                dmg = random.randint(lo, hi)
                # Depth-step strike: brief bonus after Q/E onto / near target lane
                if self.w_step_anim > 0 and w_lane_gap(self.w, e.w) == 0:
                    dmg = max(1, int(dmg * W_STEP_STRIKE_MULT))
                e.hp -= dmg
                e.hurt_flash = 14
                e.hit_react = 14
                if profile.get("trip") and getattr(e, "etype", "") == "skirmisher":
                    e.hitstun = max(getattr(e, "hitstun", 0), 18)
                if profile.get("break_block"):
                    e.shield_broken = getattr(e, "shield_broken", 0) + 30
                kb = profile.get("kb", 6.0)
                e.vx = kb * SX * self.facing
                e.vy = -4.8 * SY
                fr, sh = profile.get("freeze", 3), profile.get("shake", (7, 9))
                play("hit")
                combat_freeze(fr)
                combat_shake(*sh)
                for _ in range(11):
                    particles.append(Particle(e.x, e.y - 20 * SY, BLOOD_COL,
                                              vx=random.uniform(-3, 3) * SX, vy=random.uniform(-4, -0.5) * SY))
                hits += 1
                if hits >= max_hits:
                    break
        if whiffed and hits == 0:
            particles.append(Particle(self.x + 20 * SX * self.facing, w_ground_y(self.w) - 35 * SY,
                                      (140, 130, 120), vx=random.uniform(-1, 1) * SX,
                                      vy=random.uniform(-2, 0) * SY, life=8, size=2))

    def update(self, keys, enemies, particles, shift_held=False):
        if self.combo_timer > 0:
            self.combo_timer -= 1
            if self.combo_timer <= 0:
                self.combo_step = 0
        self.handle_input(keys, shift_held=shift_held)
        self.regen_slow_meter()
        if self.sword_cd > 0:
            self.sword_cd -= 1
        if self.melee_cd > 0:
            self.melee_cd -= 1
        if self.fan_cd > 0:
            self.fan_cd -= 1

        wp = WEAPON_PROFILES["sword"]
        if self.sword_anim > 0:
            self.sword_anim -= 1
            if wp["active_lo"] <= self.sword_anim <= wp["active_hi"]:
                mv = wp["moves"].get(self.attack_style, wp["moves"]["slash"])
                self.x += mv.get("lunge", 1.0) * SX * self.facing
        if self.melee_anim > 0:
            self.melee_anim -= 1

        if self.bow_timer > 0:
            self.bow_timer -= 1
        if self.xbow_timer > 0:
            self.xbow_timer -= 1
        if self.xbow_cock > 0:
            self.xbow_cock -= 1

        self.physics()
        if self.hitstun > 0:
            self.hitstun -= 1
            self.vx *= 0.82
            if self.on_ground:
                self.vx *= 0.88

        if self.weapon == "sword" and wp["active_lo"] <= self.sword_anim <= wp["active_hi"]:
            mv = wp["moves"].get(self.attack_style, wp["moves"]["slash"])
            self._deal_melee_hit(enemies, particles, mv, self.attack_style, self.swing_id,
                                 multi=mv.get("multi", 1))

        if self.melee_anim > 0 and self.melee_profile:
            if self.melee_active_lo <= self.melee_anim <= self.melee_active_hi:
                self._deal_melee_hit(enemies, particles, self.melee_profile, self.attack_style, self.swing_id)

        for arr in self.arrows:
            arr.update()
            for e in enemies:
                if e.alive and arr.alive:
                    ey = w_ground_y(e.w)
                    if abs(arr.x - e.x) < 15 * SX and ey - 55 * SY < arr.y < ey + 5 * SY:
                        if not w_can_hit(arr.w, e.w):
                            continue
                        if hasattr(e, "blocks_hit") and e.blocks_hit(self, projectile=True):
                            arr.alive = False
                            break
                        dmg = random.randint(*arr.damage)
                        e.hp -= dmg
                        e.hurt_flash = 10
                        e.hit_react = 10
                        play("hit")
                        combat_freeze(2)
                        combat_shake(4, 6)
                        for _ in range(6):
                            particles.append(Particle(e.x, e.y - 25 * SY, BLOOD_COL))
                        max_p = getattr(arr, "max_pierce", 2 if arr.pierce else 1)
                        if arr.pierce:
                            arr.hit_count += 1
                            if arr.hit_count >= max_p:
                                arr.alive = False
                        else:
                            arr.alive = False
                            break
        self.arrows = [a for a in self.arrows if a.alive]

    def draw(self, surf, w_peer=None):
        ap = 0.0
        if self.weapon == "sword" and self.sword_anim > 0:
            ap = self._sword_raw_phase()
        elif self.melee_anim > 0:
            ap = self._sword_raw_phase()
        bc = self.bow_charge / max(1, WEAPON_PROFILES["bow"]["charge_max"]) if self.weapon == "bow" else 0
        xba = (WEAPON_PROFILES["crossbow"]["bolt_cd"] - self.xbow_timer) / WEAPON_PROFILES["crossbow"]["bolt_cd"] if self.weapon == "crossbow" else 0
        react = self.hit_react / 14.0 if self.hit_react > 0 else 0.0
        block_amt = 1.0 if self.blocking else 0.0
        show_attack = ap if (self.weapon == "sword" or self.melee_anim > 0) else 0
        body_kw = dict(
            attack_progress=show_attack,
            bow_draw=bc, crossbow_aim=xba if self.weapon == "crossbow" else 0,
            attack_style=self.attack_style, hit_react_amt=react, block_amt=block_amt,
        )

        def _draw_inner(s):
            self.draw_body(s, **body_kw)

        # Adjacent W ghosts first (behind solid body) — show where Q/E lands
        for dw in (-1, 1):
            self.draw_w_slice_ghost(surf, int(self.w) + dw, alpha=30, body_kwargs=body_kw)
        self._with_projection(surf, _draw_inner)
        for a in self.arrows:
            a.draw(surf)

# ── Enemy ──────────────────────────────────────────────────────────────────────
class Enemy(Stickman):
    def __init__(self, x, y, etype="soldier"):
        arch = ENEMY_ARCHETYPES.get(etype, ENEMY_ARCHETYPES["soldier"])
        super().__init__(x, y, arch["col"], arch["size"])
        self.alive = True
        self.etype = etype
        self.arch = arch
        self.hp = arch["hp"]
        self.max_hp = self.hp
        self.atk_total = arch["atk_total"]
        self.atk_hit_frame = arch["atk_hit"]
        self.atk_timer = random.randint(40, 80)
        self.atk_active = 0
        self.atk_style = arch["atk_style"]
        self.telegraph = 0
        self.aim_draw = 0
        self.patrol_dir = random.choice([-1, 1])
        self.patrol_tick = 0
        self.aggro = False
        self.counted = False
        self.shoot_timer = random.randint(90, 160) if arch.get("ranged") else 99999
        self.e_arrows = []
        self.hitstun = 0
        self.dash_timer = 0
        self.shield_broken = 0
        self.echo_flash = 0
        self.echo_ap = 0.0
        self.echo_bow = 0.0
        self.echo_style = self.atk_style

    def blocks_hit(self, player, projectile=False):
        if w_lane_gap(self.w, player.w) > 1:
            return False
        if self.shield_broken > 0:
            self.shield_broken -= 1
            return False
        if not self.arch.get("blocks"):
            return False
        facing_player = (player.x - self.x) * self.facing > 0
        return facing_player and not projectile

    def update(self, player, particles):
        if self.echo_flash > 0:
            self.echo_flash -= 1

        if self.hitstun > 0:
            self.hitstun -= 1
            self.vx *= 0.7
            if self.lane_cd > 0:
                self.lane_cd -= 1
            self.physics()
            if self.hp <= 0:
                self.alive = False
            return

        lead = _echo_lead_frames(player)
        dx = player.x - self.x
        dist = abs(dx)
        if dist < 320 * SX:
            self.aggro = True
        if dist > 520 * SX:
            self.aggro = False

        arch = self.arch
        gb = arch.get("guard_break", False)

        if self.aggro:
            self.facing = 1 if dx > 0 else -1
            spd = arch["speed"] * SX

            if self.etype == "skirmisher" and self.dash_timer <= 0 and dist > 70 * SX and dist < 200 * SX:
                if random.random() < 0.02 and self.atk_active <= 0:
                    self.dash_timer = 14
            # Skirmishers hunt across the 5-lane W field (±1 step toward player, or feint)
            if self.etype == "skirmisher" and self.lane_cd <= 0 and random.random() < 0.018:
                gap = w_lane_gap(self.w, player.w)
                if gap > 0:
                    step = 1 if int(self.w) < int(player.w) else -1
                    nw = int(self.w) + step
                    if W_LANE_FAR <= nw <= W_LANE_NEAR:
                        self.w = nw
                        self.lane_cd = 28
                elif random.random() < 0.35:
                    # Same lane: occasional feint to FORE/BACK flank
                    feint = random.choice((-1, 1))
                    nw = int(self.w) + feint
                    if W_LANE_FAR <= nw <= W_LANE_NEAR:
                        self.w = nw
                        self.lane_cd = 32
            if self.lane_cd > 0:
                self.lane_cd -= 1
            if self.dash_timer > 0:
                self.dash_timer -= 1
                self.vx = spd * 1.8 * self.facing
            elif self.atk_active > 0 or self.aim_draw > 0:
                self.vx = 0
            elif arch.get("ranged") and self.aim_draw == 0 and self.shoot_timer <= 25:
                self.vx = -0.9 * SX * self.facing
            else:
                stop_dist = 45 * SX
                if self.etype == "shielder":
                    stop_dist = 38 * SX
                self.vx = spd * self.facing if dist > stop_dist else 0

            if self.atk_timer > 0:
                self.atk_timer -= 1
            melee_dist = 58 * SX if self.etype != "bruiser" else 52 * SX
            if dist < melee_dist and self.atk_timer <= 0 and self.atk_active <= 0 and self.aim_draw <= 0:
                self.atk_timer = 70 if self.etype == "bruiser" else 60
                self.atk_active = self.atk_total
                self.telegraph = 0

            if self.atk_active > 0:
                frames_to_hit = self.atk_active - self.atk_hit_frame
                if frames_to_hit == lead:
                    self.echo_flash = TIME_SPEC["echo_flash_frames"]
                    self.echo_ap = choreo_enemy_attack_progress(self.atk_hit_frame, self.atk_total)
                    self.echo_style = self.atk_style
                    self.echo_bow = 0.0
                self.atk_active -= 1
                tele_frame = self.atk_total - 7
                if self.atk_active == tele_frame:
                    self.telegraph = 5 if self.etype == "bruiser" else 4
                    for _ in range(4):
                        particles.append(Particle(
                            self.x + 14 * SX * self.facing, GROUND_Y - int(4 * SY),
                            (100, 82, 58), vx=random.uniform(-1.5, 1.5) * SX,
                            vy=random.uniform(-0.8, -0.1) * SY, life=12, size=2,
                        ))
                if self.telegraph > 0:
                    self.telegraph -= 1
                if self.atk_active == self.atk_hit_frame and dist < 68 * SX:
                    lo, hi = arch["dmg"]
                    dmg = random.randint(lo, hi)
                    apply_damage_to_player(player, dmg, self.facing, particles,
                                           guard_break=gb, attacker=self)

            if arch.get("ranged"):
                if self.shoot_timer > 0:
                    self.shoot_timer -= 1
                if self.shoot_timer <= 0 and dist > 90 * SX and self.atk_active <= 0:
                    if self.aim_draw < 22:
                        release_lead = max(1, 22 - lead)
                        if self.aim_draw == release_lead:
                            self.echo_flash = TIME_SPEC["echo_flash_frames"]
                            self.echo_ap = 0.0
                            self.echo_bow = 1.0
                            self.echo_style = self.atk_style
                        self.aim_draw += 1
                    else:
                        self.e_arrows.append(EnemyArrow(
                            self.x + 10 * SX * self.facing, w_ground_y(self.w) - 28 * SY,
                            self.facing, lane=self.w))
                        self.shoot_timer = random.randint(90, 160)
                        self.aim_draw = 0
                        play("arrow")
        else:
            self.patrol_tick += 1
            if self.patrol_tick > 120:
                self.patrol_dir = -self.patrol_dir
                self.patrol_tick = 0
            self.vx = self.patrol_dir * 1.2 * SX
            self.facing = self.patrol_dir

        for ea in self.e_arrows:
            ea.update()
            if ea.alive and abs(ea.x - player.x) < 16 * SX:
                py = w_ground_y(player.w)
                if py - 52 * SY < ea.y < py + 5 * SY:
                    if not w_can_hit(ea.w, player.w):
                        ea.alive = False
                        continue
                    apply_damage_to_player(player, random.randint(6, 12), ea.dir, particles,
                                           source="projectile", attacker=self, source_w=ea.w)
                    ea.alive = False
        self.e_arrows = [ea for ea in self.e_arrows if ea.alive]
        self.physics()
        if self.hp <= 0 and not self.counted:
            self.alive = False

    def draw(self, surf, w_peer=None):
        if not self.alive:
            return

        ap = choreo_enemy_attack_progress(self.atk_active, self.atk_total) if self.atk_active > 0 else 0.0
        react = self.hit_react / 14.0 if self.hit_react > 0 else 0.0
        bow = (self.aim_draw / 22.0) if self.arch.get("ranged") and self.aim_draw > 0 else 0.0
        body_kw = dict(
            attack_progress=ap if bow <= 0 else 0, bow_draw=bow,
            attack_style=self.atk_style, telegraph=1 if self.telegraph > 0 else 0,
            hit_react_amt=react,
        )

        def _draw_inner(s):
            if self.echo_flash > 0:
                flash_max = max(1, TIME_SPEC["echo_flash_frames"])
                alpha = int(95 * self.echo_flash / flash_max)
                self.draw_echo_pose(
                    s, attack_progress=self.echo_ap, bow_draw=self.echo_bow,
                    attack_style=self.echo_style, alpha=alpha,
                )
            self.draw_body(s, **body_kw)
            for ea in self.e_arrows:
                ea.draw(s)
            bw = int(36 * self.s * SY)
            bx = int(self.x - bw // 2)
            by = int(self.y - 65 * self.s * SY)
            bh = max(5, round(5 * SY))
            pygame.draw.rect(s, (80, 20, 20), (bx, by, bw, bh))
            pygame.draw.rect(s, (200, 60, 40), (bx, by, int(bw * max(0, self.hp / self.max_hp)), bh))
            lbl = self.arch.get("label", "")
            if lbl:
                t = FONT_SMALL.render(lbl, True, (210, 130, 220))
                s.blit(t, (bx - 2, by - int(14 * SY)))

        # Ghost toward player when gap==1 (reachable next Q/E) — keeps clutter low
        if w_peer is not None and w_lane_gap(self.w, w_peer) == 1:
            step = 1 if int(w_peer) > int(self.w) else -1
            self.draw_w_slice_ghost(surf, int(self.w) + step, alpha=46, body_kwargs=body_kw)
        self._with_projection(surf, _draw_inner)

# ── Boss: Sebastian Monroe ──────────────────────────────────────────────────────
class Boss(Stickman):
    PHASE_THRESHOLDS = [350, 150]

    def __init__(self, x, y):
        super().__init__(x, y, BOSS_COL, size=1.8)
        self.hp = self.max_hp = 600
        self.alive = True
        self.counted = False
        self.phase = 0
        self.action = "walk"
        self.action_timer = 120
        self.slam_progress = 0.0
        self.slam_active = False
        self.charge_windup = 0
        self.shoot_timer = 0
        self.e_arrows = []
        self.roar_done = False
        self.enrage_flash = 0
        self.intro_timer = 130
        self.pending_taunt = None
        self._last_phase = 0
        self.pattern_idx = 0
        self.pattern_queue = []
        self.telegraph_label = ""
        self.hitstun = 0
        self.atk_active = 0
        self.atk_hit_frame = 0
        self.w = W_LANE_MID
        self.boss_echo_label = ""
        self.echo_flash = 0
        self.echo_ap = 0.0
        self.echo_kind = ""

    def _peek_next_pattern_action(self):
        if not self.pattern_queue:
            queue = list(MONROE_PATTERNS.get(self.phase, MONROE_PATTERNS[0]))
            idx = 0
        else:
            queue = self.pattern_queue
            idx = self.pattern_idx
            if idx >= len(queue):
                idx = 0
        return queue[idx]

    def _parse_pattern_action(self, spec):
        if spec == "walk":
            self.action = "walk"
            self.action_timer = 80
        elif spec == "slam":
            self._begin_slam()
        elif spec == "charge":
            self.action = "charge"
            self.charge_windup = 18
            self.action_timer = 70
            self.telegraph_label = "CHARGE"
        elif spec.startswith("shoot:"):
            n = int(spec.split(":")[1])
            self._begin_shoot(n)
            self.telegraph_label = "SHOOT"

    def _advance_pattern(self):
        if not self.pattern_queue:
            self.pattern_queue = list(MONROE_PATTERNS.get(self.phase, MONROE_PATTERNS[0]))
            self.pattern_idx = 0
        if self.pattern_idx >= len(self.pattern_queue):
            self.pattern_idx = 0
        act = self.pattern_queue[self.pattern_idx]
        self.pattern_idx += 1
        self._parse_pattern_action(act)

    def update(self, player, particles):
        if self.intro_timer > 0:
            self.intro_timer -= 1
            self.vx = 0
            self.physics()
            return

        if not self.roar_done:
            play("boss_roar")
            self.roar_done = True

        if self.phase < 2 and self.hp <= self.PHASE_THRESHOLDS[self.phase]:
            self.phase += 1
            play("boss_roar")
            self.enrage_flash = 50
            if self.phase != self._last_phase:
                self._last_phase = self.phase
                taunts = MONROE_PHASE_TAUNTS
                if self.phase < len(taunts):
                    self.pending_taunt = taunts[self.phase]
                self.pattern_idx = 0
                self.pattern_queue = []

        if self.echo_flash > 0:
            self.echo_flash -= 1

        if self.hitstun > 0:
            self.hitstun -= 1
            self.vx = 0
            self.physics()
            return

        dx = player.x - self.x
        dist = abs(dx)
        self.facing = 1 if dx > 0 else -1
        if self.enrage_flash > 0:
            self.enrage_flash -= 1

        if self.action_timer > 0:
            self.action_timer -= 1
        else:
            self._advance_pattern()

        if self.action == "walk":
            self.telegraph_label = ""
            self.boss_echo_label = _pattern_action_label(self._peek_next_pattern_action())
            self.vx = 2.8 * SX * self.facing if dist > 70 * SX else 0
        elif self.action == "charge":
            self.boss_echo_label = ""
            if self.charge_windup > 0:
                if self.charge_windup == 18:
                    self.echo_flash = TIME_SPEC["echo_flash_frames"]
                    self.echo_kind = "charge"
                self.charge_windup -= 1
                self.vx = 0
            else:
                self.vx = 9 * SX * self.facing
                if dist < 60 * SX:
                    self._slam_hit(player, particles, (28, 45), guard_break=True)
                    self.action = "walk"
                    self.action_timer = 40
                    self.telegraph_label = ""
        elif self.action == "slam":
            self.boss_echo_label = ""
            self.vx = 0
            if self.slam_progress < 0.58:
                if self.slam_progress < 0.02:
                    self.echo_flash = TIME_SPEC["echo_flash_frames"]
                    self.echo_kind = "slam"
                self.slam_progress = min(0.58, self.slam_progress + 0.038)
                self.telegraph_label = "SLAM"
            else:
                self.slam_progress = min(1.0, self.slam_progress + 0.11)
            if self.slam_progress >= 1.0:
                self.atk_active = 1
                self._slam_hit(player, particles, (32, 52), guard_break=True)
                self.atk_active = 0
                self.slam_active = False
                self.slam_progress = 0.0
                self.action = "walk"
                self.action_timer = 30
                self.telegraph_label = ""
        elif self.action == "shoot":
            self.boss_echo_label = ""
            self.vx = 0

        if self.action == "shoot":
            if self.shoot_timer > 0:
                self.shoot_timer -= 1
            elif self.action_timer > 0:
                self.e_arrows.append(EnemyArrow(
                    self.x + 22 * SX * self.facing, w_ground_y(self.w) - 42 * SY,
                    self.facing, lane=self.w))
                self.shoot_timer = 14
                play("arrow")

        for ea in self.e_arrows:
            ea.update()
            if ea.alive and abs(ea.x - player.x) < 16 * SX:
                py = w_ground_y(player.w)
                if py - 52 * SY < ea.y < py + 5 * SY:
                    if not w_can_hit(ea.w, player.w):
                        ea.alive = False
                        continue
                    apply_damage_to_player(player, random.randint(14, 22), ea.dir, particles,
                                           source="projectile", attacker=self, source_w=ea.w)
                    ea.alive = False
        self.e_arrows = [ea for ea in self.e_arrows if ea.alive]
        self.physics()
        if self.hp <= 0 and not self.counted:
            self.alive = False

    def _begin_slam(self):
        self.action = "slam"
        self.action_timer = 45
        self.slam_progress = 0.0
        self.slam_active = True
        self.telegraph_label = "SLAM"

    def _begin_shoot(self, bursts):
        self.action = "shoot"
        self.action_timer = bursts * 18 + 10
        self.shoot_timer = 0

    def _slam_hit(self, player, particles, dmg, guard_break=True):
        if abs(player.x - self.x) < 110 * SX:
            if player.parry_active > 0:
                player.parry_active = 0
                player.parry_counter = DEFENSE_SPEC["parry_counter_frames"]
                self.hitstun = 12
                play("parry")
                combat_freeze(6)
                combat_shake(8, 10)
                combat_trigger_slowmo(
                    TIME_SPEC["parry_slow_frames"] + getattr(player, "slow_parry_bonus", 0),
                    TIME_SPEC["slow_scale"],
                )
            else:
                d = random.randint(*dmg)
                blocked = apply_damage_to_player(player, d, self.facing, particles,
                                                 guard_break=guard_break, attacker=self,
                                                 all_lanes=True)
                if not blocked or guard_break:
                    combat_freeze(5)
                    combat_shake(12, 14)
        for _ in range(22):
            particles.append(Particle(self.x + random.randint(-int(50 * SX), int(50 * SX)), GROUND_Y,
                                      random.choice(SPARK_COLS),
                                      vx=random.uniform(-5, 5) * SX, vy=random.uniform(-6, -0.5) * SY,
                                      life=random.randint(12, 28), size=random.randint(1, 3)))

    def draw(self, surf, w_peer=None):
        if not self.alive:
            return

        slam_p = self.slam_progress if self.slam_active else 0.0
        charge_amt = min(1.0, self.charge_windup / 18.0) if self.charge_windup > 0 else 0.0
        react = self.hit_react / 14.0 if self.hit_react > 0 else 0.0
        body_kw = dict(boss_slam=slam_p, charge_pose=charge_amt, hit_react_amt=react)

        def _draw_inner(s):
            if self.echo_flash > 0:
                flash_max = max(1, TIME_SPEC["echo_flash_frames"])
                alpha = int(90 * self.echo_flash / flash_max)
                if self.echo_kind == "slam":
                    self.draw_echo_pose(s, boss_slam=0.55, alpha=alpha)
                elif self.echo_kind == "charge":
                    self.draw_echo_pose(s, charge_pose=1.0, alpha=alpha)
            saved = self.col
            if self.enrage_flash > 0 and self.enrage_flash % 6 < 3:
                self.col = (255, 255, 50)
            self.draw_body(s, **body_kw)
            self.col = saved
            for ea in self.e_arrows:
                ea.draw(s)

        if w_peer is not None and w_lane_gap(self.w, w_peer) == 1:
            step = 1 if int(w_peer) > int(self.w) else -1
            self.draw_w_slice_ghost(surf, int(self.w) + step, alpha=40, body_kwargs=body_kw)
        self._with_projection(surf, _draw_inner)

        bw = int(320 * SX)
        bx = (WIDTH - bw) // 2
        by = int(8 * SY)
        bh = max(14, int(round(18 * SY)))
        pygame.draw.rect(surf, (60, 15, 15), (bx, by, bw, bh), border_radius=max(2, round(4 * SY)))
        fill = int(bw * max(0, self.hp / self.max_hp))
        pc = [(220, 40, 30), (200, 90, 20), (220, 190, 20)][self.phase]
        pygame.draw.rect(surf, pc, (bx, by, fill, bh), border_radius=max(2, round(4 * SY)))
        for pct in [350 / 600, 150 / 600]:
            mx = bx + int(bw * pct)
            pygame.draw.line(surf, (255, 255, 80), (mx, by), (mx, by + bh), LW)
        lbl = FONT_MED.render(f"MONROE  {max(0, self.hp)} / {self.max_hp}", True, (255, 180, 100))
        surf.blit(lbl, (WIDTH // 2 - lbl.get_width() // 2, by + 1))

        if self.telegraph_label and self.intro_timer <= 0:
            tt = FONT_MED.render(self.telegraph_label, True, (255, 220, 100))
            surf.blit(tt, (WIDTH // 2 - tt.get_width() // 2, by + bh + int(6 * SY)))

        if self.action == "walk" and self.boss_echo_label and self.intro_timer <= 0:
            echo_txt = FONT_SMALL.render(f"ECHO → {self.boss_echo_label}", True, (70, 200, 245))
            surf.blit(echo_txt, (WIDTH // 2 - echo_txt.get_width() // 2, by + bh + int(28 * SY)))

        if self.intro_timer > 0:
            t1 = FONT_BIG.render("SEBASTIAN MONROE", True, (220, 50, 30))
            t2 = FONT_SMALL.render("President of the Monroe Republic", True, (180, 80, 60))
            t3 = FONT_TINY.render(f"He knows {HERO_NAME}. He knows why you came.", True, (160, 100, 80))
            surf.blit(t1, (WIDTH // 2 - t1.get_width() // 2, HEIGHT // 2 - int(60 * SY)))
            surf.blit(t2, (WIDTH // 2 - t2.get_width() // 2, HEIGHT // 2 - int(20 * SY)))
            surf.blit(t3, (WIDTH // 2 - t3.get_width() // 2, HEIGHT // 2 + int(8 * SY)))

# ── Background & HUD ───────────────────────────────────────────────────────────
def draw_lane_depth_guides(surf):
    """Perspective lane bands for 5-lane FAR→NEAR depth."""
    for w in range(W_LANE_COUNT):
        gy = w_ground_y(w)
        if w == W_LANE_MID:
            col = (48, 40, 30)
        elif w in (W_LANE_BACK, W_LANE_FORE):
            col = (38, 33, 26)
        else:
            col = (30, 27, 22)
        pygame.draw.line(surf, col, (int(40 * SX), gy), (WIDTH - int(40 * SX), gy), max(1, LW))
        lbl = FONT_TINY.render(W_LANE_LABELS[w], True, (70, 62, 52))
        surf.blit(lbl, (int(8 * SX), gy - int(16 * SY)))


def draw_background(surf, buildings, fire_parts, advance_fire=True):
    for i in range(HEIGHT):
        t=i/HEIGHT
        pygame.draw.line(surf,(int(18+22*t),int(14+14*t),int(10+8*t)),(0,i),(WIDTH,i))
    mx=int(WIDTH*0.75); my=int(70*SY)
    pygame.draw.circle(surf,(200,195,160),(mx,my),max(20, round(28*SY)))
    pygame.draw.circle(surf,(18,14,10),(mx+int(10*SX),my-int(5*SY)),max(16, round(22*SY)))
    random.seed(42)
    nstars=max(80, int(80*SX*SY))
    ycap=int(160*SY)
    for _ in range(nstars):
        sx,sy_=random.randint(0,WIDTH),random.randint(0,ycap); a=random.randint(80,220)
        pygame.draw.circle(surf,(a,a,int(a*0.9)),(sx,sy_),max(1, round(SY)))
    random.seed()
    for bx,bw,bh in buildings:
        pygame.draw.rect(surf,(22,17,12),(bx,GROUND_Y-bh,bw,bh))
        stepx=max(12, round(18*SX)); stepy=max(14, round(20*SY))
        padx=max(5, round(6*SX)); pady=max(8, round(10*SY))
        for wx in range(bx+padx,bx+bw-padx,stepx):
            for wy in range(GROUND_Y-bh+pady,GROUND_Y-pady,stepy):
                wc=(80,60,20) if random.random()<0.12 else (12,10,8)
                pygame.draw.rect(surf,wc,(wx,wy,max(8,round(10*SX)),max(10,round(12*SY))))
    pygame.draw.rect(surf,GROUND_COL,(0,GROUND_Y,WIDTH,HEIGHT-GROUND_Y))
    pygame.draw.line(surf,GROUND_LINE,(0,GROUND_Y),(WIDTH,GROUND_Y),LW)
    draw_lane_depth_guides(surf)
    gst=max(28, round(40*SX))
    goff=max(4, round(5*SY))
    for i in range(0,WIDTH,gst):
        pygame.draw.line(surf,(35,28,20),(i,GROUND_Y+goff),(i+int(20*SX),GROUND_Y+goff),max(1,LW-1))
    for p in fire_parts:
        if advance_fire:
            p.update()
        p.draw(surf)
    if advance_fire:
        fire_parts[:] = [p for p in fire_parts if p.life > 0]

def draw_hud(surf, player, wave_lbl, enemy_count, high_score, checkpoint_wave, scrap=0,
             death_rewind_window=0):
    hx,hy=int(20*SX),int(20*SY)
    hw,hh=int(180*SX),int(18*SY)
    pygame.draw.rect(surf,(40,20,10),(hx,hy,hw,hh),border_radius=max(3, round(4*SY)))
    hf=int((hw-2)*max(0,player.hp)/player.max_hp)
    hc=(180,50,30) if player.hp<30 else (160,200,80) if player.hp>70 else (220,160,30)
    iy=hy+int(1*SY); ih=max(12, hh-int(2*SY))
    pygame.draw.rect(surf,hc,(hx+1,iy,hf,ih),border_radius=max(2, round(3*SY)))
    surf.blit(FONT_SMALL.render(f"HP {max(0,player.hp)}/{player.max_hp}",True,HUD_COL),(hx+int(4*SX),hy+int(3*SY)))

    wm={"sword":"[1] SWORD","bow":"[2] BOW  ","crossbow":"[3] XBOW"}
    wc={"sword":HUD_COL,"bow":ARROW_COL,"crossbow":BOLT_COL}
    surf.blit(FONT_SMALL.render(wm[player.weapon],True,wc[player.weapon]),(hx,hy+int(24*SY)))
    surf.blit(FONT_SMALL.render(f"SCRAP: {scrap}", True, (180, 160, 90)), (hx, hy + int(40 * SY)))
    if player.blocking:
        surf.blit(FONT_TINY.render("BLOCK", True, (150, 200, 255)), (hx + int(100 * SX), hy + int(40 * SY)))
    if player.dodge_cd > 0:
        surf.blit(FONT_TINY.render(f"DODGE {player.dodge_cd}", True, (120, 180, 220)), (hx + int(100 * SX), hy + int(52 * SY)))
    elif player.can_dodge:
        surf.blit(FONT_TINY.render("DODGE ready", True, (100, 160, 200)), (hx + int(100 * SX), hy + int(52 * SY)))
    if player.parry_counter > 0:
        surf.blit(FONT_TINY.render("RIPOSTE!", True, (255, 220, 100)), (hx, hy + int(54 * SY)))

    lane_y = hy + int(68 * SY)
    lane_step = int(34 * SX)
    for i, name in enumerate(W_LANE_LABELS):
        active = int(player.w) == i
        col = (220, 200, 120) if active else (75, 68, 58)
        txt = f"[{name}]" if active else name
        surf.blit(FONT_TINY.render(txt, True, col), (hx + i * lane_step, lane_y))
    # Reachable adjacent lanes (Q/E) — faint markers under active
    for dw in (-1, 1):
        adj = int(player.w) + dw
        if W_LANE_FAR <= adj <= W_LANE_NEAR:
            mark = FONT_TINY.render("·", True, (110, 100, 80))
            surf.blit(mark, (hx + adj * lane_step + int(10 * SX), lane_y + int(10 * SY)))

    meter_max = max(1.0, getattr(player, "slow_meter_max", TIME_SPEC["meter_max"]))
    meter_y = lane_y + int(22 * SY)
    mw, mh = int(120 * SX), max(5, round(6 * SY))
    pygame.draw.rect(surf, (25, 30, 40), (hx, meter_y, mw, mh), border_radius=max(2, round(3 * SY)))
    fill = int(mw * max(0, min(1, player.slow_meter / meter_max)))
    mc = (90, 210, 255) if TIME_SLOW_FRAMES > 0 else (55, 140, 190)
    if fill > 0:
        pygame.draw.rect(surf, mc, (hx, meter_y, fill, mh), border_radius=max(2, round(3 * SY)))
    stutter = "STUTTER" if TIME_SLOW_FRAMES > 0 else "GRID"
    surf.blit(FONT_TINY.render(f"{stutter} T", True, (100, 185, 220)), (hx + mw + int(6 * SX), meter_y - int(1 * SY)))

    if getattr(player, "can_rewind", False) and player.rewind_max > 0:
        rw_y = meter_y + int(14 * SY)
        for i in range(player.rewind_max):
            filled = i < player.rewind_charges
            col = (190, 110, 255) if filled else (42, 36, 52)
            pygame.draw.circle(surf, col, (hx + int(8 * SX) + i * int(14 * SX), rw_y), max(4, round(5 * SY)))
        surf.blit(
            FONT_TINY.render("REWIND R", True, (145, 105, 200)),
            (hx + int(8 * SX) + player.rewind_max * int(14 * SX) + int(4 * SX), rw_y - int(7 * SY)),
        )

    if "BOSS" not in wave_lbl:
        wt=FONT_MED.render(wave_lbl,True,HUD_COL)
        surf.blit(wt,(WIDTH//2-wt.get_width()//2,int(14*SY)))
        et=FONT_SMALL.render(f"Enemies: {enemy_count}",True,(180,130,80))
        surf.blit(et,(WIDTH//2-et.get_width()//2,int(38*SY)))

    rx=int(150*SX)
    surf.blit(FONT_SMALL.render(f"KILLS: {player.kills}",True,HUD_DIM),(WIDTH-rx,hy))
    surf.blit(FONT_SMALL.render(f"BEST:  {high_score}",True,(160,130,60)),(WIDTH-rx,hy+int(16*SY)))

    if player.weapon=="sword":
        sword_cd_max = WEAPON_PROFILES["sword"]["cd_max"]
        cd=player.sword_cd/max(1,int(sword_cd_max*player.sword_cd_mult)) if player.sword_cd>0 else 0
        cy=hy+int(36*SY); cw,ch=int(130*SX),max(5, round(6*SY))
        pygame.draw.rect(surf,(40,30,15),(WIDTH-rx,cy,cw,ch),border_radius=max(2, round(3*SY)))
        pygame.draw.rect(surf,(220,180,60),(WIDTH-rx,cy,int(cw*(1-cd)),ch),border_radius=max(2, round(3*SY)))
        surf.blit(FONT_SMALL.render("SWING CD",True,HUD_DIM),(WIDTH-rx,cy+ch+int(2*SY)))
    elif player.weapon=="crossbow":
        xcd = WEAPON_PROFILES["crossbow"]["bolt_cd"]
        cd=player.xbow_timer/xcd if player.xbow_timer>0 else 0
        cy=hy+int(36*SY); cw,ch=int(130*SX),max(5, round(6*SY))
        pygame.draw.rect(surf,(20,40,20),(WIDTH-rx,cy,cw,ch),border_radius=max(2, round(3*SY)))
        pygame.draw.rect(surf,BOLT_COL,(WIDTH-rx,cy,int(cw*(1-cd)),ch),border_radius=max(2, round(3*SY)))
        surf.blit(FONT_SMALL.render("BOLT CD ",True,HUD_DIM),(WIDTH-rx,cy+ch+int(2*SY)))

    if checkpoint_wave is not None:
        ct=FONT_SMALL.render(f"CKPT: Wave {checkpoint_wave+1}",True,(100,200,100))
        surf.blit(ct,(hx,HEIGHT-int(22*SY)))

    hint=FONT_SMALL.render("Q/E depth  ·  Shift block/parry  ·  S dodge  ·  T slow  ·  R rewind",True,(95,78,58))
    surf.blit(hint,(WIDTH//2-hint.get_width()//2,HEIGHT-int(20*SY)))

    if death_rewind_window > 0 and player.hp <= 0 and player.rewind_charges > 0:
        pulse = 0.75 + 0.25 * math.sin(pygame.time.get_ticks() * 0.02)
        msg = FONT_MED.render("BLACKOUT REWIND — press R", True,
                              (int(200 * pulse), int(120 * pulse), 255))
        surf.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - int(10 * SY)))

def draw_intro(surf, high_score, checkpoint_wave, t_ms=0):
    global _INTRO_BG_CACHE
    if _INTRO_BG_CACHE is None:
        _INTRO_BG_CACHE = _make_intro_background()
    surf.blit(_INTRO_BG_CACHE, (0, 0))

    def Y(y):
        return int(y * SY)

    cx = WIDTH // 2
    gold = (232, 198, 118)
    gold_dim = (180, 150, 95)
    muted = (145, 128, 108)
    cream = (235, 228, 212)

    # Decorative rule + corner ticks
    rule_w = int(min(520 * SX, WIDTH * 0.72))
    ry = Y(168)
    pygame.draw.line(surf, (90, 70, 45), (cx - rule_w // 2, ry), (cx + rule_w // 2, ry), max(1, round(SY)))
    pygame.draw.line(surf, gold_dim, (cx - rule_w // 2, ry + 1), (cx + rule_w // 2, ry + 1), max(1, round(SY)))
    tick = max(10, int(14 * SY))
    for dx in (-rule_w // 2, rule_w // 2 - tick):
        pygame.draw.line(surf, gold, (cx + dx, ry - tick), (cx + dx + tick, ry), 2)
        pygame.draw.line(surf, gold, (cx + dx, ry + tick), (cx + dx + tick, ry), 2)

    title = "REVOLUTION"
    ty = Y(108)
    # Soft glow pass (wider, dimmer)
    glow_c = (40, 32, 18)
    for ox, oy in ((4, 4), (-3, 3), (3, -2)):
        g = FONT_TITLE.render(title, True, glow_c)
        surf.blit(g, (cx - g.get_width() // 2 + ox, ty + oy))
    hi = FONT_TITLE.render(title, True, (255, 235, 170))
    lo = FONT_TITLE.render(title, True, (200, 155, 70))
    surf.blit(lo, (cx - hi.get_width() // 2, ty + 1))
    surf.blit(hi, (cx - hi.get_width() // 2, ty))

    tag = FONT_MED.render("No Electricity  ·  No Mercy", True, cream)
    surf.blit(tag, (cx - tag.get_width() // 2, Y(182)))

    hero = FONT_SMALL.render(f"You are  {HERO_NAME}  —  chalk north for {HERO_LOST_NAME}", True, gold_dim)
    surf.blit(hero, (cx - hero.get_width() // 2, Y(208)))

    # Controls panel
    panel_top, panel_h = Y(248), int(202 * SY)
    panel_w = int(min(620 * SX, WIDTH - 80))
    px = cx - panel_w // 2
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((8, 6, 12, 168))
    br = max(6, round(8 * SY))
    pygame.draw.rect(panel, (212, 168, 75, 55), panel.get_rect(), width=1, border_radius=br)
    surf.blit(panel, (px, panel_top))

    lines = [
        "A/D  move   ·   W / Space  jump   ·   S  dodge",
        "Q  depth back (FAR)   ·   E  depth forward (NEAR)   ·   5 lanes",
        "J / LMB  attack   ·   K (hold)  bow   ·   L  crossbow / fan",
        "Shift hold  block   ·   Shift tap  parry   ·   1/2/3  weapons",
        "Combat: hold T  Grid stutter (slow-mo)  ·  cyan echoes = incoming hits",
        "Tier 4+: R  Blackout rewind (1 charge/sector)  ·  Rewind Cell perk +1",
        "World map: sectors + Monroe  ·   I  Armory (after 1st clear)",
        "F11  fullscreen   ·   [  ]  volume   ·   T  trailer",
    ]
    ly = panel_top + int(14 * SY)
    for line in lines:
        s = FONT_SMALL.render(line, True, muted)
        surf.blit(s, (cx - s.get_width() // 2, ly))
        ly += int(22 * SY)

    _blit_shadow_text(surf, FONT_MED, "ENTER  —  World map  (campaign)", gold, cx, Y(382), off=2, shadow_rgb=(0, 0, 0))

    # Coming soon pill (subtle pulse)
    pulse = 0.88 + 0.12 * math.sin(t_ms * 0.004)
    pill_txt = FONT_SMALL.render("COMING SOON", True, (24, 18, 12))
    sub_studio = FONT_TINY.render("43 Industries", True, (90, 78, 62))
    pill_pad_x, pill_pad_y = int(28 * SX), int(10 * SY)
    pill_w = max(pill_txt.get_width(), sub_studio.get_width()) + pill_pad_x * 2
    pill_h = pill_txt.get_height() + sub_studio.get_height() + pill_pad_y * 2 + int(4 * SY)
    pill_x = cx - pill_w // 2
    pill_y = Y(408)
    glow_pad = int(14 * SY)
    glow_a = int(72 * pulse)
    glow_s = pygame.Surface((pill_w + glow_pad * 2, pill_h + glow_pad * 2), pygame.SRCALPHA)
    pygame.draw.rect(
        glow_s,
        (212, 170, 90, glow_a),
        glow_s.get_rect(),
        border_radius=br + 6,
    )
    surf.blit(glow_s, (pill_x - glow_pad, pill_y - glow_pad))
    pill_surf = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
    inner = (240, 210, 120) if pulse > 0.94 else (220, 185, 100)
    pygame.draw.rect(pill_surf, (*inner, 255), (0, 0, pill_w, pill_h), border_radius=br)
    pygame.draw.rect(pill_surf, (255, 245, 200, int(200 * pulse)), (0, 0, pill_w, pill_h), width=2, border_radius=br)
    surf.blit(pill_surf, (pill_x, pill_y))
    surf.blit(pill_txt, (pill_x + (pill_w - pill_txt.get_width()) // 2, pill_y + pill_pad_y))
    surf.blit(
        sub_studio,
        (pill_x + (pill_w - sub_studio.get_width()) // 2, pill_y + pill_pad_y + pill_txt.get_height() + int(2 * SY)),
    )

    if checkpoint_wave is not None:
        _blit_shadow_text(
            surf,
            FONT_MED,
            f"C  Continue from Wave {checkpoint_wave + 1}",
            (118, 218, 138),
            cx,
            Y(484),
            off=2,
        )

    hs = FONT_SMALL.render(f"High Score  {high_score}  kills", True, gold_dim)
    surf.blit(hs, (cx - hs.get_width() // 2, Y(514)))

    ex = FONT_SMALL.render("ESC  —  Exit", True, (120, 105, 88))
    surf.blit(ex, (cx - ex.get_width() // 2, Y(542)))

def draw_gameover(surf,player,high_score,win=False,sectors_cleared=None):
    sectors_cleared = sectors_cleared or []
    ov=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    ov.fill((0,0,0,165)); surf.blit(ov,(0,0))
    cx=WIDTH//2
    if win:
        _blit_shadow_text(surf,FONT_BIG,"VICTORY — MONROE DEFEATED",(130,230,115),cx,int(165*SY),off=3)
        sub=FONT_MED.render(_story_victory_line(),True,(100,180,80))
    else:
        _blit_shadow_text(surf,FONT_BIG,"YOU FELL",(220,75,55),cx,int(165*SY),off=3)
        sub=FONT_MED.render(_story_death_line(sectors_cleared),True,(160,80,60))
    kl =FONT_MED.render(f"Enemies defeated: {player.kills}",True,HUD_COL)
    bst=FONT_MED.render(f"High Score: {high_score} kills",True,(160,130,60))
    mm =FONT_MED.render("M  Main menu",True,(140,155,100))
    rs =FONT_MED.render("R  Restart   |   ESC  Quit",True,(140,120,80))
    for txt,y in[(sub,int(222*SY)),(kl,int(288*SY)),(bst,int(323*SY)),(mm,int(358*SY)),(rs,int(395*SY))]:
        surf.blit(txt,(cx-txt.get_width()//2,y))

def draw_pause_overlay(surf, master_vol):
    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 150))
    surf.blit(ov, (0, 0))
    cx, cy = WIDTH // 2, HEIGHT // 2
    bw, bh = int(440 * SX), int(220 * SY)
    bx, by = cx - bw // 2, cy - bh // 2
    panel = pygame.Surface((bw, bh), pygame.SRCALPHA)
    panel.fill((12, 10, 16, 200))
    br = max(8, round(10 * SY))
    pygame.draw.rect(panel, (212, 168, 75, 90), panel.get_rect(), width=1, border_radius=br)
    surf.blit(panel, (bx, by))

    pct = int(round(master_vol * 100))
    _blit_shadow_text(surf, FONT_BIG, "PAUSED", (235, 210, 130), cx, cy - int(88 * SY), off=3)
    t2 = FONT_MED.render(f"Volume  {pct}%    [  ]  adjust", True, (175, 155, 105))
    surf.blit(t2, (cx - t2.get_width() // 2, cy - int(28 * SY)))
    t3 = FONT_SMALL.render("RESUME  —  ESC or P", True, (120, 200, 130))
    t4 = FONT_SMALL.render("MAIN MENU  —  M", True, (170, 145, 95))
    t5 = FONT_SMALL.render("QUIT  —  Q", True, (190, 105, 85))
    for t, dy in [(t3, 28), (t4, 58), (t5, 86)]:
        surf.blit(t, (cx - t.get_width() // 2, cy + dy))

# ── Wave config ────────────────────────────────────────────────────────────────
BOSS_WAVE = len(SECTOR_SPAWNS)

def spawn_wave(idx):
    idx = max(0, min(idx, len(SECTOR_SPAWNS) - 1))
    cfg = SECTOR_SPAWNS[idx]
    out = []
    slot = 0
    for etype, count in cfg.items():
        for i in range(count):
            side = 1 if slot % 2 == 0 else -1
            slot += 1
            o80, o60 = 80 * SX, 60 * SX
            o220 = 220 * SX
            spread = i * o60
            if etype == "commander":
                ex = WIDTH + o220 + spread if side == 1 else -o220 - spread
            else:
                ex = WIDTH + o80 + spread if side == 1 else -o80 - spread
            out.append(Enemy(ex, GROUND_Y, etype))
            lane = W_LANE_MID
            if idx >= 1:
                lane = slot % W_LANE_COUNT
            if etype == "commander" and idx >= 2:
                # Commanders hold the backfield
                lane = W_LANE_FAR if slot % 2 == 0 else W_LANE_BACK
            if etype == "skirmisher":
                # Skirmishers prefer the front three lanes
                lane = (W_LANE_MID, W_LANE_FORE, W_LANE_NEAR)[slot % 3]
            if etype == "bruiser" and idx >= 3:
                lane = W_LANE_FORE if slot % 2 else W_LANE_MID
            out[-1].w = lane
    return out

# ── Campaign story (shared with Godot via story/campaign_story.json) ───────────
def _load_campaign_story():
    """Load shared story JSON; fall back to embedded defaults if missing."""
    paths = [
        Path(__file__).resolve().parent / "story" / "campaign_story.json",
        Path(__file__).resolve().parent / "RevolutionGodot" / "data" / "campaign_story.json",
    ]
    for p in paths:
        try:
            if p.is_file():
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
    return None


_STORY = _load_campaign_story() or {}

HERO_NAME = _STORY.get("hero_name", "Ash Trace")
HERO_LOST_NAME = _STORY.get("hero_lost_name", "Mira")  # sibling taken north

PROLOGUE_LINES = list(_STORY.get("prologue") or [
    f"My name is {HERO_NAME}. Fifteen years since the lights died — I still see them when I close my eyes.",
    "I wore Monroe's colors once. I don't anymore.",
    f"Someone I loved — {HERO_LOST_NAME} — was taken to Philadelphia. I follow the chalk north.",
    "Arrows in my own hand, I swear. The war map isn't strategy. It's the only road left.",
])

_SECTORS = list(_STORY.get("sectors") or [])
if _SECTORS:
    SECTOR_BRIEFINGS = [list(s.get("briefing") or []) for s in _SECTORS]
    SECTOR_CLEAR_LINES = [str(s.get("clear") or "") for s in _SECTORS]
    SECTOR_BLURB_AFTER = [str(s.get("blurb_after") or "") for s in _SECTORS]
    SECTOR_RADIO = [list(s.get("radio") or []) for s in _SECTORS]
else:
    SECTOR_BRIEFINGS = [
        ["THE FRINGE — edge of what's left.",
         "Militia patrols treat these roads like property. I used to walk them in their colors.",
         "Break through. Chalk arrows point north — my handwriting, or a ghost of it."],
        ["DEAD GRID — substation country.",
         "Every wire is cold. Every tower is silent. My head still aches near the concrete.",
         "Locals swear something hums below. I believe them. The grid remembers."],
        ["ASH CORRIDOR — smoke on the horizon.",
         "Commanders push forward. Orders coordinated. Someone upstream is planning this.",
         f"I burned this name into the dirt once. Now I cut through it for {HERO_LOST_NAME}."],
        ["BROKEN LINE — refugee track.",
         "Families fled north until the Militia closed the crossing. I was there. I followed orders.",
         f"{HERO_LOST_NAME} was loaded onto a Republic wagon. I didn't stop it. I quit that night."],
        ["IRON MARCH — open ground.",
         "Full companies. Full authorization. They're not patrolling — they're hunting.",
         "Some of them still remember my face from the uniform. Good. Let them."],
        ["THE LAST GATE — last settlement before the capital.",
         "Turn back and live. Push through and the Republic answers.",
         f"No reinforcements. Just me — and whatever's left of who I was before I lost {HERO_LOST_NAME}."],
        ["PHILADELPHIA — Monroe Citadel.",
         "President Sebastian Monroe built an empire on the blackout. I once carried his orders.",
         f"End this. Find {HERO_LOST_NAME}. Or die in the shadow of his towers."],
    ]
    SECTOR_CLEAR_LINES = [
        "The patrol breaks. My chalk's still here. So am I.",
        "The wires sing. My head splits — but I know which way is north.",
        "They burn the corridor. They can't burn the trail.",
        f"Families cross because I cleared it. That's the debt. {HERO_LOST_NAME}'s mark is older than I remembered.",
        "The march falters. They know my face. They know I'm coming.",
        "The gate opens. Philadelphia waits. No more excuses.",
        f"Monroe falls. The Republic cracks. {HERO_LOST_NAME} is still out there. The story isn't over.",
    ]
    SECTOR_BLURB_AFTER = [
        f"Patrols scattered — {HERO_NAME.split()[0]}'s chalk trail north open",
        f"Dead grid… {HERO_NAME.split()[0]} felt the current below",
        "Corridor held — commanders retreating",
        f"Crossing open — debt paid toward {HERO_LOST_NAME}",
        "March broken — capital within reach",
        "Last gate passed — citadel ahead",
        f"Monroe Citadel — fallen. {HERO_LOST_NAME} still missing.",
    ]
    SECTOR_RADIO = [[] for _ in SECTOR_BRIEFINGS]

_raw_taunts = _STORY.get("monroe_phase_taunts")
if isinstance(_raw_taunts, list) and _raw_taunts:
    MONROE_PHASE_TAUNTS = [None if t is None else str(t) for t in _raw_taunts]
else:
    MONROE_PHASE_TAUNTS = [
        None,
        f"MONROE: Trace. You still chalk roads for ghosts.",
        f"MONROE: You wore my colors. You followed my orders. And you still chase {HERO_LOST_NAME}?",
        "MONROE: I built a nation for the living. You die for the dead!",
    ]

DEATH_LINES = list(_STORY.get("death_lines") or [
    f"The Militia writes {HERO_NAME} off the roster. Again.",
    "The chalk outlasts me. Someone else will follow it.",
    f"I die within sight of the towers. {HERO_LOST_NAME} never knows.",
    f"{HERO_NAME} falls. The road to {HERO_LOST_NAME} goes dark — for now.",
])

VICTORY_LINES = list(_STORY.get("victory_lines") or [
    "Monroe is down. The Republic cracks.",
    f"Philadelphia is free tonight. {HERO_LOST_NAME} is still out there somewhere.",
    f"No one stops me from looking. — {HERO_NAME}",
])

def _story_death_line(sectors_cleared):
    n = len(sectors_cleared)
    return DEATH_LINES[min(n, len(DEATH_LINES) - 1)]

def _story_victory_line():
    return VICTORY_LINES[-1]

def draw_story_beat(surf, title, lines, line_idx, t_ms):
    global _INTRO_BG_CACHE
    if _INTRO_BG_CACHE is None:
        _INTRO_BG_CACHE = _make_intro_background()
    surf.blit(_INTRO_BG_CACHE, (0, 0))
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 140))
    surf.blit(dim, (0, 0))
    cx = WIDTH // 2
    gold = (232, 198, 118)
    _blit_shadow_text(surf, FONT_MED, title.upper(), gold, cx, int(72 * SY), off=2)
    rule_w = int(min(560 * SX, WIDTH * 0.78))
    ry = int(108 * SY)
    pygame.draw.line(surf, (90, 70, 45), (cx - rule_w // 2, ry), (cx + rule_w // 2, ry), max(1, round(SY)))

    idx = max(0, min(line_idx, len(lines) - 1))
    y = int(168 * SY)
    for i, line in enumerate(lines[: idx + 1]):
        alpha = 255 if i < idx else int(180 + 75 * (0.5 + 0.5 * math.sin(t_ms * 0.006)))
        col = (235, 228, 212) if i < idx else (220, 205, 185)
        txt = FONT_MED.render(line, True, col)
        surf.blit(txt, (cx - txt.get_width() // 2, y))
        y += int(34 * SY)

    hint = FONT_SMALL.render("ENTER  —  continue", True, (140, 125, 105))
    surf.blit(hint, (cx - hint.get_width() // 2, int(HEIGHT - 52 * SY)))

MAP_NODE_FRAC=[
    (0.11, 0.72), (0.24, 0.54), (0.38, 0.60), (0.50, 0.42),
    (0.63, 0.50), (0.76, 0.36), (0.90, 0.20),
]
if _SECTORS:
    MAP_NODES = [
        {
            "title": str(s.get("title") or f"Sector {i}"),
            "blurb": str(s.get("blurb") or ""),
            "rumor": str(s.get("rumor") or ""),
        }
        for i, s in enumerate(_SECTORS)
    ]
else:
    MAP_NODES = [
        {"title": "The Fringe", "blurb": "Ash's first chalk marks", "rumor": "Militia roads. Stay low."},
        {"title": "Dead Grid", "blurb": "Where the wires still sing", "rumor": "Beyond the fringe — nothing hums."},
        {"title": "Ash Corridor", "blurb": "Named for fire — and Trace", "rumor": "Smoke and orders from upstream."},
        {"title": "Broken Line", "blurb": "Where Mira was taken", "rumor": "Refugees speak of Philadelphia."},
        {"title": "Iron March", "blurb": "They remember Ash's face", "rumor": "Full companies on the march."},
        {"title": "The Last Gate", "blurb": "No reinforcements — only Ash", "rumor": "Last stop before the capital."},
        {"title": "Philadelphia", "blurb": "Monroe — and Mira's trail", "rumor": "Monroe waits in the towers."},
    ]


def world_map_node_xy(i):
    nx, ny = MAP_NODE_FRAC[i]
    return int(nx * WIDTH), int(ny * HEIGHT)


def armory_list_for_tier(tier):
    return [u for u in UPGRADE_CATALOG if u["tier"] <= tier]


def try_armory_purchase(upg_id, scrap, owned, perks, gear, tier):
    upg = next((u for u in UPGRADE_CATALOG if u["id"] == upg_id), None)
    if not upg:
        return scrap, owned, perks, gear, False
    if upg["tier"] > tier:
        return scrap, owned, perks, gear, False
    if upg["type"] == "stat" and upg["id"] == "hp_10":
        stacks = sum(1 for x in owned if x == "hp_10")
        if stacks >= upg.get("max_stacks", 3):
            return scrap, owned, perks, gear, False
    elif upg["id"] in owned and upg["type"] in ("gear", "move"):
        return scrap, owned, perks, gear, False
    elif upg["type"] == "perk" and upg["perk"] in perks:
        return scrap, owned, perks, gear, False
    if scrap < upg["cost"]:
        return scrap, owned, perks, gear, False
    scrap -= upg["cost"]
    owned = list(owned)
    perks = list(perks)
    gear = dict(gear)
    if upg["type"] == "stat":
        owned.append(upg["id"])
    elif upg["type"] == "gear":
        owned.append(upg["id"])
        gear[upg["slot"]] = upg["gear_id"]
    elif upg["type"] == "move":
        owned.append(upg["move"])
    elif upg["type"] == "perk":
        owned.append(upg["id"])
        if len(perks) < 2:
            perks.append(upg["perk"])
    return scrap, owned, perks, gear, True


def draw_armory(surf, armory_sel, scrap, owned, perks, gear, sectors_cleared):
    global _INTRO_BG_CACHE
    if _INTRO_BG_CACHE is None:
        _INTRO_BG_CACHE = _make_intro_background()
    surf.blit(_INTRO_BG_CACHE, (0, 0))
    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 140))
    surf.blit(ov, (0, 0))
    cx = WIDTH // 2
    tier = combat_tier(sectors_cleared)
    _blit_shadow_text(surf, FONT_BIG, "ARMORY", (220, 185, 100), cx, int(40 * SY), off=2)
    surf.blit(FONT_MED.render(f"Scrap: {scrap}   ·   Combat tier: {tier}", True, (180, 160, 120)),
              (cx - int(200 * SX), int(88 * SY)))
    items = armory_list_for_tier(tier)
    y0 = int(120 * SY)
    for i, upg in enumerate(items):
        y = y0 + i * int(28 * SY)
        owned_mark = ""
        if upg["type"] == "stat" and upg["id"] == "hp_10":
            stacks = sum(1 for x in owned if x == "hp_10")
            if stacks >= upg.get("max_stacks", 3):
                owned_mark = "[MAX]"
            elif stacks > 0:
                owned_mark = f"[{stacks}/{upg.get('max_stacks', 3)}]"
        elif upg["type"] == "perk" and upg["perk"] in perks:
            owned_mark = "[EQUIPPED]"
        elif upg["id"] in owned or (upg["type"] == "move" and upg.get("move") in owned):
            owned_mark = "[OWNED]"
        sel = i == armory_sel
        col = (255, 235, 170) if sel else (140, 125, 105)
        line = f"{upg['name']}  —  {upg['cost']} scrap  {owned_mark}"
        if upg["tier"] > tier:
            line += f"  (needs tier {upg['tier']})"
        t = FONT_SMALL.render(line, True, col)
        surf.blit(t, (int(80 * SX), y))
    hint = FONT_SMALL.render("UP/DOWN select  ·  ENTER buy/equip  ·  ESC  world map", True, (120, 105, 88))
    surf.blit(hint, (cx - hint.get_width() // 2, HEIGHT - int(36 * SY)))


def draw_world_map(surf, map_sel, map_unlock, checkpoint_wave, sectors_cleared, t_ms, scrap=0):
    global _INTRO_BG_CACHE
    if _INTRO_BG_CACHE is None:
        _INTRO_BG_CACHE = _make_intro_background()
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 120))
    surf.blit(_INTRO_BG_CACHE, (0, 0))
    surf.blit(dim, (0, 0))

    pts = [world_map_node_xy(i) for i in range(len(MAP_NODES))]
    if len(pts) >= 2:
        pygame.draw.lines(surf, (55, 44, 36), False, pts, max(3, round(5 * SY)))
        glow = [(p[0], p[1] + 1) for p in pts]
        pygame.draw.lines(surf, (120, 90, 55), False, glow, max(1, round(2 * SY)))

    gold = (220, 185, 100)
    locked_col = (72, 64, 58)
    cx = WIDTH // 2
    _blit_shadow_text(surf, FONT_BIG, "THE REPUBLIC — WAR MAP", gold, cx, int(36 * SY), off=2)
    sub = FONT_SMALL.render(
        "A / D  select   ·   ENTER  deploy   ·   I  Armory   ·   ESC  title",
        True,
        (140, 125, 105),
    )
    surf.blit(sub, (cx - sub.get_width() // 2, int(78 * SY)))

    pulse = 0.5 + 0.5 * math.sin(t_ms * 0.005)
    nr = max(12, int(14 * SY))
    for i, meta in enumerate(MAP_NODES):
        px, py = pts[i]
        unlocked = i <= map_unlock
        sel = i == map_sel
        r = nr + (int(5 * pulse) if sel else 0)
        if unlocked:
            pygame.draw.circle(surf, (40, 28, 18), (px, py), r + 4)
            pygame.draw.circle(surf, (180, 140, 60) if sel else (100, 78, 48), (px, py), r + 2)
            pygame.draw.circle(surf, (30, 22, 14), (px, py), r)
            pygame.draw.circle(surf, (240, 210, 130) if sel else gold, (px, py), max(4, r - 5))
        else:
            pygame.draw.circle(surf, (25, 22, 20), (px, py), r + 2)
            pygame.draw.circle(surf, locked_col, (px, py), r)
            pygame.draw.line(surf, (45, 40, 38), (px - r // 2, py - r // 2), (px + r // 2, py + r // 2), 2)

        lbl = f"W{i+1}" if i < BOSS_WAVE else "BOSS"
        lt = FONT_TINY.render(lbl, True, (20, 16, 12) if unlocked else (50, 45, 40))
        surf.blit(lt, (px - lt.get_width() // 2, py - lt.get_height() // 2))

        if unlocked and i in sectors_cleared:
            ck = FONT_TINY.render("✓", True, (100, 220, 130))
            surf.blit(ck, (px + r + 2, py - r - 2))

    detail_y = int(HEIGHT - 118 * SY)
    meta = MAP_NODES[map_sel]
    cleared = map_sel in sectors_cleared
    wave_lbl = f"Sector  {map_sel+1}  —  Wave fight" if map_sel < BOSS_WAVE else "Boss encounter"
    t1 = FONT_MED.render(meta["title"], True, (235, 215, 170))
    blurb = SECTOR_BLURB_AFTER[map_sel] if cleared else meta["blurb"]
    t2 = FONT_SMALL.render(blurb, True, (150, 135, 115) if not cleared else (120, 200, 130))
    t3 = FONT_TINY.render(wave_lbl, True, (120, 108, 90))
    surf.blit(t1, (cx - t1.get_width() // 2, detail_y))
    surf.blit(t2, (cx - t2.get_width() // 2, detail_y + int(26 * SY)))
    surf.blit(t3, (cx - t3.get_width() // 2, detail_y + int(48 * SY)))

    if map_sel > map_unlock:
        rumor = meta.get("rumor", "Unknown territory.")
        lock = FONT_MED.render(f"LOCKED  —  {rumor}", True, (180, 90, 70))
        surf.blit(lock, (cx - lock.get_width() // 2, detail_y + int(72 * SY)))
    elif checkpoint_wave is not None and map_sel == checkpoint_wave:
        ck = FONT_SMALL.render("Matches your checkpoint — same as Continue from title", True, (100, 200, 130))
        surf.blit(ck, (cx - ck.get_width() // 2, detail_y + int(72 * SY)))
    if combat_tier(sectors_cleared) >= 1:
        arm = FONT_TINY.render(f"Scrap: {scrap}  ·  Press I for Armory", True, (160, 140, 90))
        surf.blit(arm, (cx - arm.get_width() // 2, HEIGHT - int(24 * SY)))


def world_map_pick_at(mx, my):
    for i in range(len(MAP_NODES)):
        px, py = world_map_node_xy(i)
        rr = max(22, int(22 * SY)) ** 2
        dx, dy = mx - px, my - py
        if dx * dx + dy * dy <= rr:
            return i
    return None


def gen_buildings():
    blds=[]; x=0
    span=400*SX
    while x<WIDTH+span:
        w=random.randint(int(40*SX), int(110*SX)); h=random.randint(int(80*SY), int(230*SY))
        blds.append((x,w,h)); x+=w+random.randint(int(5*SX), int(30*SX))
    return blds

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    load_sounds()
    buildings=gen_buildings()
    particles=[]; fire_parts=[]; fire_timer=0
    state="intro"
    paused=False
    map_sel=0

    high_score, checkpoint_wave, map_unlock, story_seen, sectors_cleared = load_save()
    combat_meta = load_combat_meta()
    scrap = combat_meta["scrap"]
    owned_upgrades = combat_meta["owned_upgrades"]
    equipped_perks = combat_meta["equipped_perks"]
    equipped_gear = combat_meta["equipped_gear"]
    armory_sel = 0

    player=None; enemies=[]; boss=None
    wave=0; wave_clear_timer=0; checkpoint_banner=0
    deploy_sector=None
    story_title=""; story_lines=[]; story_idx=0; story_done="worldmap"
    story_banner=""; story_banner_timer=0
    pending_deploy=None
    rewind_buffer=RewindBuffer()
    death_rewind_window=0

    def _persist_combat():
        write_combat_meta(scrap=scrap, owned_upgrades=owned_upgrades,
                          equipped_perks=equipped_perks, equipped_gear=equipped_gear)

    def _persist_story():
        write_save(high_score, checkpoint_wave, map_unlock,
                   story_seen=story_seen, sectors_cleared=sectors_cleared)
        _persist_combat()

    def _grant_scrap(amount):
        nonlocal scrap
        scrap += int(amount)
        _persist_combat()

    def _mark_sector_cleared(sector):
        nonlocal sectors_cleared, story_seen, owned_upgrades
        key = f"clear_{sector}"
        if key not in story_seen:
            story_seen.append(key)
        if sector not in sectors_cleared:
            sectors_cleared.append(sector)
            _grant_scrap(SCRAP_SECTOR_CLEAR)
            tier = combat_tier(sectors_cleared)
            for t in range(tier + 1):
                for grant in TIER_GRANTS.get(t, []):
                    if grant not in owned_upgrades and grant not in ("perk_slot", "veteran_title"):
                        owned_upgrades.append(grant)
        _persist_story()

    def _begin_story(title, lines, done_action, deploy=None):
        nonlocal state, story_title, story_lines, story_idx, story_done, pending_deploy
        story_title = title
        story_lines = list(lines)
        story_idx = 0
        story_done = done_action
        if deploy is not None:
            pending_deploy = deploy
        state = "story"

    def _finish_story():
        nonlocal state, story_seen, pending_deploy, deploy_sector
        if story_done == "worldmap":
            state = "worldmap"
        elif story_done == "playing":
            if pending_deploy is not None:
                deploy_sector = pending_deploy
                reset(start_wave=pending_deploy)
                pending_deploy = None
            state = "playing"
        elif story_done == "win":
            state = "win"
        pending_deploy = None

    def reset(from_checkpoint=False, start_wave=None):
        nonlocal player, enemies, boss, wave, particles, fire_parts
        nonlocal wave_clear_timer, checkpoint_banner, paused, death_rewind_window
        global REWIND_FLASH_FRAMES
        meta = {
            "owned_upgrades": owned_upgrades,
            "equipped_perks": equipped_perks,
            "equipped_gear": equipped_gear,
        }
        if start_wave is not None:
            w0=int(start_wave)
        elif from_checkpoint and checkpoint_wave is not None:
            w0=checkpoint_wave
        else:
            w0=0
        wave=w0; particles=[]; fire_parts=[]; boss=None
        wave_clear_timer=0; checkpoint_banner=0
        paused=False
        player = Player(WIDTH // 2, GROUND_Y)
        apply_loadout(player, meta, sectors_cleared)
        player.rewind_charges = player.rewind_max
        rewind_buffer.clear()
        death_rewind_window = 0
        REWIND_FLASH_FRAMES = 0
        enemies = spawn_wave(wave) if wave < BOSS_WAVE else []
        if wave >= BOSS_WAVE:
            boss = Boss(WIDTH + 200 * SX, GROUND_Y)

    def _do_rewind():
        nonlocal enemies, boss, wave, wave_clear_timer, death_rewind_window
        result = try_combat_rewind(
            rewind_buffer, player, enemies, boss, wave_clear_timer, particles,
        )
        if result:
            enemies, boss, wave, wave_clear_timer = result
            death_rewind_window = 0
            return True
        return False

    def _trigger_gameover():
        nonlocal state, high_score, map_unlock, story_seen, sectors_cleared
        map_unlock = max(map_unlock, wave)
        high_score = update_high_score(player.kills)
        hs, ck, mu, ss, sc = load_save()
        write_save(high_score, ck, max(mu, map_unlock), story_seen=ss, sectors_cleared=sc)
        map_unlock = max(map_unlock, mu)
        story_seen = ss
        sectors_cleared = sc
        state = "gameover"

    while True:
        clock.tick(FPS)
        keys=pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type==pygame.MOUSEBUTTONDOWN:
                if state=="worldmap" and event.button==1:
                    pk=world_map_pick_at(event.pos[0],event.pos[1])
                    if pk is not None:
                        map_sel=pk
                elif state=="playing" and not paused and event.button==1:
                    if player.hp > 0:
                        player.try_attack()

            if event.type==pygame.KEYUP:
                if state=="playing" and not paused and player is not None:
                    if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and player.hp > 0:
                        player.release_shift_parry()
                continue

            if event.type!=pygame.KEYDOWN:
                continue
            k=event.key

            if k==pygame.K_F11:
                toggle_window_fullscreen()
                continue
            if k==pygame.K_LEFTBRACKET:
                set_master_volume(MASTER_VOLUME-0.1)
                continue
            if k==pygame.K_RIGHTBRACKET:
                set_master_volume(MASTER_VOLUME+0.1)
                continue

            if state=="intro":
                if k==pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if k==pygame.K_RETURN:
                    if "prologue" not in story_seen:
                        story_seen.append("prologue")
                        _persist_story()
                        _begin_story("Revolution", PROLOGUE_LINES, "worldmap")
                    else:
                        state="worldmap"
                        map_sel=min(map_unlock, len(MAP_NODES)-1)
                if k==pygame.K_c and checkpoint_wave is not None:
                    deploy_sector=checkpoint_wave
                    state="playing"; reset(True)
                if k==pygame.K_t:
                    open_trailer_in_browser()

            elif state=="story":
                if k in (pygame.K_RETURN, pygame.K_SPACE):
                    if story_idx < len(story_lines) - 1:
                        story_idx += 1
                    else:
                        _finish_story()
                elif k == pygame.K_ESCAPE:
                    _finish_story()

            elif state=="worldmap":
                if k==pygame.K_ESCAPE:
                    state="intro"
                elif k==pygame.K_i and combat_tier(sectors_cleared) >= 1:
                    state="armory"
                    armory_sel=0
                elif k in(pygame.K_a,pygame.K_LEFT):
                    map_sel=(map_sel-1)%len(MAP_NODES)
                elif k in(pygame.K_d,pygame.K_RIGHT):
                    map_sel=(map_sel+1)%len(MAP_NODES)
                elif k==pygame.K_RETURN:
                    if map_sel<=map_unlock:
                        brief_key = f"brief_{map_sel}"
                        if brief_key not in story_seen:
                            story_seen.append(brief_key)
                            _persist_story()
                            title = MAP_NODES[map_sel]["title"]
                            _begin_story(title, SECTOR_BRIEFINGS[map_sel], "playing", deploy=map_sel)
                        else:
                            deploy_sector = map_sel
                            state = "playing"
                            reset(start_wave=map_sel)

            elif state=="armory":
                items = armory_list_for_tier(combat_tier(sectors_cleared))
                if k == pygame.K_ESCAPE:
                    state = "worldmap"
                elif k in (pygame.K_UP, pygame.K_w):
                    armory_sel = (armory_sel - 1) % max(1, len(items))
                elif k in (pygame.K_DOWN, pygame.K_s):
                    armory_sel = (armory_sel + 1) % max(1, len(items))
                elif k == pygame.K_RETURN and items:
                    upg = items[armory_sel % len(items)]
                    scrap, owned_upgrades, equipped_perks, equipped_gear, ok = try_armory_purchase(
                        upg["id"], scrap, owned_upgrades, equipped_perks, equipped_gear,
                        combat_tier(sectors_cleared))
                    if ok:
                        _persist_combat()

            elif state=="playing":
                if paused:
                    if k==pygame.K_m:
                        state="intro"; paused=False
                    elif k==pygame.K_q:
                        pygame.quit(); sys.exit()
                    elif k in(pygame.K_ESCAPE,pygame.K_p):
                        paused=False
                else:
                    if k in(pygame.K_ESCAPE,pygame.K_p):
                        paused=True
                    elif k==pygame.K_r:
                        _do_rewind()
                    elif player.hp > 0:
                        if k==pygame.K_j:
                            player.try_attack()
                        elif k in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                            player.arm_shift()
                        elif k in (pygame.K_s, pygame.K_DOWN):
                            player.try_dodge()
                        elif k == pygame.K_q:
                            player.try_lane_step(-1)
                        elif k == pygame.K_e:
                            player.try_lane_step(1)
                        elif k==pygame.K_l:
                            if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
                                player.try_crossbow(fan=True)
                            else:
                                player.try_crossbow()

            elif state in("gameover","win"):
                if k==pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if k==pygame.K_r:
                    state="playing"; reset(False)
                if k==pygame.K_m:
                    state="intro"; paused=False

        if state=="intro":
            draw_intro(screen, high_score, checkpoint_wave, pygame.time.get_ticks())

        elif state=="worldmap":
            draw_world_map(screen, map_sel, map_unlock, checkpoint_wave, sectors_cleared,
                           pygame.time.get_ticks(), scrap=scrap)

        elif state=="armory":
            draw_armory(screen, armory_sel, scrap, owned_upgrades, equipped_perks,
                        equipped_gear, sectors_cleared)

        elif state=="story":
            draw_story_beat(screen, story_title, story_lines, story_idx, pygame.time.get_ticks())

        elif state=="playing":
            is_boss=wave>=BOSS_WAVE
            global COMBAT_HITSTOP
            advance_fire=True
            run_sim=False
            if not paused:
                combat_shake_tick()
                rewind_flash_tick()
                if COMBAT_HITSTOP > 0:
                    COMBAT_HITSTOP -= 1
                    run_sim = False
                else:
                    run_sim = combat_time_step_ready()
                advance_fire = run_sim
                if run_sim:
                    # Death rescue: freeze combat so R can rewind a clean buffer
                    if player.hp <= 0:
                        can_rescue = (
                            getattr(player, "can_rewind", False)
                            and player.rewind_charges > 0
                            and len(rewind_buffer) > 12
                        )
                        if can_rescue:
                            if death_rewind_window <= 0:
                                death_rewind_window = REWIND_SPEC["death_window"]
                            death_rewind_window -= 1
                            if death_rewind_window <= 0:
                                _trigger_gameover()
                        else:
                            _trigger_gameover()
                    else:
                        death_rewind_window = 0
                        player.try_time_slow(keys[pygame.K_t])
                        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
                        player.try_bow(keys[pygame.K_k] and player.weapon=="bow")

                        fire_timer+=1
                        if fire_timer%3==0:
                            fire_parts.append(Particle(
                                random.randint(0,WIDTH),GROUND_Y-random.randint(0,int(5*SY)),
                                random.choice(FIRE_COLS),vx=random.uniform(-.5,.5)*SX,
                                vy=random.uniform(-2,-.5)*SY,life=random.randint(20,50),size=random.randint(2,4)))

                        all_foes=enemies+([boss] if boss and boss.alive else [])
                        player.update(keys,all_foes,particles,shift_held=shift_held)

                        for e in enemies:
                            if e.alive: e.update(player,particles)
                        if boss and boss.alive:
                            boss.update(player,particles)
                            if boss.pending_taunt:
                                story_banner = boss.pending_taunt
                                story_banner_timer = 220
                                boss.pending_taunt = None

                        for e in enemies:
                            if not e.alive and not e.counted:
                                player.kills+=1; e.counted=True; play('death')
                                bonus = SCRAP_PER_KILL + player.scrap_per_kill_bonus
                                _grant_scrap(bonus)
                                for _ in range(18):
                                    particles.append(Particle(e.x,e.y-25*SY,BLOOD_COL,
                                                              vx=random.uniform(-4,4)*SX,vy=random.uniform(-6,-1)*SY))
                        if boss and not boss.alive and not boss.counted:
                            player.kills+=10; boss.counted=True; play('death')
                            _grant_scrap(SCRAP_PER_KILL * 10)
                            for _ in range(40):
                                particles.append(Particle(boss.x,boss.y-30*SY,BLOOD_COL,
                                                          vx=random.uniform(-6,6)*SX,vy=random.uniform(-8,-1)*SY))

                        rewind_buffer.push(capture_combat_snapshot(
                            player, enemies, boss, wave, wave_clear_timer))

                        enemies=[e for e in enemies if e.alive]
                        for p in particles: p.update()
                        particles=[p for p in particles if p.life>0]
                        if checkpoint_banner>0: checkpoint_banner-=1
                        if story_banner_timer>0:
                            story_banner_timer-=1

                        if is_boss:
                            if boss and not boss.alive:
                                state="win"
                                high_score=update_high_score(player.kills)
                                map_unlock=max(map_unlock,BOSS_WAVE)
                                _mark_sector_cleared(BOSS_WAVE)
                                _grant_scrap(SCRAP_BOSS_WIN)
                                hs,_,mu,ss,sc=load_save()
                                write_save(hs,None,max(mu,map_unlock),story_seen=ss,sectors_cleared=sc)
                                checkpoint_wave=None
                                map_unlock=max(map_unlock,mu)
                                sectors_cleared=sc
                        else:
                            if not enemies:
                                wave_clear_timer+=1
                                if wave_clear_timer==1:
                                    play('wave_clear')
                                    if deploy_sector is not None and wave == deploy_sector:
                                        _mark_sector_cleared(wave)
                                        if wave < len(SECTOR_CLEAR_LINES):
                                            story_banner = SECTOR_CLEAR_LINES[wave]
                                            story_banner_timer = 200
                                if wave_clear_timer>100:
                                    wave+=1
                                    map_unlock=max(map_unlock,wave)
                                    write_save(high_score,checkpoint_wave,map_unlock,
                                               story_seen=story_seen,sectors_cleared=sectors_cleared)
                                    if wave%2==0 and wave<BOSS_WAVE:
                                        save_checkpoint(wave,player.kills)
                                        high_score,checkpoint_wave,map_unlock,story_seen,sectors_cleared=load_save()
                                        checkpoint_banner=200; play('checkpoint')
                                    if wave>=BOSS_WAVE:
                                        boss=Boss(WIDTH+100*SX,GROUND_Y); enemies=[]
                                    else:
                                        enemies=spawn_wave(wave)
                                    wave_clear_timer=0
                            else:
                                wave_clear_timer=0
            else:
                advance_fire=False

            shaking=not paused and COMBAT_SHAKE_FRAMES>0
            surf=pygame.Surface((WIDTH,HEIGHT)) if shaking else screen
            if shaking:
                surf.fill((14,10,8))

            draw_background(surf,buildings,fire_parts,advance_fire=advance_fire)
            draw_list = list(enemies)
            if boss and boss.alive:
                draw_list.append(boss)
            draw_list.append(player)
            draw_list.sort(key=lambda ent: getattr(ent, "w", W_LANE_MID))
            pw = getattr(player, "w", W_LANE_MID)
            for ent in draw_list:
                if ent is player:
                    ent.draw(surf)
                else:
                    ent.draw(surf, w_peer=pw)
            for p in particles:
                p.draw(surf)

            wlbl="BOSS WAVE" if is_boss else f"WAVE {wave+1}/{BOSS_WAVE}"
            ecnt=len(enemies) if not is_boss else (1 if boss and boss.alive else 0)
            draw_hud(surf,player,wlbl,ecnt,high_score,checkpoint_wave,scrap=scrap,
                     death_rewind_window=death_rewind_window)

            if TIME_SLOW_FRAMES > 0 and not paused:
                tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                tint.fill((40, 90, 140, 28))
                surf.blit(tint, (0, 0))

            if REWIND_FLASH_FRAMES > 0 and not paused:
                flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                fa = int(90 * REWIND_FLASH_FRAMES / max(1, REWIND_SPEC["flash_frames"]))
                flash.fill((110, 35, 170, fa))
                surf.blit(flash, (0, 0))

            if 0<wave_clear_timer<100 and not is_boss:
                if wave<BOSS_WAVE:
                    txt=FONT_MED.render(f"WAVE {wave} CLEARED — Prepare...",True,(200,180,80))
                else:
                    txt=FONT_MED.render("BOSS INCOMING — SEBASTIAN MONROE!",True,(220,60,40))
                surf.blit(txt,(WIDTH//2-txt.get_width()//2,HEIGHT//2-int(20*SY)))

            if checkpoint_banner>0:
                cp=FONT_MED.render(f"CHECKPOINT SAVED  (Wave {checkpoint_wave+1})",True,(100,230,100))
                surf.blit(cp,(WIDTH//2-cp.get_width()//2,HEIGHT//2+int(55*SY)))

            if story_banner_timer>0 and story_banner:
                st=FONT_MED.render(story_banner,True,(220,200,140))
                surf.blit(st,(WIDTH//2-st.get_width()//2,HEIGHT//2-int(58*SY)))

            if shaking:
                screen.fill((14,10,8))
                sx,sy_=combat_shake_offset()
                screen.blit(surf,(sx,sy_))

            if paused:
                draw_pause_overlay(screen,MASTER_VOLUME)

        elif state in("gameover","win"):
            draw_background(screen,buildings,[])
            draw_gameover(screen,player,high_score,win=(state=="win"),sectors_cleared=sectors_cleared)

        pygame.display.flip()

if __name__=="__main__":
    main()
