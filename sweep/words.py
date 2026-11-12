"""Word-level sweep decoder: ONE stroke (or a few, with lifts) may span a whole word of 1-4 Cangjie characters.

Template of a word = the main codes of its characters concatenated, consecutive equal letters collapsed, as ONE polyline. The boundary
between characters is NOT assumed to be visible in the path: the whole path is matched against the whole template (same channels as the
single-character decoder, SHARK2 style). Boundary evidence is optional: a LIFT (stroke break) or a DWELL near a character boundary of the
candidate raises its score. A word is ranked by path score + log word frequency. The best per-character segmentation (no word lexicon)
is a separate, slower function: `CharSegmenter`.

Input as in decoder.py: points [(x, y, t_ms)] in key widths; `lifts` = indices i where the finger lifted between points[i] and points[i+1].
Python 3.8+, standard library only; written from the published SHARK2 idea, no third-party code.
"""
import math
from array import array
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, asdict, replace

from sweep.decoder import SweepConfig, align_cost, concat_template, detect_dwells, backtrack_count, end_alphas, hit_sequence, resample
from sweep.keyboard import default_layout


@dataclass
class WordConfig:
    """Channel weights start from the tuned single-character (mouse) values; the word-specific ones are tuned in tune_words.py."""
    n: int = 40                    # resample points of the fine comparison
    m: int = 8                     # resample points of the coarse pre-selection
    keep: int = 150                # candidates that survive the coarse pass
    shape_weight: float = 0.0      # shape channel off by default (it did not help in the single-character ablation)
    loc_weight: float = 22.41
    end_weight: float = 22.456
    cover_weight: float = 2.769
    end_alpha: float = 1.93
    evidence_power: float = 0.065    # path-evidence weights are multiplied by ((vertices-1)/evidence_ref) ** evidence_power
    evidence_ref: float = 4.0
    word_prior_weight: float = 0.093  # weight of ln(freq + floor) for words (2-4 chars)
    char_prior_weight: float = 0.1  # weight of ln(weight + floor) for single characters (as in SweepConfig.prior_weight)
    prior_floor: float = 1.0
    char_offset: float = 0.949       # added to every single-character candidate when chars and words compete in one list
    prune_radius: float = 1.2      # first/last key of the template within this of the path's first/last point
    len_lo: float = 0.7            # path length / template length must lie in [len_lo, len_hi]
    len_hi: float = 1.6
    min_candidates: int = 30       # fewer than this after pruning: widen radius x1.6 and the length window, then no pruning
    dwell_ms: float = 250.0
    dwell_radius: float = 0.35
    dwell_assign_radius: float = 0.9
    repeat_miss_penalty: float = 2.332
    dwell_extra_penalty: float = 2.165
    boundary_dwell_ok: bool = True  # a dwell at a character boundary is not "extra"
    boundary_dwell_bonus: float = 0.19  # log-score bonus when a dwell sits on a character boundary
    lift_weight: float = 2.495       # weight of squared distance between lift/landing points and a boundary of the candidate
    lift_extra_penalty: float = 4.0  # per lift beyond the candidate's number of boundaries
    align_weight: float = 2.49      # key-sequence alignment rerank of the best `align_top` candidates; 0 = off
    align_gate: float = 0.2        # words
    align_ins: float = 0.42
    align_miss: float = 1.0
    hit_radius: float = 0.582
    align_top: int = 25
    top_k: int = 10

    def to_dict(self):
        return asdict(self)

    def replace(self, **kw):
        return replace(self, **kw)

    def as_sweep(self):
        return SweepConfig(dwell_ms=self.dwell_ms, dwell_radius=self.dwell_radius, dwell_assign_radius=self.dwell_assign_radius)


def split_strokes(points, lifts):
    out, a = [], 0
    for i in sorted(set(lifts)):
        if 0 <= i < len(points) - 1:
            out.append(points[a:i + 1])
            a = i + 1
    out.append(points[a:])
    return out


def path_length(points):
    return sum(math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]) for i in range(1, len(points)))


