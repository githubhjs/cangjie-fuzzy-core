"""Synthetic sweep generator: an ideal path through the code's key centres plus configurable motor/sensing noise.

NOT real finger or mouse data. Every number in a profile is an assumption (see SPEC.md, section "Noise profiles"); the point of the
profiles is to bracket plausible behaviour, not to measure it. Positions are in key widths, time in ms.

Noise ingredients (all seedable):
  per-trace bias        a constant offset of the whole path (hand posture / pointer calibration)
  waypoint jitter       gaussian error of each intended key position
  start/end offsets     extra gaussian error of the first and last key (landing / release point)
  corner cutting        interior waypoints are pulled toward the chord of their neighbours
  overshoot             interior waypoints and the last key are passed over in the travel direction
  detours               a lateral spur between two keys; this is what produces y-h-y-j-m-n-b-v-c style extra key touches
  smoothing             Catmull-Rom spline through the control points (a mouse path is smooth, a finger path less so)
  speed variation       Fitts-style segment durations x lognormal speed factor, slower near the two ends
  tremor                per-sample gaussian noise
  dwell                 for a repeated letter ('hh'), with probability p_dwell the user pauses on that key; users also sometimes
                        hesitate (a pause on a key that is NOT repeated), and linger a little at the start/end
"""
import math
import random
from dataclasses import dataclass, replace

from sweep.decoder import collapse, repeat_positions


@dataclass(frozen=True)
class NoiseProfile:
    name: str
    sigma_wp: float = 0.2      # key widths
    sigma_bias: float = 0.1
    sigma_start: float = 0.2
    sigma_end: float = 0.2
    corner_cut_max: float = 0.3   # key widths: the corner is cut by up to this much toward the chord of its neighbours
    overshoot_prob: float = 0.3
    overshoot_amt: float = 0.2
    detour_prob: float = 0.1
    detour_amp: float = 0.5
    backtrack_prob: float = 0.0  # per interior waypoint: after reaching it the path goes BACK toward the previous waypoint, then on (y-h-y-j-m ...)
    tremor: float = 0.03
    spline: int = 0           # Catmull-Rom samples per segment; 0 = straight segments
    dt_min: float = 8.0        # ms between samples
    dt_max: float = 16.0
    seg_base_ms: float = 90.0  # Fitts-style segment time: base + slope * log2(1 + D)
    seg_slope_ms: float = 110.0
    speed_sigma: float = 0.25  # lognormal sigma of the per-trace speed factor
    p_dwell: float = 0.85      # chance the user dwells on a repeated letter
    dwell_mean_ms: float = 330.0
    dwell_sd_ms: float = 90.0
    p_hesitate: float = 0.05   # chance of an unintended pause at an interior key
    hesitate_mean_ms: float = 130.0
    hesitate_sd_ms: float = 60.0
    linger_max_ms: float = 120.0   # pause at start and end, uniform 0..this
    event_driven: bool = False  # True: no sample is emitted while the pointer is perfectly still (mouse / touchpad events)

    def scaled(self, k):
        """Noise level k: spatial errors x k, probabilities x k (capped). k = 0 is a noiseless path (dwell kept)."""
        if k == 0:
            return replace(self, sigma_wp=0, sigma_bias=0, sigma_start=0, sigma_end=0, corner_cut_max=0, overshoot_prob=0,
                           overshoot_amt=0, detour_prob=0, detour_amp=0, backtrack_prob=0, tremor=0, spline=0, speed_sigma=0,
                           p_dwell=1.0, dwell_sd_ms=0, p_hesitate=0, linger_max_ms=0)
        return replace(self, sigma_wp=self.sigma_wp * k, sigma_bias=self.sigma_bias * k, sigma_start=self.sigma_start * k,
                       sigma_end=self.sigma_end * k, corner_cut_max=min(0.9, self.corner_cut_max * k),
                       overshoot_prob=min(0.9, self.overshoot_prob * k), overshoot_amt=self.overshoot_amt * k,
                       detour_prob=min(0.6, self.detour_prob * k), backtrack_prob=min(0.8, self.backtrack_prob * k), detour_amp=self.detour_amp * k, tremor=self.tremor * k)


