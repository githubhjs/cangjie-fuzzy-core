"""Cangjie 3 sweep decoder: a path over a QWERTY keyboard -> ranked characters.

Method (see SPEC.md): SHARK2-style template matching (Kristensson & Zhai, UIST 2004) specialised to a CLOSED lexicon of codes with
1-5 letters. Each code is a template polyline through its key centres (consecutive repeated letters collapsed). Input and template are
resampled to N equidistant points; a shape channel (scale/translation free), a location channel (absolute) and an explicit start/end
term are combined as Gaussian log-likelihoods, plus a log-weight prior. Candidates are pre-filtered by start/end key proximity.
Repeated letters ('hh') are invisible in a path, so they are decided by DWELL: time spent nearly still on a key.

Input is platform neutral: a list of (x, y, t_ms) in KEY-WIDTH units of the Layout, in time order. Output: ranked (char, code, score).
Python 3.8+, standard library only. Written from the published algorithms; no third-party code was consulted or copied.
"""
import math
from dataclasses import dataclass, replace, asdict

from sweep.keyboard import default_layout


@dataclass
class SweepConfig:
    """Defaults = the tuned MOUSE profile (primary desktop). Other profiles: sweep/results/defaults_<profile>.json."""
    n: int = 24                    # resample points per path
    shape_weight: float = 6.807      # log-likelihood weight of mean squared shape distance (key widths^2)
    loc_weight: float = 17.552        # same, location channel
    end_weight: float = 10.655        # same, start/end point distance
    cover_weight: float = 2.806      # weight of mean over template keys of (distance from the key to the nearest path point)^2:
                                   # the path must pass near every intended key, whatever its speed profile (SHARK2 D(t,u) idea)
    loc_tolerance: float = 0.0     # key widths of free slack in the location channel (SHARK2 "tunnel" idea, point-wise)
    end_alpha: float = 1.746         # location point weight at the two ends relative to the middle (>=1)
    shape_short_scale: float = 0.357  # shape weight multiplier for 1-segment templates (2 distinct keys: shape = direction only)
    shape_single_scale: float = 0.0  # ... for 0-segment templates (one key): shape undefined, keep 0
    prior_weight: float = 0.101      # weight of log(weight + prior_floor)
    prior_floor: float = 1.0
    prune_radius: float = 1.2      # key widths: template first/last key must be this close to the path's first/last point
    prune_fallback: bool = True    # if nothing survives, retry with radius x2 then no pruning
    use_index: bool = True         # bucket index by (first key, last key); same results as the scan, just faster
    repeat_mode: str = "dwell"     # "dwell": use dwell evidence for repeated letters; "ignore": rank repeats by prior only
    dwell_ms: float = 250.0        # still for at least this long = one dwell
    dwell_radius: float = 0.35     # "still" = within this many key widths of the dwell anchor
    dwell_assign_radius: float = 0.9  # a dwell counts for the template key nearest to it if within this distance
    repeat_miss_penalty: float = 2.332   # log-score cost: code has a repeated letter at a key but no dwell was seen there
    dwell_extra_penalty: float = 2.165   # log-score cost: dwell seen at a key but code has no repeated letter there
    align_weight: float = 2.49      # key-sequence alignment rerank (spur / backtrack tolerance); 0 = off
    align_gate: float = 2.0        # geometry trust divisor: geometry log-score is scaled by 1 / (1 + align_gate * excess)
    align_ins: float = 0.42        # cost of a key the path touches that the code does not contain (extra touch, spur, backtrack)
    align_miss: float = 1.0        # cost of a code key the path never touches
    hit_radius: float = 0.582        # a key is "touched" when the path passes within this many key widths of its centre
    align_top: int = 40            # only the best `align_top` candidates by score are reranked
    top_k: int = 10

    def to_dict(self):
        return asdict(self)

    def replace(self, **kw):
        return replace(self, **kw)


def collapse(code):
    out = []
    for c in code:
        if not out or out[-1] != c:
            out.append(c)
    return "".join(out)


def repeat_positions(code):
    """Indices (into the collapsed code) of letters that are repeated consecutively in `code`."""
    idx, pos, prev = [], -1, None
    run = 0
    for c in code:
        if c != prev:
            if run > 1:
                idx.append(pos)
            pos += 1
            prev, run = c, 1
        else:
            run += 1
    if run > 1:
        idx.append(pos)
    return frozenset(idx)