def main_codes(char_entries):
    """char -> main code: the shortest code, ties broken by higher weight, then by code (deterministic)."""
    best = {}
    for code, ch, w in char_entries:
        cur = best.get(ch)
        if cur is None or (len(code), -w, code) < (len(cur[0]), -cur[1], cur[0]):
            best[ch] = (code, w)
    return {ch: cw[0] for ch, cw in best.items()}


def _excess(self, keys, hits, cfg):
    cache = self.__dict__.setdefault("_ideal", {})
    key = (keys, cfg.align_ins, cfg.align_miss, cfg.hit_radius)
    ideal = cache.get(key)
    if ideal is None:
        cen = self.layout.centers
        ih = hit_sequence([(cen[k][0], cen[k][1], 0.0) for k in keys], cen, cfg.hit_radius)
        ideal = align_cost(keys, ih, cfg.align_ins, cfg.align_miss)
        cache[key] = ideal
    return max(0.0, align_cost(keys, hits, cfg.align_ins, cfg.align_miss) - ideal)


class _WT:
    __slots__ = ("keys", "vkeys", "coarse", "length", "first", "last", "entries", "maxw", "maxc", "nv")


class WordLexicon:
    """Entries store the RAW prior ln(freq + floor); the weights that scale it live in WordConfig (so they can be tuned without a rebuild).
    chars: [(code, char, weight)] (all codes of every character); words: [(word, freq)].
    Candidates: every word whose characters all have a code (main code), and, if with_chars, every (char, code) as a 1-character entry."""

    def __init__(self, chars, words, layout=None, cfg=None, with_chars=True, min_len=2, max_len=4):
        self.layout = layout or default_layout()
        self.cfg = cfg or WordConfig()
        cfg = self.cfg
        cen = self.layout.centers
        mc = main_codes(chars)
        groups = {}
        nwords = 0
        if with_chars:
            for code, ch, w in chars:
                keys, bounds, reps = concat_template([code])
                groups.setdefault(keys, []).append((ch, "char", math.log(w + cfg.prior_floor), reps, tuple(bounds), 1))
        for word, freq in words:
            if not (min_len <= len(word) <= max_len):
                continue
            try:
                codes = [mc[c] for c in word]
            except KeyError:
                continue
            keys, bounds, reps = concat_template(codes)
            groups.setdefault(keys, []).append((word, "word", math.log(freq + cfg.prior_floor), reps, tuple(bounds), len(word)))
            nwords += 1
        self.n_words = nwords
        self.mc = mc  # char -> main code
        self.templates = []
        self.buckets = {}
        for keys, ents in groups.items():
            t = _WT()
            t.keys = keys
            t.vkeys = [cen[k] for k in keys]
            t.nv = len(keys)
            r = resample(t.vkeys, cfg.m)
            t.coarse = array("d", [v for p in r for v in p])
            t.length = path_length(t.vkeys)
            t.first, t.last = keys[0], keys[-1]
            t.entries = ents
            wr = [e[2] for e in ents if e[1] == "word"]
            cr = [e[2] for e in ents if e[1] == "char"]
            t.maxw = max(wr) if wr else None
            t.maxc = max(cr) if cr else None
            self.templates.append(t)
            self.buckets.setdefault((t.first, t.last), []).append(t)
        for lst in self.buckets.values():
            lst.sort(key=lambda t: t.length)
        self.bucket_len = {k: [t.length for t in v] for k, v in self.buckets.items()}

    excess = _excess