# Assumed typical behaviour. 'mid' level = x1.0. See SPEC.md for the (limited) grounding.
PROFILES = {
    # Phone, finger or thumb on keys ~0.9-1.0 cm wide: big sloppy offsets, mostly straight segments, 60-120 Hz events.
    "finger": NoiseProfile("finger", sigma_wp=0.22, sigma_bias=0.15, sigma_start=0.2, sigma_end=0.2, corner_cut_max=0.45,
                           overshoot_prob=0.3, overshoot_amt=0.2, detour_prob=0.12, detour_amp=0.55, tremor=0.03,
                           spline=0, dt_min=8, dt_max=16, speed_sigma=0.25, p_dwell=0.8),
    # PRIMARY desktop profile: mouse drag over a drawn keyboard. Absolute positions, smooth path, 60-125 Hz, more accurate aim but
    # fast sweeps overshoot; button held = sweep, release = end. Dwell is the only repeat signal.
    "mouse": NoiseProfile("mouse", event_driven=True, sigma_wp=0.14, sigma_bias=0.03, sigma_start=0.12, sigma_end=0.14, corner_cut_max=0.3,
                          overshoot_prob=0.3, overshoot_amt=0.2, detour_prob=0.05, detour_amp=0.4, tremor=0.01,
                          spline=8, dt_min=8, dt_max=16, speed_sigma=0.3, p_dwell=0.9, linger_max_ms=150),
    # Variant of mouse: precision touchpad (relative pointer: the cursor lags the finger, no absolute target feel).
    "touchpad": NoiseProfile("touchpad", event_driven=True, sigma_wp=0.24, sigma_bias=0.05, sigma_start=0.25, sigma_end=0.25, corner_cut_max=0.4,
                             overshoot_prob=0.4, overshoot_amt=0.3, detour_prob=0.10, detour_amp=0.5, tremor=0.02,
                             spline=8, dt_min=8, dt_max=16, speed_sigma=0.35, p_dwell=0.8, linger_max_ms=200),
    # Variant of finger: touch screen on a PC (keys drawn larger in cm than a phone's: smaller error in key widths).
    "touchscreen": NoiseProfile("touchscreen", sigma_wp=0.17, sigma_bias=0.1, sigma_start=0.16, sigma_end=0.16, corner_cut_max=0.35,
                                overshoot_prob=0.3, overshoot_amt=0.15, detour_prob=0.08, detour_amp=0.45, tremor=0.02,
                                spline=0, dt_min=8, dt_max=16, speed_sigma=0.25, p_dwell=0.8),
}

LEVELS = {"oracle": 0.0, "low": 0.5, "mid": 1.0, "high": 1.6, "vhigh": 2.5}


def _spline(pts, per_seg, keep):
    """Centripetal Catmull-Rom through the control points (a smooth hand path that still visits every control point).
    Returns (smoothed points, index of each kept control point in the smoothed list)."""
    if per_seg <= 0 or len(pts) < 3:
        return list(pts), list(keep)
    ext = [(2 * pts[0][0] - pts[1][0], 2 * pts[0][1] - pts[1][1])] + list(pts) + [(2 * pts[-1][0] - pts[-2][0], 2 * pts[-1][1] - pts[-2][1])]
    out, where = [], {}
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        t0 = 0.0
        t1 = t0 + max(1e-6, math.hypot(p1[0] - p0[0], p1[1] - p0[1])) ** 0.5
        t2 = t1 + max(1e-6, math.hypot(p2[0] - p1[0], p2[1] - p1[1])) ** 0.5
        t3 = t2 + max(1e-6, math.hypot(p3[0] - p2[0], p3[1] - p2[1])) ** 0.5
        where[i - 1] = len(out)
        for s in range(per_seg):
            t = t1 + (t2 - t1) * s / per_seg
            pt = []
            for d in (0, 1):
                a1 = (t1 - t) / (t1 - t0) * p0[d] + (t - t0) / (t1 - t0) * p1[d]
                a2 = (t2 - t) / (t2 - t1) * p1[d] + (t - t1) / (t2 - t1) * p2[d]
                a3 = (t3 - t) / (t3 - t2) * p2[d] + (t - t2) / (t3 - t2) * p3[d]
                b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
                b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
                pt.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
            out.append((pt[0], pt[1]))
    where[len(pts) - 1] = len(out)
    out.append(pts[-1])
    return out, [where[j] for j in keep]