def concat_template(codes):
    """Template of a word: the codes of its characters concatenated, consecutive equal letters collapsed.
    Returns (keys, bounds, repeats): keys = collapsed letter string (one vertex per letter); bounds = [(end_vertex_of_char_i,
    start_vertex_of_char_i+1)] for every character boundary; repeats = vertices whose letter is repeated INSIDE one character's code."""
    keys = []
    repeats = set()
    starts, ends = [], []
    for code in codes:
        first = True
        prev_in_code = None
        for ch in code:
            if first:
                if keys and keys[-1] == ch:
                    starts.append(len(keys) - 1)  # same key on both sides of the boundary: one vertex
                else:
                    keys.append(ch)
                    starts.append(len(keys) - 1)
                first = False
            elif ch == prev_in_code:
                repeats.add(len(keys) - 1)
            else:
                keys.append(ch)
            prev_in_code = ch
        ends.append(len(keys) - 1)
    bounds = [(ends[i], starts[i + 1]) for i in range(len(codes) - 1)]
    return "".join(keys), bounds, frozenset(repeats)


def hit_sequence(points, centers, radius, step=0.15):
    """Keys the path touches, in order, consecutive repeats collapsed. The path is walked in steps of at most `step` key widths
    (so fast strokes with sparse samples are not missed); a point touches the nearest key if that key is within `radius`."""
    seq = []
    r2 = radius * radius
    items = list(centers.items())

    def visit(x, y):
        bk, bd = None, r2
        for k, (cx, cy) in items:
            d = (cx - x) ** 2 + (cy - y) ** 2
            if d <= bd:
                bk, bd = k, d
        if bk is not None and (not seq or seq[-1] != bk):
            seq.append(bk)

    visit(points[0][0], points[0][1])
    for i in range(1, len(points)):
        ax, ay, bx, by = points[i - 1][0], points[i - 1][1], points[i][0], points[i][1]
        d = math.hypot(bx - ax, by - ay)
        n = int(d / step)
        for j in range(1, n + 1):
            f = j / (n + 1.0)
            visit(ax + (bx - ax) * f, ay + (by - ay) * f)
        visit(bx, by)
    return seq


def backtrack_count(hits):
    """Revisits: touches of a key the path had already touched and left (y h y: the second y). Evidence that the path doubled back."""
    return len(hits) - len(set(hits))


def align_cost(tkeys, hits, ins, miss):
    """Edit distance between the code's keys and the keys the path touched with NO substitution: a code key must be touched, in order
    (cost 0), else it is missing (cost `miss`); a touched key the code does not need costs `ins` (cheap: spurs and backtracks)."""
    nt, nh = len(tkeys), len(hits)
    INF = 1e9
    prev = [j * ins for j in range(nh + 1)]
    for i in range(1, nt + 1):
        cur = [prev[0] + miss] + [INF] * nh
        tk = tkeys[i - 1]
        for j in range(1, nh + 1):
            best = prev[j] + miss
            v = cur[j - 1] + ins
            if v < best:
                best = v
            if tk == hits[j - 1] and prev[j - 1] < best:
                best = prev[j - 1]
            cur[j] = best
        prev = cur
    return prev[nh]