class WordDecoder:
    # Lexicon.excess() is shared: WordLexicon gets the same helper below
    def __init__(self, lexicon, config=None):
        self.lex = lexicon
        self.cfg = config or lexicon.cfg

    def _candidates(self, sx, sy, ex, ey, lp, radius, lo, hi):
        cen = self.lex.layout.centers
        r2 = radius * radius
        starts = [k for k, (x, y) in cen.items() if (x - sx) ** 2 + (y - sy) ** 2 <= r2]
        ends = [k for k, (x, y) in cen.items() if (x - ex) ** 2 + (y - ey) ** 2 <= r2]
        out = []
        for a in starts:
            for b in ends:
                lst = self.lex.buckets.get((a, b))
                if not lst:
                    continue
                lens = self.lex.bucket_len[(a, b)]
                i = bisect_left(lens, lp / hi) if hi else 0
                j = bisect_right(lens, lp / lo) if lo else len(lens)
                out.extend(lst[i:j])
        return out

    def decode(self, points, lifts=(), top_k=None):
        """Returns [(text, kind, score)] best first; kind is 'word' or 'char'."""
        cfg = self.cfg
        top_k = top_k or cfg.top_k
        if not points:
            return []
        n = cfg.n
        uf = resample(points, n)
        uc = resample(points, cfg.m)
        sx, sy, ex, ey = uf[0][0], uf[0][1], uf[-1][0], uf[-1][1]
        lp = path_length(points)
        cands = []
        for radius, lo, hi in ((cfg.prune_radius, cfg.len_lo, cfg.len_hi), (cfg.prune_radius * 1.6, cfg.len_lo * 0.7, cfg.len_hi * 1.4),
                               (cfg.prune_radius * 2.5, 0.0, 0.0)):
            if lp < 1e-6:
                lo, hi = 0.0, 0.0
            cands = self._candidates(sx, sy, ex, ey, lp, radius, lo, hi)
            if len(cands) >= cfg.min_candidates:
                break
        # coarse pass: location on m points + prior
        m = cfg.m
        cx = [p[0] for p in uc]
        cy = [p[1] for p in uc]
        wts = [2.0 if i in (0, m - 1) else 1.0 for i in range(m)]
        sw = sum(wts)
        wts = [w / sw for w in wts]
        scored = []
        wl = cfg.loc_weight
        for t in cands:
            tc = t.coarse
            acc = 0.0
            for i in range(m):
                dx = cx[i] - tc[2 * i]
                dy = cy[i] - tc[2 * i + 1]
                acc += wts[i] * (dx * dx + dy * dy)
            scale = (max(t.nv - 1, 1) / cfg.evidence_ref) ** cfg.evidence_power
            pr = -1e9
            if t.maxw is not None:
                pr = cfg.word_prior_weight * t.maxw
            if t.maxc is not None:
                pr = max(pr, cfg.char_prior_weight * t.maxc + cfg.char_offset)
            scored.append((-(wl * scale) * acc + pr, id(t), t))
        scored.sort(key=lambda r: -r[0])
        keep = [r[2] for r in scored[:cfg.keep]]
        # fine pass
        alphas = end_alphas(n, cfg.end_alpha)
        ux = [p[0] for p in uf]
        uy = [p[1] for p in uf]
        ucx, ucy = sum(ux) / n, sum(uy) / n
        uxc = [x - ucx for x in ux]
        uyc = [y - ucy for y in uy]
        usize = max(max(ux) - min(ux), max(uy) - min(uy))
        strokes = split_strokes(points, lifts)
        dwells = []
        sc = cfg.as_sweep()
        for st in strokes:
            if len(st) > 2:
                dwells.extend(detect_dwells(st, sc))
        hints = [(points[i], points[i + 1]) for i in sorted(set(lifts)) if 0 <= i < len(points) - 1]
        best = {}
        for t in keep:
            tp = resample(t.vkeys, n)
            xl = 0.0
            for i in range(n):
                dx = ux[i] - tp[i][0]
                dy = uy[i] - tp[i][1]
                xl += alphas[i] * (dx * dx + dy * dy)
            xe = ((ux[0] - tp[0][0]) ** 2 + (uy[0] - tp[0][1]) ** 2 + (ux[-1] - tp[-1][0]) ** 2 + (uy[-1] - tp[-1][1]) ** 2) * 0.5
            xs = 0.0
            if cfg.shape_weight > 0 and t.nv >= 2 and usize > 1e-9:
                tcx = sum(p[0] for p in tp) / n
                tcy = sum(p[1] for p in tp) / n
                tsize = max(max(p[0] for p in tp) - min(p[0] for p in tp), max(p[1] for p in tp) - min(p[1] for p in tp))
                if tsize > 1e-9:
                    s = tsize / usize
                    acc = 0.0
                    for i in range(n):
                        dx = uxc[i] * s - (tp[i][0] - tcx)
                        dy = uyc[i] * s - (tp[i][1] - tcy)
                        acc += dx * dx + dy * dy
                    xs = acc / n
            xc = 0.0
            if cfg.cover_weight > 0:
                for (vx, vy) in t.vkeys:
                    mm = 1e18
                    for i in range(n):
                        d2 = (ux[i] - vx) ** 2 + (uy[i] - vy) ** 2
                        if d2 < mm:
                            mm = d2
                    xc += mm
                xc /= t.nv
            scale = (max(t.nv - 1, 1) / cfg.evidence_ref) ** cfg.evidence_power
            gated = -scale * (cfg.loc_weight * xl + cfg.cover_weight * xc + cfg.shape_weight * xs)
            base = gated - scale * cfg.end_weight * xe
            dset = set()
            for (dx_, dy_, _) in dwells:
                bi, bd = -1, cfg.dwell_assign_radius
                for vi, (vx, vy) in enumerate(t.vkeys):
                    d = math.hypot(dx_ - vx, dy_ - vy)
                    if d <= bd:
                        bi, bd = vi, d
                if bi >= 0:
                    dset.add(bi)
            for text, kind, raw, reps, bounds, nch in t.entries:
                s = base + ((cfg.word_prior_weight * raw) if kind == "word" else (cfg.char_prior_weight * raw + cfg.char_offset))
                bset = set()
                for a, b in bounds:
                    bset.add(a)
                    bset.add(b)
                s -= cfg.repeat_miss_penalty * len(reps - dset)
                extra = dset - reps
                if cfg.boundary_dwell_ok:
                    on_b = extra & bset
                    s += cfg.boundary_dwell_bonus * len(on_b)
                    extra = extra - bset
                s -= cfg.dwell_extra_penalty * len(extra)
                if hints:
                    for (p1, p2) in hints:
                        if not bounds:
                            s -= cfg.lift_extra_penalty
                            continue
                        c = min((p1[0] - t.vkeys[a][0]) ** 2 + (p1[1] - t.vkeys[a][1]) ** 2 + (p2[0] - t.vkeys[b][0]) ** 2 + (p2[1] - t.vkeys[b][1]) ** 2
                                for a, b in bounds)
                        s -= cfg.lift_weight * c * 0.5
                    if len(hints) > len(bounds):
                        s -= cfg.lift_extra_penalty * (len(hints) - len(bounds))
                cur = best.get(text)
                if cur is None or s > cur[0]:
                    best[text] = (s, kind, t.keys, gated)
        ranked = sorted(((s, text, kind, keys, geo) for text, (s, kind, keys, geo) in best.items()), key=lambda r: (-r[0], r[1]))
        if cfg.align_weight > 0.0 and ranked:
            hits = hit_sequence(points, self.lex.layout.centers, cfg.hit_radius)
            rev = backtrack_count(hits)  # revisited keys: backtrack / spur evidence
            top = []
            for s, text, kind, keys, geo in ranked[:cfg.align_top]:
                ex = self.lex.excess(keys, hits, cfg)
                top.append((s - geo + geo / (1.0 + cfg.align_gate * rev) - cfg.align_weight * ex, text, kind, keys))
            top.sort(key=lambda r: (-r[0], r[1]))
            ranked = top + [(s - cfg.align_weight * 1e3, text, kind, keys) for s, text, kind, keys, geo in ranked[cfg.align_top:]]
        else:
            ranked = [(s, text, kind, keys) for s, text, kind, keys, geo in ranked]
        return [(text, kind, s) for s, text, kind, keys in ranked[:top_k]]


