"""Turn a raw Whisper transcript into clean, insertable text.

Order: spoken commands -> filler strip -> dictionary correction -> domain "dot" join ->
whitespace/punctuation repair -> capitalization.
"""

import difflib
import re

# spoken command -> replacement (matched case-insensitively, tolerating attached punctuation)
_COMMANDS = [
    (r"new\s+paragraph", "\n\n"),
    (r"new\s+line", "\n"),
    (r"full\s+stop", "."),
    (r"period", "."),
    (r"comma", ","),
    (r"question\s+mark", "?"),
    (r"exclamation\s+(?:mark|point)", "!"),
    (r"semicolon", ";"),
    (r"colon", ":"),
    (r"open\s+quote", "“"),
    (r"close\s+quote", "”"),
]
_COMMAND_RES = [
    # allow Whisper's own punctuation glued around the spoken command
    (re.compile(rf"[,.!?;:]?\s*\b{pat}\b[,.!?;:]?", re.IGNORECASE), rep)
    for pat, rep in _COMMANDS
]

_FILLER_RE = re.compile(r"\b(?:um+|uh+|erm+|uhm+|mm+|hmm+)\b[,.]?\s*", re.IGNORECASE)

_TLDS = ("com", "net", "org", "io", "dev", "ai", "in", "co", "edu", "gov", "me", "app")
_DOT_RE = re.compile(
    rf"(\w)\s+dot\s+({'|'.join(_TLDS)})\b", re.IGNORECASE
)
_AT_RE = re.compile(rf"(\w)\s+at\s+((?:\w+\.)+(?:{'|'.join(_TLDS)}))\b", re.IGNORECASE)
# tokens that whitespace/capitalization repair must never touch
_PROTECT_RE = re.compile(
    rf"(?:\S+@\S+\.\S+|https?://\S+|www\.\S+|\w+(?:\.\w+)*\.(?:{'|'.join(_TLDS)})\b(?:/\S*)?)",
    re.IGNORECASE)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")


def _apply_dictionary(text: str, entries: list[str]) -> str:
    """Replace words that fuzzy-match a dictionary entry with the entry's exact form."""
    if not entries:
        return text
    by_lower = {e.lower(): e for e in entries}

    def fix(m: re.Match) -> str:
        w = m.group(0)
        lw = w.lower()
        if lw in by_lower:
            return by_lower[lw]  # exact word, canonical casing
        for el, entry in by_lower.items():
            if len(lw) < 4 or abs(len(lw) - len(el)) > 3:
                continue
            ratio = difflib.SequenceMatcher(None, lw, el).ratio()
            # names get mangled hard ("Siryanch" for "Suryansh") — allow looser
            # matches when the first letter agrees and both words are long
            if ratio >= 0.8 or (ratio >= 0.7 and lw[0] == el[0] and len(lw) >= 6):
                return entry
        return w

    return _WORD_RE.sub(fix, text)


def _repair(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.!?;:])", r"\1", text)          # no space before punctuation
    text = re.sub(r"([,.!?;:])(?=[A-Za-z])", r"\1 ", text)  # one space after
    text = re.sub(r"([,.!?;:]){2,}", r"\1", text)         # collapse doubled punctuation
    text = re.sub(r" *\n *", "\n", text)                  # trim around newlines
    return text.strip()


def _capitalize(text: str) -> str:
    out = []
    cap = True
    for ch in text:
        if cap and ch.isalpha():
            out.append(ch.upper())
            cap = False
        else:
            out.append(ch)
            if ch in ".!?\n":
                cap = True
            elif ch.isalpha() or ch.isdigit():
                cap = False
    return "".join(out)


def clean(raw: str, strip_fillers: bool = True, dictionary: list[str] | None = None) -> str:
    text = raw.strip()
    for rx, rep in _COMMAND_RES:
        text = rx.sub(rep, text)
    if strip_fillers:
        text = _FILLER_RE.sub("", text)
    text = _apply_dictionary(text, dictionary or [])
    text = _DOT_RE.sub(r"\1.\2", text)   # "gmail dot com" -> "gmail.com"
    text = _AT_RE.sub(r"\1@\2", text)    # "suryansh at gmail.com" -> "suryansh@gmail.com"
    # shield emails/URLs from spacing & capitalization repair
    protected = []
    def stash(m):
        protected.append(m.group(0))
        return f"\x00{len(protected)-1}\x00"
    text = _PROTECT_RE.sub(stash, text)
    text = _repair(text)
    text = _capitalize(text)
    for i, tok in enumerate(protected):
        text = text.replace(f"\x00{i}\x00", tok)
    return text


def word_count(text: str) -> int:
    return len(text.split())
