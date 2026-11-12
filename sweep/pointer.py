"""Optional batch pointer low-pass in normalised key units; no platform dependencies.

See SPEC section 13 for the estimator, gating and port contract. Filtering never
changes sample count/timestamps or crosses lifts / long event-driven pauses.
"""
import math
from statistics import median

MODES = ("off", "smooth", "length", "window", "smooth_window")


def _spans(points, lifts):
    cuts = {i + 1 for i in lifts if 0 <= i < len(points) - 1}
    cuts.update(i for i in range(1, len(points))
                if points[i][2] - points[i - 1][2] > 32.0)
    bounds = [0] + sorted(cuts) + [len(points)]
    return list(zip(bounds, bounds[1:]))


def estimate_jitter(points, lifts=()):
    """Robust iid per-axis sigma, from time-linear interior residuals.

    A radial Gaussian's median is sigma * sqrt(2 ln 2). Normalise each
    residual for its three noise coefficients before taking the median.
    Corners are outliers; constant-speed lines have zero residual.
    """
    residuals = []
    for a, b in _spans(points, lifts):
        for i in range(a + 1, b - 1):
            p, q, r = points[i - 1:i + 2]
            dt = r[2] - p[2]
            if dt <= 0 or q[2] <= p[2] or q[2] >= r[2]:
                continue
            f = (q[2] - p[2]) / dt
            dx = q[0] - (p[0] + f * (r[0] - p[0]))
            dy = q[1] - (p[1] + f * (r[1] - p[1]))
            residuals.append(math.hypot(dx, dy) / math.sqrt(1 + f * f + (1 - f) ** 2))
    return median(residuals) / math.sqrt(2 * math.log(2)) if len(residuals) >= 5 else 0.0


def prepare_pointer(points, cfg, lifts=()):
    """Return (scoring points, length points, estimated sigma).

    `pointer_filter`: off, smooth, length, window, smooth_window. An inactive
    filter returns the original sequence (including its exact coordinates).
    The local linear fit uses real timestamps, including at the endpoints;
    unlike a causal average it introduces no fixed lag at gesture completion.
    """
    mode = cfg.pointer_filter
    if mode not in MODES:
        raise ValueError("unknown pointer_filter: %s" % mode)
    if mode == "off" or len(points) < 7:
        return points, points, 0.0
    sigma = estimate_jitter(points, lifts)
    if sigma <= cfg.pointer_jitter_floor:
        return points, points, sigma
    radius = min(6, max(2, int(math.ceil(sigma / 0.05))))
    smoothed = list(points)
    for a, b in _spans(points, lifts):
        if b - a < 7:
            continue
        for i in range(a, b):
            lo, hi = max(a, i - radius), min(b, i + radius + 1)
            count = hi - lo
            st = sx = sy = stt = stx = sty = 0.0
            origin = points[i][2]
            for j in range(lo, hi):
                x, y, stamp = points[j]
                t = stamp - origin
                st += t
                sx += x
                sy += y
                stt += t * t
                stx += t * x
                sty += t * y
            den = count * stt - st * st
            if den > 1e-12:
                x = (sx * stt - st * stx) / den
                y = (sy * stt - st * sty) / den
            else:
                x, y = sx / count, sy / count
            smoothed[i] = (x, y, origin)
    scoring = smoothed if mode in ("smooth", "smooth_window") else points
    return scoring, smoothed, sigma