def resample(pts, n):
    """Resample a polyline (list of (x, y, ...)) to n points equidistant along its length. Zero length -> n copies."""
    m = len(pts)
    if m == 0:
        raise ValueError("empty path")
    if m == 1 or n == 1:
        return [(pts[0][0], pts[0][1])] * n
    cum = [0.0]
    for i in range(1, m):
        cum.append(cum[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = cum[-1]
    if total < 1e-9:
        return [(pts[0][0], pts[0][1])] * n
    out = []
    j = 1
    step = total / (n - 1)
    for i in range(n):
        d = i * step
        while j < m - 1 and cum[j] < d:
            j += 1
        seg = cum[j] - cum[j - 1]
        f = 0.0 if seg < 1e-12 else (d - cum[j - 1]) / seg
        f = 0.0 if f < 0.0 else (1.0 if f > 1.0 else f)
        out.append((pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * f, pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * f))
    return out


def end_alphas(n, end_alpha):
    """Location point weights, sum 1: lowest in the middle, rising linearly to end_alpha x at the two ends."""
    if n == 1:
        return [1.0]
    w = [1.0 + (end_alpha - 1.0) * abs(2.0 * i / (n - 1) - 1.0) for i in range(n)]
    s = sum(w)
    return [v / s for v in w]


def detect_dwells(points, cfg):
    """Dwell events: maximal runs of samples all within dwell_radius of the run's first sample, lasting >= dwell_ms.
    Duration = time of the first sample AFTER the run (or of the last sample if the path ends in the run) minus the run's start, so
    a stream that stops sending while the pointer is still (mouse events) is handled like a timer-driven stream.
    Returns [(x, y, duration_ms)] with (x, y) = mean position of the run."""
    out = []
    m = len(points)
    i = 0
    r2 = cfg.dwell_radius ** 2
    while i < m - 1:
        ax, ay, at = points[i][0], points[i][1], points[i][2]
        j = i + 1
        while j < m and (points[j][0] - ax) ** 2 + (points[j][1] - ay) ** 2 <= r2:
            j += 1
        # event-driven pointers (mouse, touchpad) send NOTHING while still, so the stay lasts until the next sample that left the radius
        dur = (points[j][2] if j < m else points[j - 1][2]) - at
        if dur >= cfg.dwell_ms:
            xs = sum(p[0] for p in points[i:j]) / (j - i)
            ys = sum(p[1] for p in points[i:j]) / (j - i)
            out.append((xs, ys, dur))
            i = j
        else:
            i += 1
    return out


class _Template:
    __slots__ = ("keys", "pts", "cx", "cy", "size", "nseg", "first", "last", "entries", "vkeys")


class Lexicon:
    """Closed lexicon: entries (code, char, weight). Builds collapsed-code templates once; shared by all decodes."""

    def __init__(self, entries, layout=None, n=32):
        self.layout = layout or default_layout()
        self.n = n
        self.entries = [(c, ch, float(w)) for (c, ch, w) in entries]
        groups = {}
        for code, ch, w in self.entries:
            groups.setdefault(collapse(code), []).append((code, ch, w, repeat_positions(code)))
        self.templates = []
        for keys, ents in groups.items():
            t = _Template()
            t.keys = keys
            verts = [self.layout.centers[k] for k in keys]
            t.vkeys = verts
            t.pts = resample(verts, n)
            t.cx = sum(p[0] for p in t.pts) / n
            t.cy = sum(p[1] for p in t.pts) / n
            xs = [p[0] for p in t.pts]
            ys = [p[1] for p in t.pts]
            t.size = max(max(xs) - min(xs), max(ys) - min(ys))
            t.nseg = len(keys) - 1
            t.first, t.last = keys[0], keys[-1]
            t.entries = ents
            self.templates.append(t)
        self.buckets = {}
        for t in self.templates:
            self.buckets.setdefault((t.first, t.last), []).append(t)

    def excess(self, keys, hits, cfg):
        """Unexplained cost of a candidate: alignment cost of the touched keys minus the cost the candidate's own ideal straight sweep would
        have (a perfect sweep also touches keys in between, and that is not a slip). 0 for a clean sweep."""
        cache = self.__dict__.setdefault("_ideal", {})
        key = (keys, cfg.align_ins, cfg.align_miss, cfg.hit_radius)
        ideal = cache.get(key)
        if ideal is None:
            cen = self.layout.centers
            ih = hit_sequence([(cen[k][0], cen[k][1], 0.0) for k in keys], cen, cfg.hit_radius)
            ideal = align_cost(keys, ih, cfg.align_ins, cfg.align_miss)
            cache[key] = ideal
        return max(0.0, align_cost(keys, hits, cfg.align_ins, cfg.align_miss) - ideal)

    @classmethod
    def from_tsv(cls, path, layout=None, n=32, min_len=2):
        ents = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                p = line.rstrip("\n").split("\t")
                if len(p) >= 3 and len(p[0]) >= min_len:
                    ents.append((p[0], p[1], float(p[2])))
        return cls(ents, layout, n)


class SweepDecoder:
    def __init__(self, lexicon, config=None):
        self.lex = lexicon
        self.cfg = config or SweepConfig()
        if self.cfg.n != lexicon.n:  # templates are resampled at build time; rebuild if N differs
            self.lex = Lexicon(lexicon.entries, lexicon.layout, self.cfg.n)

    def _candidates(self, sx, sy, ex, ey, radius):
        lex = self.lex
        if radius is None:
            return lex.templates
        cen = lex.layout.centers
        r2 = radius * radius
        if self.cfg.use_index:
            starts = [k for k, (x, y) in cen.items() if (x - sx) ** 2 + (y - sy) ** 2 <= r2]
            ends = [k for k, (x, y) in cen.items() if (x - ex) ** 2 + (y - ey) ** 2 <= r2]
            out = []
            for a in starts:
                for b in ends:
                    out.extend(lex.buckets.get((a, b), ()))
            return out
        out = []
        for t in lex.templates:
            fx, fy = cen[t.first]
            lx, ly = cen[t.last]
            if (fx - sx) ** 2 + (fy - sy) ** 2 <= r2 and (lx - ex) ** 2 + (ly - ey) ** 2 <= r2:
                out.append(t)
        return out

    def decode(self, points, top_k=None):
        """points: [(x, y, t_ms)] in key widths. Returns [(char, code, score)] best first, one row per character."""
        cfg = self.cfg
        n = cfg.n
        top_k = top_k or cfg.top_k
        if not points:
            return []
        u = resample(points, n)
        ux = [p[0] for p in u]
        uy = [p[1] for p in u]
        sx, sy, ex, ey = ux[0], uy[0], ux[-1], uy[-1]
        ucx, ucy = sum(ux) / n, sum(uy) / n
        uxc = [x - ucx for x in ux]
        uyc = [y - ucy for y in uy]
        usize = max(max(ux) - min(ux), max(uy) - min(uy))
        alphas = end_alphas(n, cfg.end_alpha)
        dwells = detect_dwells(points, cfg) if cfg.repeat_mode == "dwell" and len(points) > 2 else []
        tol = cfg.loc_tolerance
        cands = None
        for radius in (cfg.prune_radius, cfg.prune_radius * 2.0, None):
            cands = self._candidates(sx, sy, ex, ey, radius)
            if cands or not cfg.prune_fallback:
                break
        ws, wl, we = cfg.shape_weight, cfg.loc_weight, cfg.end_weight
        pw, pf = cfg.prior_weight, cfg.prior_floor
        use_dwell = cfg.repeat_mode == "dwell"
        best = {}
        log = math.log
        for t in cands:
            tp = t.pts
            # location channel (absolute)
            xl = 0.0
            if tol > 0.0:
                for i in range(n):
                    d = math.hypot(ux[i] - tp[i][0], uy[i] - tp[i][1]) - tol
                    if d > 0.0:
                        xl += alphas[i] * d * d
            else:
                for i in range(n):
                    dx = ux[i] - tp[i][0]
                    dy = uy[i] - tp[i][1]
                    xl += alphas[i] * (dx * dx + dy * dy)
            # start/end term
            xe = ((ux[0] - tp[0][0]) ** 2 + (uy[0] - tp[0][1]) ** 2 + (ux[-1] - tp[-1][0]) ** 2 + (uy[-1] - tp[-1][1]) ** 2) * 0.5
            # shape channel: translate to centroid, scale the input to the template's size, mean squared distance
            if t.nseg >= 1 and t.size > 1e-9 and usize > 1e-9:
                s = t.size / usize
                tcx, tcy = t.cx, t.cy
                acc = 0.0
                for i in range(n):
                    dx = uxc[i] * s - (tp[i][0] - tcx)
                    dy = uyc[i] * s - (tp[i][1] - tcy)
                    acc += dx * dx + dy * dy
                xs = acc / n
                shape_w = ws * (cfg.shape_short_scale if t.nseg == 1 else 1.0)
            else:
                xs, shape_w = 0.0, ws * cfg.shape_single_scale
            xc = 0.0
            if cfg.cover_weight > 0.0:
                for (vx, vy) in t.vkeys:
                    m = 1e18
                    for i in range(n):
                        d2 = (ux[i] - vx) ** 2 + (uy[i] - vy) ** 2
                        if d2 < m:
                            m = d2
                    xc += m
                xc /= len(t.vkeys)
            gated = -(shape_w * xs + wl * xl + cfg.cover_weight * xc)  # what a backtrack distorts (not the start/end term)
            base = gated - we * xe
            dset = None
            if use_dwell:
                dset = set()
                for (dx_, dy_, _) in dwells:
                    bi, bd = -1, cfg.dwell_assign_radius
                    for vi, (vx, vy) in enumerate(t.vkeys):
                        d = math.hypot(dx_ - vx, dy_ - vy)
                        if d <= bd:
                            bi, bd = vi, d
                    if bi >= 0:
                        dset.add(bi)
            for code, ch, w, rep in t.entries:
                sc = base + pw * log(w + pf)
                if use_dwell:
                    sc -= cfg.repeat_miss_penalty * len(rep - dset) + cfg.dwell_extra_penalty * len(dset - rep)
                cur = best.get(ch)
                if cur is None or sc > cur[0] or (sc == cur[0] and code < cur[1]):
                    best[ch] = (sc, code, gated)
        ranked = sorted(((sc, ch, code, geo) for ch, (sc, code, geo) in best.items()), key=lambda r: (-r[0], r[2], r[1]))
        if cfg.align_weight > 0.0 and ranked:
            hits = hit_sequence(points, self.lex.layout.centers, cfg.hit_radius)
            rev = backtrack_count(hits)  # revisited keys: backtrack / spur evidence
            top = []
            for sc, ch, code, geo in ranked[:cfg.align_top]:
                ex = self.lex.excess(collapse(code), hits, cfg)
                top.append((sc - geo + geo / (1.0 + cfg.align_gate * rev) - cfg.align_weight * ex, ch, code))
            top.sort(key=lambda r: (-r[0], r[2], r[1]))
            ranked = top + [(sc - cfg.align_weight * 1e3, ch, code) for sc, ch, code, geo in ranked[cfg.align_top:]]
        else:
            ranked = [(sc, ch, code) for sc, ch, code, geo in ranked]
        ranked = ranked[:top_k]
        return [(ch, code, sc) for sc, ch, code in ranked]