def generate(code, layout, profile, level, rng, dwell=None, keys=None, reps=None, hold_at=()):
    """One simulated sweep for `code`. profile: NoiseProfile (already the base 'mid' profile); level: multiplier k.
    dwell: True / False forces / forbids the pause on repeated letters (None: random with profile.p_dwell).
    Returns [(x, y, t_ms)] in key widths."""
    p = profile.scaled(level)
    if keys is None:
        keys = collapse(code)
    if reps is None:
        reps = repeat_positions(code)
    reps = frozenset(reps) | frozenset(hold_at)
    verts = [layout.centers[k] for k in keys]
    g = rng.gauss
    bias = (g(0, p.sigma_bias), g(0, p.sigma_bias))
    w = []
    for i, (vx, vy) in enumerate(verts):
        sx = p.sigma_wp
        ox, oy = g(0, sx), g(0, sx)
        if i == 0:
            ox += g(0, p.sigma_start)
            oy += g(0, p.sigma_start)
        if i == len(verts) - 1:
            ox += g(0, p.sigma_end)
            oy += g(0, p.sigma_end)
        w.append([vx + bias[0] + ox, vy + bias[1] + oy])
    # corner cutting
    cc = rng.uniform(0, p.corner_cut_max) if p.corner_cut_max > 0 else 0.0
    if cc > 0 and len(w) > 2:
        orig = [list(a) for a in w]
        for i in range(1, len(w) - 1):
            mx = (orig[i - 1][0] + orig[i + 1][0]) / 2.0 - orig[i][0]
            my = (orig[i - 1][1] + orig[i + 1][1]) / 2.0 - orig[i][1]
            dist = math.hypot(mx, my)
            if dist > 1e-9:
                step = min(dist, cc)  # an ABSOLUTE cut of up to cc key widths toward the chord midpoint
                w[i][0] += mx / dist * step
                w[i][1] += my / dist * step
    # overshoot along travel direction
    if p.overshoot_prob > 0 and len(w) > 1:
        orig = [list(a) for a in w]
        for i in range(1, len(w)):
            if rng.random() < p.overshoot_prob:
                dx, dy = orig[i][0] - orig[i - 1][0], orig[i][1] - orig[i - 1][1]
                n = math.hypot(dx, dy)
                if n > 1e-9:
                    a = rng.uniform(0, p.overshoot_amt)
                    w[i][0] += dx / n * a
                    w[i][1] += dy / n * a
    # control points with detours; wp_idx[j] = index of waypoint j in the control list
    ctrl, wp_idx = [], []
    for i in range(len(w)):
        wp_idx.append(len(ctrl))
        ctrl.append((w[i][0], w[i][1]))
        if 0 < i < len(w) - 1 and p.backtrack_prob > 0 and rng.random() < p.backtrack_prob:
            f = rng.uniform(0.7, 1.0)
            ctrl.append((w[i][0] + (w[i - 1][0] - w[i][0]) * f + g(0, p.sigma_wp * 0.5), w[i][1] + (w[i - 1][1] - w[i][1]) * f + g(0, p.sigma_wp * 0.5)))
        if i < len(w) - 1 and p.detour_prob > 0 and rng.random() < p.detour_prob:
            dx, dy = w[i + 1][0] - w[i][0], w[i + 1][1] - w[i][1]
            n = math.hypot(dx, dy)
            if n > 1e-9:
                f = rng.uniform(0.25, 0.75)
                off = g(0, p.detour_amp)
                ctrl.append((w[i][0] + dx * f - dy / n * off, w[i][1] + dy * f + dx / n * off))
    if len(ctrl) == 1:
        ctrl.append((ctrl[0][0] + g(0, p.tremor + 1e-6), ctrl[0][1] + g(0, p.tremor + 1e-6)))
    sm, tracked = _spline(ctrl, p.spline, wp_idx)
    # segment durations between tracked waypoints (Fitts-like), speed factor
    speed = math.exp(g(0, p.speed_sigma)) if p.speed_sigma > 0 else 1.0
    cum = [0.0]
    for i in range(1, len(sm)):
        cum.append(cum[-1] + math.hypot(sm[i][0] - sm[i - 1][0], sm[i][1] - sm[i - 1][1]))
    total_len = cum[-1]
    # per-vertex speed multiplier: slower at the two ends (ramp over 0.6 key widths)
    tv = [0.0]
    seg_of = {}
    bounds = list(tracked)
    bounds[0] = 0
    bounds[-1] = len(sm) - 1
    for i in range(1, len(bounds)):
        bounds[i] = max(bounds[i], bounds[i - 1])
    # walk waypoint to waypoint
    t = 0.0
    vt = [0.0] * len(sm)
    for j in range(len(bounds) - 1):
        a, b = bounds[j], bounds[j + 1]
        if b <= a:
            continue
        seglen = cum[b] - cum[a]
        dur = (p.seg_base_ms + p.seg_slope_ms * math.log2(1.0 + seglen)) / speed
        sp = seglen / dur if dur > 0 else 1.0
        for k in range(a + 1, b + 1):
            d = cum[k] - cum[k - 1]
            mid = (cum[k] + cum[k - 1]) / 2.0
            ramp = min(1.0, 0.5 + 0.5 * min(mid, total_len - mid) / 0.6) if total_len > 0 else 1.0
            t += d / (sp * ramp) if sp > 0 else 0.0
            vt[k] = t
    # holds (ms) keyed by smoothed vertex index
    holds = {}
    lin = p.linger_max_ms
    holds[0] = rng.uniform(0, lin) if lin > 0 else 0.0
    holds[len(sm) - 1] = rng.uniform(0, lin) if lin > 0 else 0.0
    for j in range(len(keys)):
        idx = bounds[j]
        if j in reps:
            if (rng.random() < p.p_dwell) if dwell is None else dwell:
                holds[idx] = holds.get(idx, 0.0) + max(80.0, g(p.dwell_mean_ms, p.dwell_sd_ms))
        elif 0 < j < len(keys) - 1 and p.p_hesitate > 0 and rng.random() < p.p_hesitate:
            holds[idx] = holds.get(idx, 0.0) + max(30.0, g(p.hesitate_mean_ms, p.hesitate_sd_ms))
    # time-position table with holds
    times, poss = [], []
    shift = 0.0
    for k in range(len(sm)):
        times.append(vt[k] + shift)
        poss.append(sm[k])
        h = holds.get(k, 0.0)
        if h > 0:
            shift += h
            times.append(vt[k] + shift)
            poss.append(sm[k])
    # sample
    out = []
    tt = 0.0
    end = times[-1]
    dt_lo, dt_hi = p.dt_min, p.dt_max
    dt = rng.uniform(dt_lo, dt_hi)
    j = 0
    last_raw = None
    while True:
        while j < len(times) - 2 and times[j + 1] < tt:
            j += 1
        t0, t1 = times[j], times[j + 1]
        f = 0.0 if t1 - t0 < 1e-9 else min(1.0, max(0.0, (tt - t0) / (t1 - t0)))
        x = poss[j][0] + (poss[j + 1][0] - poss[j][0]) * f
        y = poss[j][1] + (poss[j + 1][1] - poss[j][1]) * f
        still = last_raw is not None and abs(x - last_raw[0]) < 1e-9 and abs(y - last_raw[1]) < 1e-9
        last_raw = (x, y)
        if not (p.event_driven and still and tt < end):
            if p.tremor > 0 and not (still and p.event_driven):
                x += g(0, p.tremor)
                y += g(0, p.tremor)
            out.append((x, y, tt))
        if tt >= end:
            break
        tt = min(end, tt + dt * rng.uniform(0.8, 1.2))
    return out


