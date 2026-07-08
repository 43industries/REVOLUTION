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
  * Sound effects (procedurally generated, no audio files needed)
  * High score saved to disk (revolution_save.json)
  * Blood particles, fire ambience, animated stickmen
  * Enemy commanders shoot arrows
  * Boss: Sebastian Monroe with charge/slam/shoot AI
  * Cinematic trailer: trailer.html (press T on title screen to open in browser)
"""

import pygame, sys, math, random, os, json, struct, wave, io, webbrowser
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
def load_save():
    try:
        with open(SAVE_FILE) as f:
            d=json.load(f)
        hs=d.get("high_score",0)
        ck=d.get("checkpoint_wave",None)
        mu=d.get("map_unlock")
        if mu is None:
            mu=0 if ck is None else max(0,int(ck))
        return hs, ck, int(mu)
    except Exception:
        return 0, None, 0

def write_save(score, checkpoint_wave, map_unlock):
    try:
        with open(SAVE_FILE,'w') as f:
            json.dump({
                "high_score": int(score),
                "checkpoint_wave": checkpoint_wave,
                "map_unlock": int(map_unlock),
            },f)
    except Exception:
        pass

def save_checkpoint(wave_idx, score):
    hs, ck, mu=load_save()
    mu=max(mu, int(wave_idx))
    write_save(max(score, hs), wave_idx, mu)

def update_high_score(score):
    hs, ck, mu=load_save()
    new_hs=max(score, hs)
    write_save(new_hs, ck, mu)
    return new_hs

def clear_checkpoint():
    hs, ck, mu=load_save()
    write_save(hs, None, mu)

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
                 col=ARROW_COL,tip_col=(220,180,80),pierce=False):
        self.x,self.y=float(x),float(y)
        self.vx=speed*SX*direction; self.vy=-1.0*SY
        self.alive=True; self.dir=direction
        self.damage=damage; self.col=col
        self.tip_col=tip_col; self.pierce=pierce
        self.hit_count=0
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
    def __init__(self,x,y,direction):
        self.x,self.y=float(x),float(y)
        self.vx=5.5*SX*direction; self.vy=0.0
        self.alive=True; self.dir=direction
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
    def __init__(self,x,y,col,size=1.0):
        self.x,self.y=float(x),float(y); self.col=col; self.s=size
        self.vx,self.vy=0.0,0.0; self.on_ground=False
        self.hp=100; self.max_hp=100
        self.facing=1; self.anim_tick=0; self.hurt_flash=0
        self.hit_react=0
        self.last_player_swing=-1

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

    def draw_body(self, surf, attack_progress=0, bow_draw=0,
                  crossbow_aim=0, boss_slam=0.0, attack_style="slash",
                  leg_override=None, hit_react_amt=0.0, charge_pose=0.0,
                  telegraph=0):
        s = self.s; cx, cy = int(self.x), int(self.y)
        col = WHITE if self.hurt_flash > 0 else self.col
        hr = int(9 * s * SY); tl = int(22 * s * SY); ll = int(18 * s * SY)
        hy = cy - tl - hr; ny = cy - tl; hip = cy; shy = cy - int(tl * 0.75)

        l1, l2, a1, a2 = self._limb_angles()
        if leg_override is not None:
            l1, l2, a1, a2 = leg_override[0], leg_override[1], leg_override[2], leg_override[3]

        if hit_react_amt > 0.05 and attack_progress <= 0 and boss_slam <= 0:
            pygame.draw.circle(surf, col, (cx + int(4 * SY * (-self.facing) * hit_react_amt), hy), hr, LW)
            self._draw_hit_react(surf, cx, shy, hip, ll, col, s, hit_react_amt)
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
        s=self.s
        return pygame.Rect(self.x-12*s*SY,self.y-50*s*SY,24*s*SY,55*s*SY)

# ── Player ─────────────────────────────────────────────────────────────────────
class Player(Stickman):
    """Sword timing: wind-up → short active window (one hit each) → recovery (commitment)."""
    SPEED=4.2*SX; JUMP_V=-13*SY; BOW_CD=45; XBOW_CD=30
    SWORD_ANIM_LEN=22
    SWORD_CD_MAX=36
    SWORD_ACTIVE_LO=9
    SWORD_ACTIVE_HI=13
    COMBO_WINDOW=48
    COMBO_STYLES=("jab", "slash", "finisher")

    def __init__(self,x,y,kills=0):
        super().__init__(x,y,PLAYER_COL,size=1.15)
        self.sword_anim=0
        self.sword_cd=0
        self.swing_id=0
        self.hitstun=0
        self.combo_step=0
        self.combo_timer=0
        self.attack_style="slash"
        self.bow_charge=0; self.bow_timer=0
        self.xbow_timer=0; self.xbow_cock=0
        self.arrows=[]; self.weapon="sword"; self.kills=kills

    def _sword_raw_phase(self):
        if self.sword_anim <= 0:
            return 0.0
        return (self.SWORD_ANIM_LEN - self.sword_anim) / max(1, self.SWORD_ANIM_LEN - 1)

    def _sword_commitment_lock(self):
        ph = self._sword_raw_phase()
        return ph < 0.32 or ph > 0.76

    def handle_input(self,keys):
        if self.hitstun>0:
            return
        locked = self.weapon == "sword" and self.sword_anim > 0 and self._sword_commitment_lock()
        if not locked:
            self.vx=0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:  self.vx=-self.SPEED; self.facing=-1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.vx= self.SPEED; self.facing= 1
        elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.facing=-1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.facing=1
        if (keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_SPACE]) and self.on_ground:
            if not (self.sword_anim > 0 and self._sword_commitment_lock()):
                self.vy=self.JUMP_V
        if keys[pygame.K_1]: self.weapon="sword"
        if keys[pygame.K_2]: self.weapon="bow"
        if keys[pygame.K_3]: self.weapon="crossbow"

    def try_attack(self):
        if self.hitstun>0:
            return False
        if self.weapon=="sword" and self.sword_cd<=0 and self.sword_anim<=0:
            if self.combo_timer > 0 and self.combo_step < len(self.COMBO_STYLES) - 1:
                self.combo_step += 1
            else:
                self.combo_step = 0
            self.combo_timer = self.COMBO_WINDOW
            self.attack_style = self.COMBO_STYLES[self.combo_step]
            self.sword_anim=self.SWORD_ANIM_LEN
            self.sword_cd=self.SWORD_CD_MAX
            self.swing_id+=1
            play('swing')
            return True
        return False

    def try_bow(self,charging):
        if self.hitstun>0:
            return
        if self.weapon!="bow": return
        if charging: self.bow_charge=min(self.bow_charge+1,40)
        else:
            if self.bow_charge>8 and self.bow_timer<=0:
                self.arrows.append(Arrow(self.x+15*SX*self.facing,self.y-30*SY,self.facing))
                self.bow_timer=self.BOW_CD; play('arrow')
            self.bow_charge=0

    def try_crossbow(self):
        if self.hitstun>0:
            return
        if self.weapon!="crossbow" or self.xbow_timer>0: return
        self.xbow_timer=self.XBOW_CD; self.xbow_cock=12
        self.arrows.append(Arrow(self.x+15*SX*self.facing,self.y-28*SY,self.facing,
                                 damage=(30,45),speed=14,
                                 col=BOLT_COL,tip_col=(180,255,180),pierce=True))
        play('bolt')

    def update(self,keys,enemies,particles):
        if self.combo_timer>0:
            self.combo_timer-=1
            if self.combo_timer<=0:
                self.combo_step=0
        self.handle_input(keys)
        if self.sword_cd>0:
            self.sword_cd-=1
        if self.sword_anim>0:
            self.sword_anim-=1
            ph = self._sword_raw_phase()
            if self.SWORD_ACTIVE_LO<=self.sword_anim<=self.SWORD_ACTIVE_HI:
                lunge = 1.35 if self.attack_style == "finisher" else (0.85 if self.attack_style == "jab" else 1.05)
                self.x += lunge * SX * self.facing
        if self.bow_timer>0:     self.bow_timer-=1
        if self.xbow_timer>0:    self.xbow_timer-=1
        if self.xbow_cock>0:     self.xbow_cock-=1

        self.physics()
        if self.hitstun>0:
            self.hitstun-=1
            self.vx*=0.82
            if self.on_ground:
                self.vx*=0.88

        if self.weapon=="sword" and self.SWORD_ACTIVE_LO<=self.sword_anim<=self.SWORD_ACTIVE_HI:
            reach = 42 if self.attack_style == "jab" else (54 if self.attack_style == "finisher" else 48)
            ox=12*SX if self.facing==1 else -(reach+4)*SX
            r=pygame.Rect(self.x+ox,self.y-50*SY,reach*SX,52*SY)
            dmg_rng = {"jab": (16, 24), "slash": (22, 34), "finisher": (28, 42)}
            lo, hi = dmg_rng.get(self.attack_style, (22, 34))
            for e in enemies:
                if not e.alive:
                    continue
                if getattr(e,"last_player_swing",-1)==self.swing_id:
                    continue
                if r.colliderect(e.rect()):
                    e.last_player_swing=self.swing_id
                    dmg=random.randint(lo, hi)
                    e.hp-=dmg; e.hurt_flash=14; e.hit_react=14
                    kb = 8.5 if self.attack_style == "finisher" else (5.2 if self.attack_style == "jab" else 6.8)
                    e.vx=kb*SX*self.facing; e.vy=-4.8*SY
                    freeze = 5 if self.attack_style == "finisher" else 3
                    shake = (10, 12) if self.attack_style == "finisher" else (7, 9)
                    play('hit')
                    combat_freeze(freeze)
                    combat_shake(*shake)
                    for _ in range(11):
                        particles.append(Particle(e.x,e.y-20*SY,BLOOD_COL,
                                                  vx=random.uniform(-3,3)*SX,vy=random.uniform(-4,-0.5)*SY))
                    particles.append(Particle(e.x,e.y-28*SY,(255,245,200),
                                                vx=random.uniform(-1,1)*SX,vy=random.uniform(-2,0)*SY,
                                                life=10,size=3))

        for arr in self.arrows:
            arr.update()
            for e in enemies:
                if e.alive and arr.alive:
                    if abs(arr.x-e.x)<15*SX and e.y-55*SY<arr.y<e.y+5*SY:
                        dmg=random.randint(*arr.damage)
                        e.hp-=dmg; e.hurt_flash=10; e.hit_react=10; play('hit')
                        combat_freeze(2)
                        combat_shake(4,6)
                        for _ in range(6):
                            particles.append(Particle(e.x,e.y-25*SY,BLOOD_COL))
                        if arr.pierce:
                            arr.hit_count+=1
                            if arr.hit_count>=2: arr.alive=False
                        else:
                            arr.alive=False; break
        self.arrows=[a for a in self.arrows if a.alive]

    def draw(self,surf):
        ap = self._sword_raw_phase() if self.sword_anim > 0 else 0.0
        bc =self.bow_charge/40    if self.weapon=="bow"    else 0
        xba=(self.XBOW_CD-self.xbow_timer)/self.XBOW_CD if self.weapon=="crossbow" else 0
        react = self.hit_react / 14.0 if self.hit_react > 0 else 0.0
        self.draw_body(
            surf, attack_progress=ap if self.weapon == "sword" else 0,
            bow_draw=bc, crossbow_aim=xba if self.weapon=="crossbow" else 0,
            attack_style=self.attack_style, hit_react_amt=react,
        )
        for a in self.arrows: a.draw(surf)

# ── Enemy ──────────────────────────────────────────────────────────────────────
class Enemy(Stickman):
    ATK_TOTAL=20
    ATK_HIT_FRAME=10

    def __init__(self,x,y,etype="soldier"):
        col= ENEMY_COL if etype=="soldier" else CMD_COL
        sz = 1.0       if etype=="soldier" else 1.3
        super().__init__(x,y,col,sz)
        self.alive=True; self.etype=etype
        self.hp=60 if etype=="soldier" else 130; self.max_hp=self.hp
        self.atk_timer=random.randint(40,80); self.atk_active=0
        self.atk_style="chop" if etype=="soldier" else "slash"
        self.telegraph=0
        self.aim_draw=0
        self.patrol_dir=random.choice([-1,1]); self.patrol_tick=0
        self.aggro=False; self.counted=False
        self.shoot_timer=random.randint(90,160) if etype=="commander" else 99999
        self.e_arrows=[]

    def update(self,player,particles):
        dx=player.x-self.x; dist=abs(dx)
        if dist<320*SX: self.aggro=True
        if dist>520*SX: self.aggro=False

        if self.aggro:
            self.facing=1 if dx>0 else -1
            spd=(2.2 if self.etype=="soldier" else 1.6)*SX
            if self.atk_active>0 or self.aim_draw>0:
                self.vx=0
            elif self.etype=="commander" and self.aim_draw==0 and self.shoot_timer<=25:
                self.vx=-0.9*SX*self.facing
            else:
                self.vx=spd*self.facing if dist>45*SX else 0
            if self.atk_timer>0: self.atk_timer-=1
            if dist<58*SX and self.atk_timer<=0 and self.atk_active<=0 and self.aim_draw<=0:
                self.atk_timer=60; self.atk_active=self.ATK_TOTAL
                self.telegraph=0
            if self.atk_active>0:
                self.atk_active-=1
                if self.atk_active==13:
                    self.telegraph=4
                    for _ in range(4):
                        particles.append(Particle(
                            self.x+14*SX*self.facing, GROUND_Y-int(4*SY),
                            (100, 82, 58), vx=random.uniform(-1.5,1.5)*SX,
                            vy=random.uniform(-0.8,-0.1)*SY, life=12, size=2,
                        ))
                if self.telegraph>0:
                    self.telegraph-=1
                if self.atk_active==self.ATK_HIT_FRAME and dist<65*SX:
                    player.hp-=random.randint(8,16); player.hurt_flash=12
                    player.hitstun=max(player.hitstun,12); player.hit_react=14
                    player.vx=-self.facing*5.2*SX; player.vy=-3.4*SY; play('hit')
                    combat_freeze(2)
                    combat_shake(5,7)
                    for _ in range(5):
                        particles.append(Particle(player.x,player.y-20*SY,BLOOD_COL))
            if self.etype=="commander":
                if self.shoot_timer>0: self.shoot_timer-=1
                if self.shoot_timer<=0 and dist>90*SX and self.atk_active<=0:
                    if self.aim_draw < 22:
                        self.aim_draw += 1
                    else:
                        self.e_arrows.append(EnemyArrow(self.x+10*SX*self.facing,self.y-28*SY,self.facing))
                        self.shoot_timer=random.randint(90,160)
                        self.aim_draw=0
                        play('arrow')
        else:
            self.patrol_tick+=1
            if self.patrol_tick>120: self.patrol_dir=-self.patrol_dir; self.patrol_tick=0
            self.vx=self.patrol_dir*1.2*SX; self.facing=self.patrol_dir

        for ea in self.e_arrows:
            ea.update()
            if ea.alive and abs(ea.x-player.x)<16*SX and player.y-52*SY<ea.y<player.y+5*SY:
                player.hp-=random.randint(6,12); player.hurt_flash=10
                player.hitstun=max(player.hitstun,8); player.hit_react=10
                player.vx+=-ea.dir*2.8*SX
                ea.alive=False; play('hit')
                combat_freeze(1)
                combat_shake(3,5)
        self.e_arrows=[ea for ea in self.e_arrows if ea.alive]
        self.physics()
        if self.hp<=0 and not self.counted: self.alive=False

    def draw(self,surf):
        if not self.alive: return
        ap = choreo_enemy_attack_progress(self.atk_active, self.ATK_TOTAL) if self.atk_active > 0 else 0.0
        react = self.hit_react / 14.0 if self.hit_react > 0 else 0.0
        bow = (self.aim_draw / 22.0) if self.etype == "commander" and self.aim_draw > 0 else 0.0
        self.draw_body(
            surf, attack_progress=ap if bow <= 0 else 0, bow_draw=bow,
            attack_style=self.atk_style, telegraph=1 if self.telegraph > 0 else 0,
            hit_react_amt=react,
        )
        for ea in self.e_arrows: ea.draw(surf)
        bw=int(36*self.s*SY); bx=int(self.x-bw//2); by=int(self.y-65*self.s*SY)
        bh=max(5, round(5*SY))
        pygame.draw.rect(surf,(80,20,20),(bx,by,bw,bh))
        pygame.draw.rect(surf,(200,60,40),(bx,by,int(bw*max(0,self.hp/self.max_hp)),bh))
        if self.etype=="commander":
            t=FONT_SMALL.render("CMD",True,(210,130,220)); surf.blit(t,(bx-2,by-int(14*SY)))

# ── Boss: Sebastian Monroe ──────────────────────────────────────────────────────
class Boss(Stickman):
    PHASE_THRESHOLDS=[350,150]

    def __init__(self,x,y):
        super().__init__(x,y,BOSS_COL,size=1.8)
        self.hp=self.max_hp=600; self.alive=True; self.counted=False
        self.phase=0; self.action="walk"; self.action_timer=120
        self.slam_progress=0.0; self.slam_active=False
        self.charge_windup=0
        self.shoot_timer=0; self.e_arrows=[]; self.roar_done=False
        self.enrage_flash=0; self.intro_timer=130

    def update(self,player,particles):
        if self.intro_timer>0:
            self.intro_timer-=1; self.vx=0; self.physics(); return

        if not self.roar_done: play('boss_roar'); self.roar_done=True

        # phase transitions
        if self.phase<2 and self.hp<=self.PHASE_THRESHOLDS[self.phase]:
            self.phase+=1; play('boss_roar'); self.enrage_flash=50

        dx=player.x-self.x; dist=abs(dx)
        self.facing=1 if dx>0 else -1
        if self.enrage_flash>0: self.enrage_flash-=1

        if self.action_timer>0: self.action_timer-=1
        else:
            r=random.random()
            if self.phase==0:
                if dist>100*SX and r<0.45: self.action="walk"; self.action_timer=80
                elif r<0.75:            self._begin_slam()
                else:                   self._begin_shoot(2)
            elif self.phase==1:
                if dist>80*SX and r<0.35:  self.action="charge"; self.charge_windup=18; self.action_timer=70
                elif r<0.65:            self._begin_slam()
                else:                   self._begin_shoot(3)
            else:
                if dist>60*SX and r<0.30:  self.action="charge"; self.charge_windup=18; self.action_timer=70
                elif r<0.55:            self._begin_slam()
                else:                   self._begin_shoot(5)

        # execute
        if self.action=="walk":
            self.vx=2.8*SX*self.facing if dist>70*SX else 0
        elif self.action=="charge":
            if self.charge_windup>0:
                self.charge_windup-=1
                self.vx=0
            else:
                self.vx=9*SX*self.facing
                if dist<60*SX: self._slam_hit(player,particles,(28,45)); self.action="walk"; self.action_timer=40
        elif self.action=="slam":
            self.vx=0
            if self.slam_progress < 0.58:
                self.slam_progress=min(0.58, self.slam_progress+0.038)
            else:
                self.slam_progress=min(1.0, self.slam_progress+0.11)
            if self.slam_progress>=1.0:
                self._slam_hit(player,particles,(32,52))
                self.slam_active=False; self.slam_progress=0.0
                self.action="walk"; self.action_timer=30
        elif self.action=="shoot":
            self.vx=0

        if self.action=="shoot":
            if self.shoot_timer>0: self.shoot_timer-=1
            elif self.action_timer>0:
                self.e_arrows.append(EnemyArrow(self.x+22*SX*self.facing,self.y-42*SY,self.facing))
                self.shoot_timer=14; play('arrow')

        for ea in self.e_arrows:
            ea.update()
            if ea.alive and abs(ea.x-player.x)<16*SX and player.y-52*SY<ea.y<player.y+5*SY:
                player.hp-=random.randint(14,22); player.hurt_flash=14
                player.hitstun=max(player.hitstun,11); player.hit_react=12
                player.vx+=-ea.dir*3.5*SX
                ea.alive=False; play('hit')
                combat_freeze(2)
                combat_shake(6,7)
        self.e_arrows=[ea for ea in self.e_arrows if ea.alive]
        self.physics()
        if self.hp<=0 and not self.counted: self.alive=False

    def _begin_slam(self):
        self.action="slam"; self.action_timer=45
        self.slam_progress=0.0; self.slam_active=True

    def _begin_shoot(self,bursts):
        self.action="shoot"; self.action_timer=bursts*18+10; self.shoot_timer=0

    def _slam_hit(self,player,particles,dmg):
        if abs(player.x-self.x)<110*SX:
            player.hp-=random.randint(*dmg); player.hurt_flash=18
            player.hitstun=max(player.hitstun,20); player.hit_react=18
            player.vx=-self.facing*8.5*SX; player.vy=-6*SY; play('hit')
            combat_freeze(5)
            combat_shake(12,14)
            for _ in range(14):
                particles.append(Particle(player.x,player.y-20*SY,BLOOD_COL,
                                          vx=random.uniform(-5,5)*SX,vy=random.uniform(-7,-1)*SY))
        for _ in range(22):
            particles.append(Particle(self.x+random.randint(-int(50*SX),int(50*SX)),GROUND_Y,
                                      random.choice(SPARK_COLS),
                                      vx=random.uniform(-5,5)*SX,vy=random.uniform(-6,-0.5)*SY,
                                      life=random.randint(12,28),size=random.randint(1,3)))

    def draw(self,surf):
        if not self.alive: return
        saved=self.col
        if self.enrage_flash>0 and self.enrage_flash%6<3: self.col=(255,255,50)
        slam_p=self.slam_progress if self.slam_active else 0.0
        charge_amt = min(1.0, self.charge_windup / 18.0) if self.charge_windup > 0 else 0.0
        react = self.hit_react / 14.0 if self.hit_react > 0 else 0.0
        self.draw_body(surf, boss_slam=slam_p, charge_pose=charge_amt, hit_react_amt=react)
        self.col=saved
        for ea in self.e_arrows: ea.draw(surf)

        # Boss HP bar
        bw=int(320*SX); bx=(WIDTH-bw)//2; by=int(8*SY)
        bh=max(14, int(round(18*SY)))
        pygame.draw.rect(surf,(60,15,15),(bx,by,bw,bh),border_radius=max(2, round(4*SY)))
        fill=int(bw*max(0,self.hp/self.max_hp))
        pc=[(220,40,30),(200,90,20),(220,190,20)][self.phase]
        pygame.draw.rect(surf,pc,(bx,by,fill,bh),border_radius=max(2, round(4*SY)))
        # phase markers
        for pct in[350/600,150/600]:
            mx=bx+int(bw*pct)
            pygame.draw.line(surf,(255,255,80),(mx,by),(mx,by+bh),LW)
        lbl=FONT_MED.render(f"MONROE  {max(0,self.hp)} / {self.max_hp}",True,(255,180,100))
        surf.blit(lbl,(WIDTH//2-lbl.get_width()//2,by+1))

        if self.intro_timer>0:
            t1=FONT_BIG.render("SEBASTIAN MONROE",True,(220,50,30))
            t2=FONT_SMALL.render("President of the Monroe Republic",True,(180,80,60))
            surf.blit(t1,(WIDTH//2-t1.get_width()//2,HEIGHT//2-int(60*SY)))
            surf.blit(t2,(WIDTH//2-t2.get_width()//2,HEIGHT//2-int(20*SY)))

# ── Background & HUD ───────────────────────────────────────────────────────────
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

def draw_hud(surf,player,wave_lbl,enemy_count,high_score,checkpoint_wave):
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

    if "BOSS" not in wave_lbl:
        wt=FONT_MED.render(wave_lbl,True,HUD_COL)
        surf.blit(wt,(WIDTH//2-wt.get_width()//2,int(14*SY)))
        et=FONT_SMALL.render(f"Enemies: {enemy_count}",True,(180,130,80))
        surf.blit(et,(WIDTH//2-et.get_width()//2,int(38*SY)))

    rx=int(150*SX)
    surf.blit(FONT_SMALL.render(f"KILLS: {player.kills}",True,HUD_DIM),(WIDTH-rx,hy))
    surf.blit(FONT_SMALL.render(f"BEST:  {high_score}",True,(160,130,60)),(WIDTH-rx,hy+int(16*SY)))

    if player.weapon=="sword":
        cd=player.sword_cd/player.SWORD_CD_MAX if player.sword_cd>0 else 0
        cy=hy+int(36*SY); cw,ch=int(130*SX),max(5, round(6*SY))
        pygame.draw.rect(surf,(40,30,15),(WIDTH-rx,cy,cw,ch),border_radius=max(2, round(3*SY)))
        pygame.draw.rect(surf,(220,180,60),(WIDTH-rx,cy,int(cw*(1-cd)),ch),border_radius=max(2, round(3*SY)))
        surf.blit(FONT_SMALL.render("SWING CD",True,HUD_DIM),(WIDTH-rx,cy+ch+int(2*SY)))
    elif player.weapon=="crossbow":
        cd=player.xbow_timer/player.XBOW_CD if player.xbow_timer>0 else 0
        cy=hy+int(36*SY); cw,ch=int(130*SX),max(5, round(6*SY))
        pygame.draw.rect(surf,(20,40,20),(WIDTH-rx,cy,cw,ch),border_radius=max(2, round(3*SY)))
        pygame.draw.rect(surf,BOLT_COL,(WIDTH-rx,cy,int(cw*(1-cd)),ch),border_radius=max(2, round(3*SY)))
        surf.blit(FONT_SMALL.render("BOLT CD ",True,HUD_DIM),(WIDTH-rx,cy+ch+int(2*SY)))

    if checkpoint_wave is not None:
        ct=FONT_SMALL.render(f"CKPT: Wave {checkpoint_wave+1}",True,(100,200,100))
        surf.blit(ct,(hx,HEIGHT-int(22*SY)))

    hint=FONT_SMALL.render("ESC / P  Pause   •   F11  Fullscreen   •   [ ]  Vol",True,(95,78,58))
    surf.blit(hint,(WIDTH//2-hint.get_width()//2,HEIGHT-int(20*SY)))

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

    # Controls panel
    panel_top, panel_h = Y(248), int(132 * SY)
    panel_w = int(min(620 * SX, WIDTH - 80))
    px = cx - panel_w // 2
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((8, 6, 12, 168))
    br = max(6, round(8 * SY))
    pygame.draw.rect(panel, (212, 168, 75, 55), panel.get_rect(), width=1, border_radius=br)
    surf.blit(panel, (px, panel_top))

    lines = [
        "A/D  move   ·   W / Space  jump",
        "J / LMB  sword   ·   K (hold)  bow   ·   L  crossbow",
        "1 / 2 / 3  weapons   ·   Map: 6 sectors  +  Monroe citadel (boss)",
        "F11  fullscreen   ·   [  ]  volume   ·   T  cinematic trailer",
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

def draw_gameover(surf,player,high_score,win=False):
    ov=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    ov.fill((0,0,0,165)); surf.blit(ov,(0,0))
    cx=WIDTH//2
    if win:
        _blit_shadow_text(surf,FONT_BIG,"VICTORY — MONROE DEFEATED",(130,230,115),cx,int(165*SY),off=3)
        sub=FONT_MED.render("The Republic falls. Freedom rises.",True,(100,180,80))
    else:
        _blit_shadow_text(surf,FONT_BIG,"YOU FELL",(220,75,55),cx,int(165*SY),off=3)
        sub=FONT_MED.render("The Militia claims another soul.",True,(160,80,60))
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
WAVES=[
    {"soldiers":3,"commanders":0},
    {"soldiers":5,"commanders":1},
    {"soldiers":6,"commanders":1},
    {"soldiers":8,"commanders":2},
    {"soldiers":10,"commanders":2},
    {"soldiers":12,"commanders":3},
]
BOSS_WAVE=len(WAVES)

def spawn_wave(idx):
    cfg=WAVES[idx]; out=[]
    for i in range(cfg["soldiers"]):
        side=1 if i%2==0 else -1
        o80,o60=80*SX,60*SX
        ex=WIDTH+o80+i*o60 if side==1 else -o80-i*o60
        out.append(Enemy(ex,GROUND_Y,"soldier"))
    for i in range(cfg["commanders"]):
        side=1 if i%2==0 else -1
        o220,o80=220*SX,80*SX
        ex=WIDTH+o220+i*o80 if side==1 else -o220-i*o80
        out.append(Enemy(ex,GROUND_Y,"commander"))
    return out

# ── World map (campaign) ───────────────────────────────────────────────────────
MAP_NODE_FRAC=[
    (0.11, 0.72), (0.24, 0.54), (0.38, 0.60), (0.50, 0.42),
    (0.63, 0.50), (0.76, 0.36), (0.90, 0.20),
]
MAP_NODES=[
    {"title": "The Fringe", "blurb": "First Militia patrols"},
    {"title": "Dead Grid", "blurb": "No live wires"},
    {"title": "Ash Corridor", "blurb": "Commanders forward"},
    {"title": "Broken Line", "blurb": "Volleys & steel"},
    {"title": "Iron March", "blurb": "Heavy resistance"},
    {"title": "The Last Gate", "blurb": "Before the Republic"},
    {"title": "Philadelphia", "blurb": "Monroe Citadel — boss"},
]


def world_map_node_xy(i):
    nx, ny = MAP_NODE_FRAC[i]
    return int(nx * WIDTH), int(ny * HEIGHT)


def draw_world_map(surf, map_sel, map_unlock, checkpoint_wave, t_ms):
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
        "A / D  or  ← / →  select   ·   ENTER  deploy   ·   ESC  title   ·   Click  node",
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

    detail_y = int(HEIGHT - 118 * SY)
    meta = MAP_NODES[map_sel]
    wave_lbl = f"Sector  {map_sel+1}  —  Wave fight" if map_sel < BOSS_WAVE else "Boss encounter"
    t1 = FONT_MED.render(meta["title"], True, (235, 215, 170))
    t2 = FONT_SMALL.render(meta["blurb"], True, (150, 135, 115))
    t3 = FONT_TINY.render(wave_lbl, True, (120, 108, 90))
    surf.blit(t1, (cx - t1.get_width() // 2, detail_y))
    surf.blit(t2, (cx - t2.get_width() // 2, detail_y + int(26 * SY)))
    surf.blit(t3, (cx - t3.get_width() // 2, detail_y + int(48 * SY)))

    if map_sel > map_unlock:
        lock = FONT_MED.render("LOCKED  —  advance in campaign to unlock", True, (180, 90, 70))
        surf.blit(lock, (cx - lock.get_width() // 2, detail_y + int(72 * SY)))
    elif checkpoint_wave is not None and map_sel == checkpoint_wave:
        ck = FONT_SMALL.render("Matches your checkpoint — same as Continue from title", True, (100, 200, 130))
        surf.blit(ck, (cx - ck.get_width() // 2, detail_y + int(72 * SY)))


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

    high_score, checkpoint_wave, map_unlock = load_save()

    player=None; enemies=[]; boss=None
    wave=0; wave_clear_timer=0; checkpoint_banner=0

    def reset(from_checkpoint=False, start_wave=None):
        nonlocal player,enemies,boss,wave,particles,fire_parts
        nonlocal wave_clear_timer,checkpoint_banner,paused
        if start_wave is not None:
            w0=int(start_wave)
        elif from_checkpoint and checkpoint_wave is not None:
            w0=checkpoint_wave
        else:
            w0=0
        wave=w0; particles=[]; fire_parts=[]; boss=None
        wave_clear_timer=0; checkpoint_banner=0
        paused=False
        player=Player(WIDTH//2,GROUND_Y)
        enemies=spawn_wave(wave) if wave<BOSS_WAVE else []
        if wave>=BOSS_WAVE: boss=Boss(WIDTH+200*SX,GROUND_Y)

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
                    player.try_attack()

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
                    state="worldmap"
                    map_sel=min(map_unlock, len(MAP_NODES)-1)
                if k==pygame.K_c and checkpoint_wave is not None:
                    state="playing"; reset(True)
                if k==pygame.K_t:
                    open_trailer_in_browser()

            elif state=="worldmap":
                if k==pygame.K_ESCAPE:
                    state="intro"
                elif k in(pygame.K_a,pygame.K_LEFT):
                    map_sel=(map_sel-1)%len(MAP_NODES)
                elif k in(pygame.K_d,pygame.K_RIGHT):
                    map_sel=(map_sel+1)%len(MAP_NODES)
                elif k==pygame.K_RETURN:
                    if map_sel<=map_unlock:
                        state="playing"
                        reset(start_wave=map_sel)

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
                    elif k==pygame.K_j:
                        player.try_attack()
                    elif k==pygame.K_l:
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
            draw_world_map(screen, map_sel, map_unlock, checkpoint_wave, pygame.time.get_ticks())

        elif state=="playing":
            is_boss=wave>=BOSS_WAVE
            global COMBAT_HITSTOP
            advance_fire=True
            skip_sim=False
            if not paused:
                combat_shake_tick()
                skip_sim=COMBAT_HITSTOP>0
                if skip_sim:
                    COMBAT_HITSTOP-=1
                advance_fire=not skip_sim
                if not skip_sim:
                    player.try_bow(keys[pygame.K_k] and player.weapon=="bow")

                    fire_timer+=1
                    if fire_timer%3==0:
                        fire_parts.append(Particle(
                            random.randint(0,WIDTH),GROUND_Y-random.randint(0,int(5*SY)),
                            random.choice(FIRE_COLS),vx=random.uniform(-.5,.5)*SX,
                            vy=random.uniform(-2,-.5)*SY,life=random.randint(20,50),size=random.randint(2,4)))

                    all_foes=enemies+([boss] if boss and boss.alive else [])
                    player.update(keys,all_foes,particles)

                    for e in enemies:
                        if e.alive: e.update(player,particles)
                    if boss and boss.alive:
                        boss.update(player,particles)

                    for e in enemies:
                        if not e.alive and not e.counted:
                            player.kills+=1; e.counted=True; play('death')
                            for _ in range(18):
                                particles.append(Particle(e.x,e.y-25*SY,BLOOD_COL,
                                                          vx=random.uniform(-4,4)*SX,vy=random.uniform(-6,-1)*SY))
                    if boss and not boss.alive and not boss.counted:
                        player.kills+=10; boss.counted=True; play('death')
                        for _ in range(40):
                            particles.append(Particle(boss.x,boss.y-30*SY,BLOOD_COL,
                                                      vx=random.uniform(-6,6)*SX,vy=random.uniform(-8,-1)*SY))

                    enemies=[e for e in enemies if e.alive]
                    for p in particles: p.update()
                    particles=[p for p in particles if p.life>0]
                    if checkpoint_banner>0: checkpoint_banner-=1

                    if is_boss:
                        if boss and not boss.alive:
                            state="win"
                            high_score=update_high_score(player.kills)
                            map_unlock=max(map_unlock,BOSS_WAVE)
                            hs,_,mu=load_save()
                            write_save(hs,None,max(mu,map_unlock))
                            checkpoint_wave=None
                            map_unlock=max(map_unlock,mu)
                    else:
                        if not enemies:
                            wave_clear_timer+=1
                            if wave_clear_timer==1: play('wave_clear')
                            if wave_clear_timer>100:
                                wave+=1
                                map_unlock=max(map_unlock,wave)
                                write_save(high_score,checkpoint_wave,map_unlock)
                                if wave%2==0 and wave<BOSS_WAVE:
                                    save_checkpoint(wave,player.kills)
                                    high_score,checkpoint_wave,map_unlock=load_save()
                                    checkpoint_banner=200; play('checkpoint')
                                if wave>=BOSS_WAVE:
                                    boss=Boss(WIDTH+100*SX,GROUND_Y); enemies=[]
                                else:
                                    enemies=spawn_wave(wave)
                                wave_clear_timer=0
                        else:
                            wave_clear_timer=0

                    if player.hp<=0:
                        map_unlock=max(map_unlock,wave)
                        high_score=update_high_score(player.kills)
                        hs,ck,mu=load_save()
                        write_save(high_score,ck,max(mu,map_unlock))
                        map_unlock=max(map_unlock,mu)
                        state="gameover"
            else:
                advance_fire=False

            shaking=not paused and COMBAT_SHAKE_FRAMES>0
            surf=pygame.Surface((WIDTH,HEIGHT)) if shaking else screen
            if shaking:
                surf.fill((14,10,8))

            draw_background(surf,buildings,fire_parts,advance_fire=advance_fire)
            for e in enemies: e.draw(surf)
            if boss: boss.draw(surf)
            for p in particles: p.draw(surf)
            player.draw(surf)

            wlbl="BOSS WAVE" if is_boss else f"WAVE {wave+1}/{BOSS_WAVE}"
            ecnt=len(enemies) if not is_boss else (1 if boss and boss.alive else 0)
            draw_hud(surf,player,wlbl,ecnt,high_score,checkpoint_wave)

            if 0<wave_clear_timer<100 and not is_boss:
                if wave<BOSS_WAVE:
                    txt=FONT_MED.render(f"WAVE {wave} CLEARED — Prepare...",True,(200,180,80))
                else:
                    txt=FONT_MED.render("BOSS INCOMING — SEBASTIAN MONROE!",True,(220,60,40))
                surf.blit(txt,(WIDTH//2-txt.get_width()//2,HEIGHT//2-int(20*SY)))

            if checkpoint_banner>0:
                cp=FONT_MED.render(f"CHECKPOINT SAVED  (Wave {checkpoint_wave+1})",True,(100,230,100))
                surf.blit(cp,(WIDTH//2-cp.get_width()//2,HEIGHT//2+int(55*SY)))

            if shaking:
                screen.fill((14,10,8))
                sx,sy_=combat_shake_offset()
                screen.blit(surf,(sx,sy_))

            if paused:
                draw_pause_overlay(screen,MASTER_VOLUME)

        elif state in("gameover","win"):
            draw_background(screen,buildings,[])
            draw_gameover(screen,player,high_score,win=(state=="win"))

        pygame.display.flip()

if __name__=="__main__":
    main()