def corner_candidates(points, count):
    """Indices of the `count` most significant vertices of the path (Douglas-Peucker importance: the largest distance of a point from the
    chord of the span it splits). Turning points are where one character ends and the next begins, so they are the split candidates."""
    m = len(points)
    imp = {}
    stack = [(0, m - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        ax, ay, bx, by = points[i][0], points[i][1], points[j][0], points[j][1]
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy)
        best, bk = -1.0, -1
        for k in range(i + 1, j):
            if n < 1e-9:
                d = math.hypot(points[k][0] - ax, points[k][1] - ay)
            else:
                d = abs(dy * (points[k][0] - ax) - dx * (points[k][1] - ay)) / n
            if d > best:
                best, bk = d, k
        imp[bk] = best
        stack.append((i, bk))
        stack.append((bk, j))
    top = sorted(imp, key=lambda k: -imp[k])[:max(0, count - 2)]
    return sorted(set(top) | {0, m - 1})


class CharSegmenter:
    """Best per-character segmentation, no word lexicon: dynamic programming over split candidates (turning points of the path, plus
    lift points), each segment decoded by the single-character decoder. Slow (tens of single-character decodes, about 0.5 s in Python):
    call it only when the alternative is wanted. A segment never crosses a lift."""

    def __init__(self, decoder, grid=14, seg_penalty=3.0, lift_bonus=3.0, min_chars=2, max_chars=4, min_seg_len=0.8):
        self.dec = decoder
        self.grid = grid
        self.seg_penalty = seg_penalty
        self.lift_bonus = lift_bonus
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.min_seg_len = min_seg_len

    def segment(self, points, lifts=()):
        """Returns (text, score, [(start_idx, end_idx, char, code)]) or None."""
        m = len(points)
        if m < 3:
            return None
        lset = set(i for i in lifts if 0 <= i < m - 1)
        idxs = set(corner_candidates(points, self.grid))
        for i in lset:
            idxs.add(i)
            idxs.add(i + 1)
        idxs = sorted(idxs)
        K = len(idxs)
        cum = [0.0]
        for i in range(1, m):
            cum.append(cum[-1] + math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]))
        seg = {}

        def segscore(a, b):
            key = (a, b)
            if key not in seg:
                lo, hi = idxs[a], idxs[b]
                if any(lo <= i < hi for i in lset) or cum[hi] - cum[lo] < self.min_seg_len or hi - lo < 2:
                    seg[key] = None
                else:
                    r = self.dec.decode(points[lo:hi + 1], top_k=1)
                    seg[key] = (r[0][2], r[0][0], r[0][1]) if r else None
            return seg[key]

        NEG = -1e18
        best = [[(NEG, None)] * K for _ in range(self.max_chars + 1)]
        best[0][0] = (0.0, None)
        for c in range(1, self.max_chars + 1):
            for b in range(1, K):
                for a in range(b):
                    after_lift = a > 0 and idxs[a] - 1 in lset
                    prev = best[c - 1][a - 1 if after_lift else a][0]  # a landing point continues from the point before the lift
                    if prev <= NEG / 2:
                        continue
                    s = segscore(a, b)
                    if s is None:
                        continue
                    tot = prev + s[0] - self.seg_penalty
                    if after_lift:
                        tot += self.lift_bonus
                    if tot > best[c][b][0]:
                        best[c][b] = (tot, (a, s))
        out = None
        for c in range(self.min_chars, self.max_chars + 1):
            if best[c][K - 1][0] > NEG / 2 and (out is None or best[c][K - 1][0] > out[0]):
                out = (best[c][K - 1][0], c)
        if out is None:
            return None
        parts, b, c = [], K - 1, out[1]
        while c > 0:
            _, (a, s) = best[c][b]
            parts.append((idxs[a], idxs[b], s[1], s[2]))
            b, c = (a - 1 if (a > 0 and idxs[a] - 1 in lset) else a), c - 1
        parts.reverse()
        return "".join(p[2] for p in parts), out[0], parts