def ideal_path(code, layout, rng=None):
    """Noiseless sweep (dwell kept for repeated letters)."""
    return generate(code, layout, PROFILES["finger"], 0.0, rng or random.Random(0))


def generate_word(codes, layout, profile, level, rng, boundary="continuous"):
    """A sweep over a whole word (list of character codes). boundary: 'continuous' (one stroke, nothing marks the boundaries),
    'dwell' (the user pauses on the boundary keys), 'lift' (finger lifts at each boundary; each character is its own stroke with its
    own landing error). Returns (points, lifts) with lifts = indices i where the finger lifted between points[i] and points[i+1]."""
    from sweep.decoder import concat_template
    if boundary == "lift":
        pts, lifts, t0 = [], [], 0.0
        for k, code in enumerate(codes):
            seg = generate(code, layout, profile, level, rng)
            if k > 0:
                gap = max(60.0, rng.gauss(220.0, 70.0))
                t0 += gap
                lifts.append(len(pts) - 1)
            pts.extend((x, y, t + t0) for (x, y, t) in seg)
            t0 = pts[-1][2]
        return pts, lifts
    keys, bounds, reps = concat_template(codes)
    hold = set()
    if boundary == "dwell":
        for a, b in bounds:
            hold.add(a)
    return generate(None, layout, profile, level, rng, keys=keys, reps=reps, hold_at=hold), []


def add_sample_jitter(points, sigma, rng):
    """Add independent Gaussian x/y sensing noise AFTER motor simulation.

    sigma is per axis in normalised key units. Timestamps, sample count and
    lift indices are unchanged; sigma=0 returns an exact copy without RNG use.
    """
    if sigma < 0:
        raise ValueError("jitter sigma must be nonnegative")
    if sigma == 0:
        return list(points)
    return [(x + rng.gauss(0, sigma), y + rng.gauss(0, sigma), t)
            for x, y, t in points]
