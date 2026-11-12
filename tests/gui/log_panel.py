"""Minimal IBus panel that logs what the IME shows (preedit, auxiliary text, lookup table) to argv[1].

Run it as the panel of a private ibus-daemon so a GUI test can read the real Rime candidate list:
  ibus-daemon --daemonize --address=unix:path=$T/ibus.sock --config=disable \
      --panel="python3 tests/gui/log_panel.py $T/panel.log"
Each line: '<time> <KIND> <json>'; KIND is TABLE (list of candidate strings, cursor), PREEDIT, AUX, HIDE.
"""
import json
import sys
import time

import gi
gi.require_version('IBus', '1.0')
from gi.repository import GLib, IBus  # noqa: E402

log = open(sys.argv[1], 'a', encoding='utf-8', buffering=1)


def w(kind, val):
    log.write('%.3f %s %s\n' % (time.time(), kind, json.dumps(val, ensure_ascii=False)))


class LogPanel(IBus.PanelService):
    def do_update_lookup_table(self, table, visible):
        n = table.get_number_of_candidates()
        w('TABLE', {'visible': bool(visible), 'cursor': table.get_cursor_pos(),
                    'page_size': table.get_page_size(),
                    'candidates': [table.get_candidate(i).get_text() for i in range(n)]})

    def do_hide_lookup_table(self):
        w('HIDE', 'table')

    def do_update_preedit_text(self, text, cursor, visible):
        w('PREEDIT', {'text': text.get_text(), 'visible': bool(visible)})

    def do_update_auxiliary_text(self, text, visible):
        w('AUX', {'text': text.get_text(), 'visible': bool(visible)})

    def do_focus_in(self, path):
        w('FOCUS_IN', path)

    def do_focus_out(self, path):
        w('FOCUS_OUT', path)


IBus.init()
bus = IBus.Bus()
if not bus.is_connected():
    sys.exit('log_panel: cannot connect to ibus (IBUS_ADDRESS?)')
panel = LogPanel(connection=bus.get_connection(), object_path=IBus.PATH_PANEL)
bus.request_name(IBus.SERVICE_PANEL, 0)
w('START', IBus.get_address())
bus.connect('disconnected', lambda *a: loop.quit())
loop = GLib.MainLoop()
loop.run()
