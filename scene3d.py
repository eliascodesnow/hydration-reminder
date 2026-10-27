"""A small software 3D renderer for the pouring-water scene (Pillow + numpy).

No GPU or extra 3D libraries needed. Everything is real 3D maths:

* perspective camera that gently orbits and bobs
* tapered glass built from a mesh, shaded with fresnel + specular highlights
* water volume whose surface is a displaced mesh (ripples and slosh), shaded
  from its true surface normals
* a tilting 3D bottle that pours a stream along a real gravity arc
* splash particles, rising bubbles, condensation drops, floor shadow/glow

`Scene.render(t)` returns a PIL RGB image for time `t` seconds.
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw

# ---- world geometry (arbitrary units; the glass is ~2 tall) ----------------
R_TOP, R_BOT = 1.0, 0.74      # glass radius at the rim / at the base
H = 2.15                      # glass height
BASE = 0.17                   # thickness of the glass bottom
WALL = 0.07                   # wall thickness
G = 9.0                       # gravity for the stream and splashes
SEG = 40                      # segments around the glass

MOUTH = np.array([-0.42, 2.78, 0.0])   # where the bottle's mouth sits while pouring
BOTTLE_SCALE = 0.78
BOTTLE_LEN = 2.4 * BOTTLE_SCALE
TILT_POUR = math.radians(104)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smoothstep(a, b, x):
    u = clamp((x - a) / (b - a))
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


def ease_out(u):
    return 1 - (1 - clamp(u)) ** 3


def ease_in(u):
    return clamp(u) ** 3


def norm(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def r_glass(y):
    return R_BOT + (R_TOP - R_BOT) * (y / H)


def r_inner(y):
    return r_glass(y) - WALL


class Camera:
    def __init__(self, f, dist, cx, cy):
        self.f, self.dist, self.cx, self.cy = f, dist, cx, cy
        self.zoom = 1.0
        self.R = np.eye(3)
        self.pos = np.array([0.0, 0.0, dist])
        self.set(0.0, 0.4)

    def set(self, yaw, pitch, zoom=1.0):
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
        rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        self.R = rx @ ry
        self.zoom = zoom

    def view(self, p):
        return np.asarray(p) @ self.R.T

    def project(self, v):
        s = self.f * self.zoom / (self.dist - v[..., 2])
        return self.cx + v[..., 0] * s, self.cy - v[..., 1] * s, s


def _quad_centers(a):
    return (a[:-1, :-1] + a[1:, :-1] + a[:-1, 1:] + a[1:, 1:]) * 0.25


def _paste_quads(canvas, sx, sy, zq, rgba, keep=None):
    """Draw a quad mesh (far to near) on its own layer, then alpha-paste it.

    Drawing on a separate transparent layer means neighbouring translucent quads
    overwrite instead of double-blending, so there are no visible seams.
    """
    rows, cols = zq.shape
    idx = np.flatnonzero(np.ones(zq.shape, bool) if keep is None else keep)
    if idx.size == 0:
        return
    order = idx[np.argsort(zq.ravel()[idx])]
    w, h = canvas.size
    x0, y0 = max(int(sx.min()) - 3, 0), max(int(sy.min()) - 3, 0)
    x1, y1 = min(int(sx.max()) + 4, w), min(int(sy.max()) + 4, h)
    if x1 <= x0 or y1 <= y0:
        return
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    X = (sx - x0).tolist()
    Y = (sy - y0).tolist()
    cols_l = np.clip(rgba, 0, 255).astype(np.uint8).reshape(-1, 4).tolist()
    for k in order.tolist():
        i, j = divmod(k, cols)
        col = tuple(cols_l[k])
        ld.polygon([(X[i][j], Y[i][j]), (X[i][j + 1], Y[i][j + 1]),
                    (X[i + 1][j + 1], Y[i + 1][j + 1]), (X[i + 1][j], Y[i + 1][j])],
                   fill=col, outline=col)
    canvas.paste(layer, (x0, y0), layer)


class Scene:
    # Timeline (seconds). Other modules read these to sync sound and speech.
    T_STREAM = 0.55                       # stream leaves the bottle
    T_POUR = 3.2                          # how long the pour lasts
    T_TAIL = T_STREAM + T_POUR            # stream tail leaves the bottle
    FLIGHT = 0.30                         # time for water to reach the glass
    FILL_MAX = 0.84                       # glass fills to this fraction of its height

    sound_start = T_STREAM + FLIGHT       # splash begins
    fill_end = T_TAIL + FLIGHT            # last of the water lands

    def __init__(self, width, height, bg, theme, ss=2, seed=None):
        self.W, self.H, self.ss = width, height, ss
        self.theme = theme
        self.rng = random.Random(seed)
        self._set_bg(bg)

        f = 720.0 * (height / 330.0) * ss
        self.cam = Camera(f=f, dist=11.0, cx=width * ss * 0.63, cy=height * ss * 0.79)

        self._build_geometry()
        self._build_decor()

        self.last_t = 0.0
        self.splash = []      # [x, y, z, vx, vy, vz, r]
        self.bubbles = []     # [x, y, z, vy, r, phase]
        self.sparkles = []    # celebration stars
        self.t_cele = None

    # ------------------------------------------------------------------ setup
    def _set_bg(self, bg):
        self.bg = bg.resize((self.W * self.ss, self.H * self.ss), Image.BILINEAR)

    def set_quality(self, ss):
        if ss == self.ss:
            return
        ratio = ss / self.ss
        self.ss = ss
        self.cam.f *= ratio
        self.cam.cx *= ratio
        self.cam.cy *= ratio
        self.bg = self.bg.resize((self.W * ss, self.H * ss), Image.BILINEAR)

    def _build_geometry(self):
        th = np.linspace(0, 2 * np.pi, SEG + 1)
        self.cos_t, self.sin_t = np.cos(th), np.sin(th)
        ones = np.ones(SEG + 1)

        # glass wall: 2 bands (thick bottom, then the wall itself)
        ys = np.array([0.0, BASE, H])
        rr = r_glass(ys)
        self.wall_P = np.stack([rr[:, None] * self.cos_t, ys[:, None] * ones, rr[:, None] * self.sin_t], -1)
        slope = (R_TOP - R_BOT) / H
        n = norm(np.stack([self.cos_t, -slope * ones, self.sin_t], -1))
        self.wall_n = norm(n[:-1] + n[1:])                      # (SEG, 3), per quad column
        self.wall_n = np.broadcast_to(self.wall_n, (2, SEG, 3))

        # rim ring (flat, at the top)
        rim_r = np.array([R_TOP, R_TOP - WALL])
        self.rim_P = np.stack([rim_r[:, None] * self.cos_t, np.full((2, SEG + 1), H),
                               rim_r[:, None] * self.sin_t], -1)

        # bottle: surface of revolution
        prof = [(0.0, 0.0), (0.40, 0.0), (0.50, 0.08), (0.53, 0.25), (0.53, 0.55), (0.53, 0.72),
                (0.53, 1.03), (0.53, 1.20), (0.53, 1.38), (0.50, 1.60), (0.40, 1.80), (0.27, 1.97),
                (0.22, 2.10), (0.22, 2.32), (0.26, 2.34), (0.26, 2.40)]
        self.b_prof = np.array(prof) * BOTTLE_SCALE
        self.b_label_row = 5                                     # white label; rows 4 and 6 are stripes
        bn = 36
        bth = np.linspace(0, 2 * np.pi, bn + 1)
        self.b_cos, self.b_sin = np.cos(bth), np.sin(bth)
        bP = np.stack([self.b_prof[:, 0:1] * self.b_cos, np.repeat(self.b_prof[:, 1:2], bn + 1, 1),
                       self.b_prof[:, 0:1] * self.b_sin], -1)
        self.b_P = bP
        d = np.diff(self.b_prof, axis=0)
        seg_n = np.stack([d[:, 1], -d[:, 0]], -1)
        seg_n = seg_n / np.maximum(np.linalg.norm(seg_n, axis=1, keepdims=True), 1e-9)
        mid = (bth[:-1] + bth[1:]) / 2
        self.b_n = np.stack([seg_n[:, 0:1] * np.cos(mid), np.repeat(seg_n[:, 1:2], bn, 1),
                             seg_n[:, 0:1] * np.sin(mid)], -1)   # (rows, bn, 3)

        # lights (world space)
        self.L1 = norm(np.array([-0.55, 0.85, 0.65]))
        self.L2 = norm(np.array([0.85, 0.30, 0.45]))

    def _build_decor(self):
        r = self.rng
        W, H_ = self.W * self.ss, self.H * self.ss
        self.orbs = [dict(x=r.random() * W, y=r.random() * H_, r=r.uniform(4, 22) * self.ss,
                          v=r.uniform(6, 22) * self.ss, ph=r.random() * 6.28, a=r.randint(14, 34))
                     for _ in range(16)]
        self.rays = [dict(x=W * (0.08 + 0.26 * i) + r.uniform(-20, 20), w=r.uniform(40, 80) * self.ss,
                          ph=r.random() * 6.28, a=r.randint(9, 15)) for i in range(4)]
        # condensation droplets stuck to the glass: (theta, y, size)
        self.drops = [(r.uniform(0, 2 * math.pi), r.uniform(BASE + 0.1, H - 0.3), r.uniform(0.012, 0.03))
                      for _ in range(26)]

    # ---------------------------------------------------------------- timeline
    def level_at(self, t):
        a, b = self.sound_start, self.fill_end
        u = clamp((t - a) / (b - a))
        u = 0.75 * u + 0.25 * smoothstep(0, 1, u)               # mostly steady flow, soft ends
        return BASE + (H * self.FILL_MAX - BASE) * u

    def _pouring_landed(self, t):
        return self.sound_start <= t < self.fill_end

    def bottle_pose(self, t):
        """Returns (tilt radians, pivot xyz, mouth xyz) of the bottle at time t."""
        enter = ease_out(t / 0.62)
        exit_u = ease_in((t - (self.T_TAIL + 0.15)) / 0.75)
        pour_u = clamp((t - self.T_STREAM) / self.T_POUR)

        tilt = TILT_POUR * enter + math.radians(8) * pour_u
        tilt *= (1 - exit_u)
        away = np.array([-1.0, 1.0, 0.0]) * (3.0 * (1 - enter) + 4.0 * exit_u)

        ca, sa = math.cos(tilt), math.sin(tilt)
        local_mouth = np.array([0.0, BOTTLE_LEN, 0.0])
        rot_mouth = np.array([local_mouth[0] * ca + local_mouth[1] * sa,
                              -local_mouth[0] * sa + local_mouth[1] * ca, 0.0])
        # keep the mouth anchored over the glass while pouring; rest of the time follow the tilt
        anchor = MOUTH * (1 - exit_u) + np.array([-3.4, 3.0, 0.0]) * exit_u
        mouth = anchor + away
        pivot = mouth - rot_mouth
        return tilt, pivot, mouth

    # ------------------------------------------------------------ simulation
    def celebrate(self, t):
        self.t_cele = t
        r = self.rng
        for _ in range(42):
            ang = r.random() * 2 * math.pi
            rad = r.uniform(0.2, 1.0)
            sp = r.uniform(0.6, 1.4)
            self.sparkles.append([math.cos(ang) * rad, H * 0.85, math.sin(ang) * rad,
                                  math.cos(ang) * sp, r.uniform(1.6, 3.4), math.sin(ang) * sp,
                                  r.uniform(0.05, 0.11), r.random() * 6.28, t])

    def _update(self, t, level):
        dt = clamp(t - self.last_t, 0.0, 0.08)
        self.last_t = t
        if dt <= 0:
            return
        r = self.rng
        landing = self.sound_start <= t < self.fill_end
        ri = r_inner(level) * 0.92

        if landing:
            for _ in range(int(70 * dt + r.random())):
                a, sp = r.random() * 2 * math.pi, r.uniform(0.12, 0.6)
                self.splash.append([r.uniform(-0.05, 0.05), level + 0.01, r.uniform(-0.05, 0.05),
                                    math.cos(a) * sp, r.uniform(0.9, 2.5), math.sin(a) * sp,
                                    r.uniform(0.018, 0.042)])
            for _ in range(int(11 * dt + r.random())):
                self.bubbles.append([r.uniform(-0.18, 0.18), max(BASE + 0.05, level - r.uniform(0.15, 0.7)),
                                     r.uniform(-0.18, 0.18), r.uniform(0.5, 1.0), r.uniform(0.018, 0.05),
                                     r.random() * 6.28])
        self.splash = self.splash[-140:]
        self.bubbles = self.bubbles[-70:]

        alive = []
        for p in self.splash:
            p[4] -= G * dt
            p[0] += p[3] * dt
            p[1] += p[4] * dt
            p[2] += p[5] * dt
            if math.hypot(p[0], p[2]) > ri:
                p[3] *= -0.4
                p[5] *= -0.4
            if p[1] > level - 0.005 or p[4] > 0:
                alive.append(p)
        self.splash = alive

        alive = []
        for b in self.bubbles:
            b[1] += b[3] * dt
            b[0] += math.sin(t * 5 + b[5]) * 0.12 * dt
            b[2] += math.cos(t * 4 + b[5]) * 0.12 * dt
            if b[1] < level - 0.02:
                alive.append(b)
        self.bubbles = alive

        alive = []
        for s in self.sparkles:
            s[4] -= 2.2 * dt
            s[0] += s[3] * dt
            s[1] += s[4] * dt
            s[2] += s[5] * dt
            if t - s[8] < 1.1:
                alive.append(s)
        self.sparkles = alive

    # ---------------------------------------------------------------- waves
    def _ripple_env(self, t):
        if t < self.sound_start:
            return 0.0
        if t < self.fill_end:
            return 1.0
        return math.exp(-(t - self.fill_end) * 1.3)

    def _wave(self, x, z, t, env, slosh):
        r = np.sqrt(x * x + z * z)
        h = 0.050 * env * np.exp(-1.3 * r) * np.sin(15 * r - 11 * t)
        h += 0.022 * env * np.exp(-0.8 * r) * np.sin(8.5 * r - 6.5 * t + 1.0)
        h += 0.024 * slosh * (x * np.sin(2.3 * t + 0.5) + z * np.cos(1.9 * t))
        h += 0.004 * np.sin(8 * x + 2.9 * t) + 0.004 * np.sin(7 * z - 2.1 * t + 1.3)
        if self.t_cele is not None and t > self.t_cele:
            k = t - self.t_cele
            h += 0.04 * math.exp(-k * 2.0) * np.sin(13 * r - 12 * k)
        return h

    # ---------------------------------------------------------------- drawing
    def _bg_layer(self, img, d, t):
        ss = self.ss
        W, H_ = self.W * ss, self.H * ss
        ar, ag, ab = self.theme["accent"]
        for ray in self.rays:
            sway = math.sin(t * 0.4 + ray["ph"]) * 26 * ss
            x = ray["x"] + sway
            w = ray["w"]
            a = int(ray["a"] * (0.75 + 0.25 * math.sin(t * 0.9 + ray["ph"])))
            d.polygon([(x - w * 0.3, 0), (x + w * 0.3, 0), (x + w * 1.1 + 70 * ss, H_), (x - w * 0.6 + 70 * ss, H_)],
                      fill=(ar, ag, ab, a))
        for o in self.orbs:
            y = (o["y"] - o["v"] * t) % (H_ + 2 * o["r"]) - o["r"]
            x = o["x"] + math.sin(t * 0.7 + o["ph"]) * 10 * ss
            r = o["r"]
            d.ellipse([x - r, y - r, x + r, y + r], fill=(ar, ag, ab, o["a"] // 2),
                      outline=(255, 255, 255, o["a"]), width=max(1, ss // 2))

    def _floor(self, img, d, t, level, cam):
        frac = clamp((level - BASE) / (H * self.FILL_MAX - BASE))
        gr, gg, gb = self.theme["glow"]
        th = np.linspace(0, 2 * np.pi, 48)
        for rad, a, col in [(2.5, 10, (gr, gg, gb)), (2.1, 14, (gr, gg, gb)), (1.75, 18, (gr, gg, gb))]:
            a = int(a * (0.35 + 0.65 * frac))
            P = np.stack([rad * np.cos(th), np.zeros_like(th), rad * np.sin(th)], -1)
            sx, sy, _ = cam.project(cam.view(P))
            d.polygon(list(zip(sx.tolist(), sy.tolist())), fill=col + (a,))
        for rad, a in [(1.65, 22), (1.4, 30), (1.18, 40)]:
            P = np.stack([rad * np.cos(th), np.zeros_like(th), rad * np.sin(th)], -1)
            sx, sy, _ = cam.project(cam.view(P))
            d.polygon(list(zip(sx.tolist(), sy.tolist())), fill=(0, 0, 0, a))

    def _glass_rgba(self, pv, nv, mul, back):
        cam = self.cam
        v = norm(cam.pos - pv)
        ndv = (nv * v).sum(-1)
        sgn = np.where(ndv >= 0, 1.0, -1.0)
        ne = nv * sgn[..., None]
        ndv = np.abs(ndv)
        fres = (1 - np.clip(ndv, 0, 1)) ** 3
        l1 = cam.R @ self.L1
        l2 = cam.R @ self.L2
        s1 = np.clip((ne * norm(l1 + v)).sum(-1), 0, 1) ** 70
        s2 = np.clip((ne * norm(l2 + v)).sum(-1), 0, 1) ** 36
        alpha = (10 + 150 * fres + 210 * s1 + 90 * s2) * mul
        if back:
            alpha = alpha * 0.55
        white = np.clip(s1 * 1.4 + s2 * 0.7, 0, 1)
        base = np.array([200, 230, 255.0])
        edge = np.array([120, 205, 255.0])
        rgb = base * (1 - fres[..., None]) + edge * fres[..., None]
        rgb = rgb + (255 - rgb) * white[..., None]
        return np.concatenate([rgb, alpha[..., None]], -1), ndv, sgn

    def _glass_pass(self, img, front):
        cam = self.cam
        V = cam.view(self.wall_P)
        sx, sy, _ = cam.project(V)
        pq = _quad_centers(V)
        nv = cam.view(self.wall_n)
        mul = np.array([2.6, 1.0])[:, None]                       # thick base is more opaque
        rgba, _, sgn = self._glass_rgba(pq, nv, mul, back=not front)
        keep = (sgn > 0) if front else (sgn < 0)
        _paste_quads(img, sx, sy, pq[..., 2], rgba, keep)

    def _water_body(self, img, t, level):
        cam = self.cam
        NB = 5
        ys = BASE + (level - BASE) * np.linspace(0, 1, NB + 1)
        rr = r_inner(ys)
        ones = np.ones(SEG + 1)
        P = np.stack([rr[:, None] * self.cos_t, ys[:, None] * ones, rr[:, None] * self.sin_t], -1)
        slope = (R_TOP - R_BOT) / H
        n = norm(np.stack([self.cos_t, -slope * ones, self.sin_t], -1))
        nq = norm(n[:-1] + n[1:])
        nq = np.broadcast_to(nq, (NB, SEG, 3))
        V = cam.view(P)
        sx, sy, _ = cam.project(V)
        pq = _quad_centers(V)
        nv = cam.view(nq)
        v = norm(cam.pos - pq)
        ndv = (nv * v).sum(-1)
        fres = (1 - np.abs(np.clip(ndv, -1, 1))) ** 2.5
        ndl = np.clip((nv * (cam.R @ self.L1)).sum(-1), 0, 1)
        deep = np.array([12, 76, 160.0])
        top = np.array([88, 190, 242.0])
        # depth fraction of each band (0 = bottom of the water, 1 = surface)
        frac = ((np.arange(NB) + 0.5) / NB)[:, None, None]
        rgb = deep * (1 - frac) + top * frac
        rgb = rgb * (0.72 + 0.42 * ndl[..., None])
        rgb = rgb + (np.array([150, 225, 255.0]) - rgb) * (0.5 * fres[..., None])
        for front in (False, True):
            alpha = (95 + 110 * fres) if not front else (120 + 90 * fres)
            rgba = np.concatenate([rgb, alpha[..., None]], -1)
            keep = (ndv > 0) if front else (ndv <= 0)
            _paste_quads(img, sx, sy, pq[..., 2], rgba, keep)

    def _water_surface(self, img, d, t, level):
        cam = self.cam
        NR = 7
        rho = (np.arange(NR + 1) / NR) ** 0.85
        rs = r_inner(level) * 0.985
        X = rho[:, None] * rs * self.cos_t[None, :]
        Z = rho[:, None] * rs * self.sin_t[None, :]
        env = self._ripple_env(t)
        slosh = 0.35 + 0.65 * env
        Y = level + self._wave(X, Z, t, env, slosh)
        e = 0.02
        gx = (self._wave(X + e, Z, t, env, slosh) - self._wave(X - e, Z, t, env, slosh)) / (2 * e)
        gz = (self._wave(X, Z + e, t, env, slosh) - self._wave(X, Z - e, t, env, slosh)) / (2 * e)
        N = norm(np.stack([-gx, np.ones_like(gx), -gz], -1))
        P = np.stack([X, Y, Z], -1)
        V = cam.view(P)
        sx, sy, _ = cam.project(V)
        pq = _quad_centers(V)
        nq = norm(_quad_centers(cam.view(N)))
        v = norm(cam.pos - pq)
        ndv = np.clip((nq * v).sum(-1), 0, 1)
        fres = np.clip((1 - ndv) ** 3 * 1.2 + 0.12, 0, 1)
        l1 = cam.R @ self.L1
        refl = 2 * ndv[..., None] * nq - v
        spec = np.clip((refl * l1).sum(-1), 0, 1) ** 36
        ndl = np.clip((nq * l1).sum(-1), 0, 1)
        deep = np.array([22, 112, 200.0])
        sky = np.array([165, 220, 252.0])
        rgb = deep * (1 - fres[..., None]) + sky * fres[..., None]
        rgb = rgb * (0.82 + 0.3 * ndl[..., None])
        rgb = rgb + (255 - rgb) * np.clip(spec * 1.3, 0, 1)[..., None]
        # brighten crests of the ripples a little
        crest = np.clip(_quad_centers(Y) - level, 0, 0.1) * 5
        rgb = rgb + (255 - rgb) * crest[..., None]
        alpha = np.full(spec.shape, 218.0)
        rgba = np.concatenate([rgb, alpha[..., None]], -1)
        _paste_quads(img, sx, sy, pq[..., 2], rgba)
        # meniscus ring where the water meets the glass
        ring = V[-1]
        rx, ry, _ = cam.project(ring)
        d.line(list(zip(rx.tolist(), ry.tolist())), fill=(214, 240, 255, 130), width=max(1, self.ss))

    def _bubbles(self, d, level):
        cam = self.cam
        for x, y, z, vy, r, ph in self.bubbles:
            sx, sy, s = cam.project(cam.view(np.array([x, y, z])))
            rad = max(1.5, r * s)
            d.ellipse([sx - rad, sy - rad, sx + rad, sy + rad], fill=(200, 235, 255, 40),
                      outline=(225, 245, 255, 170), width=max(1, self.ss // 2))
            d.ellipse([sx - rad * 0.55, sy - rad * 0.6, sx - rad * 0.15, sy - rad * 0.2], fill=(255, 255, 255, 190))

    def _bottle(self, img, d, t):
        cam = self.cam
        tilt, pivot, mouth = self.bottle_pose(t)
        ca, sa = math.cos(tilt), math.sin(tilt)

        def rot(a):
            x, y, z = a[..., 0], a[..., 1], a[..., 2]
            return np.stack([x * ca + y * sa, -x * sa + y * ca, z], -1)

        P = rot(self.b_P) + pivot
        V = cam.view(P)
        sx, sy, _ = cam.project(V)
        pq = _quad_centers(V)
        nv = cam.view(rot(self.b_n))
        v = norm(cam.pos - pq)
        ndv = (nv * v).sum(-1)
        sgn = np.where(ndv >= 0, 1.0, -1.0)
        ne = nv * sgn[..., None]
        ndva = np.abs(ndv)
        fres = (1 - np.clip(ndva, 0, 1)) ** 2.5
        l1 = cam.R @ self.L1
        ndl = np.clip((ne * l1).sum(-1), 0, 1)
        spec = np.clip((ne * norm(l1 + v)).sum(-1), 0, 1) ** 60
        rows = pq.shape[0]
        base = np.broadcast_to(np.array([58, 156, 232.0]), pq.shape)
        rgb = base * (0.62 + 0.55 * ndl[..., None]) + (np.array([170, 228, 255.0]) - base) * (0.55 * fres[..., None])
        label = np.zeros(pq.shape[:2], bool)
        stripe = np.zeros(pq.shape[:2], bool)
        label[self.b_label_row, :] = True
        stripe[self.b_label_row - 1, :] = True
        stripe[self.b_label_row + 1, :] = True
        rgb = np.where(label[..., None], np.array([238, 246, 255.0]) * (0.75 + 0.3 * ndl[..., None]), rgb)
        rgb = np.where(stripe[..., None], np.array([22, 96, 190.0]) * (0.7 + 0.5 * ndl[..., None]), rgb)
        rgb = rgb + (255 - rgb) * np.clip(spec * 1.4, 0, 1)[..., None]
        for front in (False, True):
            alpha = np.where(label | stripe, 225.0 if front else 150.0, (125 + 90 * fres) if front else 70.0)
            alpha = alpha + 120 * spec
            rgba = np.concatenate([rgb, alpha[..., None]], -1)
            keep = (sgn > 0) if front else (sgn < 0)
            _paste_quads(img, sx, sy, pq[..., 2], rgba, keep)
        # open mouth
        th = np.linspace(0, 2 * np.pi, 20)
        m = np.stack([0.21 * BOTTLE_SCALE * np.cos(th), np.full_like(th, BOTTLE_LEN), 0.21 * BOTTLE_SCALE * np.sin(th)], -1)
        mx, my, _ = cam.project(cam.view(rot(m) + pivot))
        d.polygon(list(zip(mx.tolist(), my.tolist())), fill=(10, 52, 104, 215))

    def _stream_path(self, t, level):
        tilt, pivot, mouth = self.bottle_pose(t)
        dx, dy = math.sin(tilt), math.cos(tilt)
        if dx < 0.25:
            return None
        c = max(-mouth[0] / dx, 0.05)
        drop = mouth[1] + dy * c - level
        tau = math.sqrt(max(2 * drop / G, 0.012))
        speed = c / tau
        return mouth, np.array([dx, dy, 0.0]), speed, tau

    def _stream(self, img, d, t, level):
        if t < self.T_STREAM:
            return
        u_head = clamp((t - self.T_STREAM) / self.FLIGHT)
        u_tail = clamp((t - self.T_TAIL) / self.FLIGHT)
        if u_tail >= 1.0:
            return
        sp = self._stream_path(t, level)
        if sp is None:
            return
        mouth, dvec, speed, tau = sp
        cam = self.cam
        n = 24
        u = np.linspace(u_tail, u_head, n)
        ta = u * tau
        pts = mouth[None, :] + speed * dvec[None, :] * ta[:, None]
        pts[:, 1] -= 0.5 * G * ta * ta
        V = cam.view(pts)
        sx, sy, s = cam.project(V)
        wob = 1 + 0.07 * np.sin(u * 28 - t * 24)
        taper = np.minimum(np.minimum((u - u_tail) * 18 + 0.25, 1.0), (u_head - u) * 18 + 0.35)
        half = 0.082 * (1.0 - 0.28 * u) * wob * np.clip(taper, 0.15, 1.0) * s
        tx, ty = np.gradient(sx), np.gradient(sy)
        ln = np.maximum(np.hypot(tx, ty), 1e-6)
        nx, ny = -ty / ln, tx / ln
        Lx, Ly = sx + nx * half, sy + ny * half
        Rx, Ry = sx - nx * half, sy - ny * half
        w, h = img.size
        x0, y0 = max(int(min(Lx.min(), Rx.min())) - 3, 0), max(int(min(Ly.min(), Ry.min())) - 3, 0)
        x1, y1 = min(int(max(Lx.max(), Rx.max())) + 4, w), min(int(max(Ly.max(), Ry.max())) + 4, h)
        if x1 <= x0 or y1 <= y0:
            return
        layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for i in range(n - 1):
            quad = [(Lx[i] - x0, Ly[i] - y0), (Lx[i + 1] - x0, Ly[i + 1] - y0),
                    (Rx[i + 1] - x0, Ry[i + 1] - y0), (Rx[i] - x0, Ry[i] - y0)]
            shade = 0.88 + 0.12 * math.sin(i * 0.9 - t * 18)
            col = (int(96 * shade), int(186 * shade), int(250 * shade), 205)
            ld.polygon(quad, fill=col, outline=col)
        # bright core highlight on the lit side
        for i in range(n - 1):
            a0, a1 = 0.55, 0.15
            quad = [(sx[i] + nx[i] * half[i] * a0 - x0, sy[i] + ny[i] * half[i] * a0 - y0),
                    (sx[i + 1] + nx[i + 1] * half[i + 1] * a0 - x0, sy[i + 1] + ny[i + 1] * half[i + 1] * a0 - y0),
                    (sx[i + 1] + nx[i + 1] * half[i + 1] * a1 - x0, sy[i + 1] + ny[i + 1] * half[i + 1] * a1 - y0),
                    (sx[i] + nx[i] * half[i] * a1 - x0, sy[i] + ny[i] * half[i] * a1 - y0)]
            ld.polygon(quad, fill=(236, 249, 255, 175))
        img.paste(layer, (x0, y0), layer)

        # foam where the stream lands
        if u_head >= 1.0:
            th = np.linspace(0, 2 * np.pi, 20)
            for rad, a in [(0.20, 50), (0.12, 90)]:
                P = np.stack([rad * np.cos(th), np.full_like(th, level + 0.01), rad * np.sin(th)], -1)
                fx, fy, _ = cam.project(cam.view(P))
                d.polygon(list(zip(fx.tolist(), fy.tolist())), fill=(240, 250, 255, a))

    def _particles(self, d):
        cam = self.cam
        for x, y, z, vx, vy, vz, r in self.splash:
            sx, sy, s = cam.project(cam.view(np.array([x, y, z])))
            rad = max(1.5, r * s)
            d.ellipse([sx - rad, sy - rad, sx + rad, sy + rad], fill=(170, 220, 255, 200))
            d.ellipse([sx - rad * 0.5, sy - rad * 0.6, sx - rad * 0.05, sy - rad * 0.1], fill=(255, 255, 255, 230))

    def _rim_and_drops(self, img, d, t, level):
        cam = self.cam
        V = cam.view(self.rim_P)
        sx, sy, _ = cam.project(V)
        pq = _quad_centers(V)
        nv = cam.view(np.broadcast_to(np.array([0.0, 1.0, 0.0]), (1, SEG, 3)))
        l1 = cam.R @ self.L1
        shade = 0.55 + 0.45 * np.clip((nv * l1).sum(-1), 0, 1)
        # a bright arc travelling around the rim as the camera moves
        ang = np.arctan2(pq[..., 2], pq[..., 0])
        arc = np.clip(np.cos(ang - 0.9), 0, 1) ** 4
        rgb = np.broadcast_to(np.array([225, 243, 255.0]), pq.shape) * shade[..., None]
        rgb = rgb + (255 - rgb) * (0.7 * arc[..., None])
        alpha = 120 + 110 * arc
        rgba = np.concatenate([rgb, alpha[..., None]], -1)
        _paste_quads(img, sx, sy, pq[..., 2], rgba)
        # outer rim line
        d.line(list(zip(sx[0].tolist(), sy[0].tolist())), fill=(235, 248, 255, 160), width=max(1, self.ss))

        # condensation: appears as the glass fills with cold water
        cold = smoothstep(self.sound_start, self.fill_end, t)
        if cold <= 0:
            return
        for th, y, size in self.drops:
            if y > level + 0.25:
                continue
            r = r_glass(y) + 0.004
            p = np.array([r * math.cos(th), y, r * math.sin(th)])
            v = cam.view(p)
            n = cam.view(np.array([math.cos(th), 0.0, math.sin(th)]))
            if n[2] < 0.25:
                continue
            x, yy, s = cam.project(v)
            rad = max(1.0, size * s)
            a = int(110 * cold)
            d.ellipse([x - rad, yy - rad * 1.25, x + rad, yy + rad * 1.25], fill=(215, 240, 255, a // 2),
                      outline=(240, 250, 255, a))
            d.ellipse([x - rad * 0.5, yy - rad * 0.7, x - rad * 0.05, yy - rad * 0.2], fill=(255, 255, 255, a + 60))

    def _celebrate_fx(self, d, t):
        if self.t_cele is None:
            return
        cam = self.cam
        k = t - self.t_cele
        if 0 <= k < 1.2:
            th = np.linspace(0, 2 * np.pi, 56)
            for off, base_a in ((0.0, 150), (0.18, 90)):
                kk = k - off
                if kk < 0:
                    continue
                rad = 1.1 + 1.7 * ease_out(kk / 1.0)
                a = int(base_a * (1 - clamp(kk / 1.0)))
                P = np.stack([rad * np.cos(th), np.full_like(th, 0.01), rad * np.sin(th)], -1)
                sx, sy, _ = cam.project(cam.view(P))
                d.line(list(zip(sx.tolist(), sy.tolist())) + [(sx[0], sy[0])],
                       fill=self.theme["accent"] + (a,), width=max(2, self.ss * 2))
        for x, y, z, vx, vy, vz, size, ph, born in self.sparkles:
            sx, sy, s = cam.project(cam.view(np.array([x, y, z])))
            life = clamp((t - born) / 1.1)
            a = int(255 * (1 - life) ** 0.8)
            rad = size * s * (0.6 + 0.6 * math.sin(t * 14 + ph) ** 2)
            col = (255, 244, 205, a)
            d.line([(sx - rad, sy), (sx + rad, sy)], fill=col, width=max(1, self.ss))
            d.line([(sx, sy - rad), (sx, sy + rad)], fill=col, width=max(1, self.ss))
            r2 = rad * 0.55
            d.line([(sx - r2, sy - r2), (sx + r2, sy + r2)], fill=col[:3] + (a // 2,), width=1)
            d.line([(sx - r2, sy + r2), (sx + r2, sy - r2)], fill=col[:3] + (a // 2,), width=1)

    # ------------------------------------------------------------------ public
    def render(self, t):
        cam = self.cam
        level = self.level_at(t)
        self._update(t, level)

        yaw = 0.30 * math.sin(0.55 * t + 0.4)
        pitch = 0.40 + 0.035 * math.sin(0.8 * t)
        zoom = 1.0 + 0.07 * (1 - ease_out(t / 0.9))
        if self.t_cele is not None and t >= self.t_cele:
            k = t - self.t_cele
            zoom += 0.045 * math.exp(-k * 4.5) * math.sin(k * 14 + 1.5)
        cam.set(yaw, pitch, zoom)

        img = self.bg.copy()
        d = ImageDraw.Draw(img, "RGBA")
        self._bg_layer(img, d, t)
        self._floor(img, d, t, level, cam)

        has_water = level > BASE + 0.02
        self._glass_pass(img, front=False)
        if has_water:
            self._water_body(img, t, level)
            self._water_surface(img, d, t, level)
            self._bubbles(d, level)
        self._bottle(img, d, t)
        self._stream(img, d, t, level)
        self._particles(d)
        self._glass_pass(img, front=True)
        self._rim_and_drops(img, d, t, level)
        self._celebrate_fx(d, t)

        if self.ss > 1:
            img = img.reduce(self.ss)
        return img
