"""textproc unit checks."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sotto.textproc import clean

cases = [
    # spoken commands
    ("So the first point new line the second point", None,
     lambda t: "\n" in t and "new line" not in t.lower()),
    ("Here we go new paragraph And then more", None, lambda t: "\n\n" in t),
    ("Is this working question mark", None, lambda t: t.endswith("?")),
    ("Wait comma what exclamation mark", None, lambda t: "," in t and t.endswith("!")),
    # fillers
    ("Um, I think, uh, this works", None, lambda t: "um" not in t.lower() and "uh" not in t.lower()),
    # dictionary fuzzy fix
    ("Suryongsh wrote this", ["Suryansh"], lambda t: t.startswith("Suryansh")),
    ("Siryanch wrote this", ["Suryansh"], lambda t: t.startswith("Suryansh")),
    # domain dot + spoken "at"
    ("Email me at suryansh at gmail dot com", None, lambda t: "suryansh@gmail.com" in t),
    ("Check github.com for updates", None, lambda t: "github.com" in t),
    # capitalization repair
    ("first. second sentence", None, lambda t: "First. Second sentence" in t),
    # spacing repair
    ("Hello ,world .", None, lambda t: "Hello, world." in t),
]

fails = 0
for raw, d, check in cases:
    out = clean(raw, strip_fillers=True, dictionary=d or [])
    status = "ok " if check(out) else "FAIL"
    if status == "FAIL":
        fails += 1
    print(f"[{status}] {raw!r} -> {out!r}")

print(f"\n{len(cases)-fails}/{len(cases)} passed")
sys.exit(1 if fails else 0)
