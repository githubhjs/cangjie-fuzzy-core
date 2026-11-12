"""Target app for GUI tests: one focused Entry; every change is logged to argv[1]."""
import sys
import time
import tkinter as tk

log = open(sys.argv[1], 'a', encoding='utf-8', buffering=1)
root = tk.Tk()
root.title('TargetApp')
root.geometry(sys.argv[2] if len(sys.argv) > 2 else '420x80+40+40')
var = tk.StringVar()
entry = tk.Entry(root, textvariable=var, font=('TkFixedFont', 16))
entry.pack(fill='x', padx=8, pady=8)


def changed(*_):
    import json
    log.write('%.3f TEXT %s\n' % (time.time(), json.dumps(var.get())))


var.trace_add('write', changed)
root.bind_all('<FocusIn>', lambda e: log.write('%.3f FOCUSIN %s\n' % (time.time(), e.widget)))
root.bind_all('<FocusOut>', lambda e: log.write('%.3f FOCUSOUT %s\n' % (time.time(), e.widget)))
# Clear command for the driver: a file named <log>.clear empties the Entry.
import os


def poll():
    flag = sys.argv[1] + '.clear'
    if os.path.exists(flag):
        os.remove(flag)
        var.set('')
        log.write('%.3f CLEARED\n' % time.time())
    root.after(100, poll)


root.after(300, lambda: (root.focus_force(), entry.focus_set()))
root.after(100, poll)
root.mainloop()
