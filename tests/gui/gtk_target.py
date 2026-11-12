"""GTK3 target for the ibus-rime test: one focused Gtk.Entry (uses GTK_IM_MODULE=ibus).
Logs every text change (TEXT), every IM preedit change (PREEDIT) and focus events to argv[1].
A file named <log>.clear empties the Entry (driver command)."""
import json
import os
import sys
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import GLib, Gtk, Pango  # noqa: E402

LOG = sys.argv[1]
log = open(LOG, 'a', encoding='utf-8', buffering=1)


def w(kind, val=''):
    log.write('%.3f %s %s\n' % (time.time(), kind, json.dumps(val, ensure_ascii=False)))


win = Gtk.Window(title='GtkTarget')
win.set_default_size(520, 90)
win.move(40, 420)  # below the pad (which sits at the top-left)
entry = Gtk.Entry()
entry.override_font(Pango.FontDescription('Sans 20'))
win.add(entry)
entry.connect('changed', lambda e: w('TEXT', e.get_text()))
entry.connect('preedit-changed', lambda e, s: w('PREEDIT', s))
win.connect('focus-in-event', lambda *a: w('FOCUSIN', 'window') or False)
win.connect('focus-out-event', lambda *a: w('FOCUSOUT', 'window') or False)
win.connect('destroy', Gtk.main_quit)


def poll():
    if os.path.exists(LOG + '.clear'):
        os.remove(LOG + '.clear')
        entry.set_text('')
        w('CLEARED')
    return True


GLib.timeout_add(100, poll)
win.show_all()
w('START', os.environ.get('GTK_IM_MODULE', ''))
GLib.timeout_add(400, lambda: (win.present(), entry.grab_focus(), False)[-1])
Gtk.main()
