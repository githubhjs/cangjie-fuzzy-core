"""Pad word decoding, JSON template cache, and background loading (stdlib only)."""
from array import array
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading

from sweep.auto import AutoDecoder, char_config
from sweep.decoder import Lexicon, SweepDecoder
from sweep.keyboard import default_layout
from sweep.words import WordConfig, WordDecoder, WordLexicon, main_codes, _WT


def cache_dir():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Caches'
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache')))
    return base / 'cangjie-sweep-pad'


def word_config(args):
    # No independently tuned word profiles exist. All device choices use the
    # published joint mouse/finger word defaults, rather than character weights.
    root = Path(__file__).resolve().parent
    package = root if (root / 'sweep').is_dir() else root.parent
    cfg = WordConfig(**json.loads((package / 'sweep/results/defaults_words.json').read_text()))
    return cfg.replace(top_k=args.top_k, loc_weight=cfg.loc_weight * args.strictness,
                       end_weight=cfg.end_weight * args.strictness,
                       cover_weight=cfg.cover_weight * args.strictness)


def char_decoder(args, entries):
    """Single-character decoder of the device profile (SPEC section 12); strictness scales the same weights as for words."""
    cfg = char_config(args.profile)
    cfg = cfg.replace(loc_weight=cfg.loc_weight * args.strictness, end_weight=cfg.end_weight * args.strictness,
                      cover_weight=cfg.cover_weight * args.strictness)
    return SweepDecoder(Lexicon([e for e in entries if len(e[0]) >= 2], default_layout(), cfg.n), cfg)


class PadDecoder:
    """decode() = decode_auto: the single-character decoder and the one-list word decoder, combined by the SPEC section 12 policy."""
    def __init__(self, lexicon, codes, cfg, chars=None):
        self.lex = lexicon
        self.codes = codes
        self.decoder = WordDecoder(lexicon, cfg)
        self.auto = AutoDecoder(chars, self.decoder, cfg.top_k)

    def decode(self, points, lifts=(), top_k=None):
        return [(text, ''.join(self.codes[c] for c in text), score)
                for text, kind, score, code in self.auto.decode(points, lifts, top_k)]

    def injection_code(self, text, separator=''):
        return separator.join(self.codes[c] for c in text)


def _cache_key(args, cfg):
    h = hashlib.sha256(b'pad-word-templates-v1;min_freq=100;length=2..4')
    for path in (args.table, args.essay, Path(__file__), Path(sys.modules['sweep.words'].__file__),
                 Path(sys.modules['sweep.decoder'].__file__), Path(sys.modules['sweep.keyboard'].__file__)):
        h.update(Path(path).read_bytes())
    h.update(json.dumps(cfg.to_dict(), sort_keys=True).encode())
    h.update(json.dumps(default_layout().centers, sort_keys=True).encode())
    return h.hexdigest()


def _dump(lex, codes):
    templates = []
    for t in lex.templates:
        entries = [[text, kind, raw, sorted(reps), bounds, nch]
                   for text, kind, raw, reps, bounds, nch in t.entries]
        templates.append([t.keys, list(t.coarse), t.length, entries, t.maxw, t.maxc])
    return dict(version=1, codes=codes, n_words=lex.n_words, templates=templates)


def _restore(data, cfg):
    if data['version'] != 1:
        raise ValueError('cache version')
    lex = WordLexicon.__new__(WordLexicon)
    lex.layout, lex.cfg = default_layout(), cfg
    lex.n_words = data['n_words']
    lex.templates, lex.buckets = [], {}
    for keys, coarse, length, entries, maxw, maxc in data['templates']:
        t = _WT()
        t.keys, t.length, t.maxw, t.maxc = keys, length, maxw, maxc
        t.vkeys = [lex.layout.centers[k] for k in keys]
        t.coarse, t.nv = array('d', coarse), len(keys)
        if len(coarse) != cfg.m * 2 or not keys:
            raise ValueError('cache template')
        t.first, t.last = keys[0], keys[-1]
        t.entries = [(text, kind, raw, frozenset(reps), tuple(tuple(b) for b in bounds), nch)
                     for text, kind, raw, reps, bounds, nch in entries]
        lex.templates.append(t)
        lex.buckets.setdefault((t.first, t.last), []).append(t)
    for bucket in lex.buckets.values():
        bucket.sort(key=lambda t: t.length)
    lex.bucket_len = {k: [t.length for t in v] for k, v in lex.buckets.items()}
    return lex, data['codes']


def make_decoder(args, directory=None):
    cfg = word_config(args)
    directory = Path(directory) if directory is not None else cache_dir()
    target = directory / (_cache_key(args, cfg) + '.json')
    chars = Lexicon.from_tsv(str(args.table), min_len=1).entries
    try:
        lex, codes = _restore(json.loads(target.read_text(encoding='utf-8')), cfg)
        return PadDecoder(lex, codes, cfg, char_decoder(args, chars))
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    codes = main_codes(chars)
    words = []
    with Path(args.essay).open(encoding='utf-8') as source:
        for line in source:
            p = line.rstrip('\n').split('\t')
            if len(p) == 2 and p[1].isdigit() and int(p[1]) >= 100 and 2 <= len(p[0]) <= 4:
                words.append((p[0], int(p[1])))
    lex = WordLexicon(chars, words, cfg=cfg)
    # A read-only/unavailable cache must not prevent decoding. Atomic replacement
    # also permits multiple pad processes to build the same key concurrently.
    temporary = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=str(directory),
                                         suffix='.json', delete=False) as output:
            temporary = Path(output.name)
            json.dump(_dump(lex, codes), output, ensure_ascii=False, separators=(',', ':'))
        os.replace(str(temporary), str(target))
    except OSError:
        pass
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return PadDecoder(lex, codes, cfg, char_decoder(args, chars))


class DecoderLoader:
    """Worker never touches Tk; UI consumes exactly one result on its own thread."""
    def __init__(self, args, factory=make_decoder):
        self.messages = queue.Queue()
        self.thread = threading.Thread(target=self._run, args=(args, factory), daemon=True)
        self.thread.start()

    def _run(self, args, factory):
        try:
            self.messages.put((factory(args), None))
        except Exception as error:
            self.messages.put((None, str(error)))

    def poll(self):
        try:
            return self.messages.get_nowait()
        except queue.Empty:
            return None
