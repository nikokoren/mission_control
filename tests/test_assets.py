#!/usr/bin/env python3
"""
Checks on the rocket drawings and the keys that reach them.

    python3 tests/test_assets.py

Separate from test_cards.py because this is about files on disk rather than
prose, and it fails for different reasons.

What prompted it: cz_8a_idle.png and cz_8a_ascent.png were committed and then
never shown. get_rocket_image_url maps "Long March 8A" by substring, and
"long march 8" already matched it, so the 8A kept the plain 8's key and the new
drawings sat in the repo unreachable. Nothing announced that -- the plugin just
went on rendering the generic rocket, because the way this resolver signals "no
drawing" is to emit a URL that 404s and let the page fall through to the
fallbacks. A drawing nobody can reach fails exactly as quietly as no drawing.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import update_launch as U  # noqa: E402

ART = os.path.join(ROOT, "rockets")
SUFFIXES = ("_idle", "_ascent", "_landed")

# Art in rockets/ that no image key reaches, and that is not a bug.
UNREACHABLE_BY_DESIGN = {
    # Station drawings for the ISS board, which scripts/iss-events.mjs picks
    # by name. Nothing to do with the launch resolver.
    "iss", "iss_eva",
    # The placeholder an empty pad and an unmatched rocket fall back to.
    "empty", "generic_idle", "generic_ascent",
}


def resolver_keys():
    """
    Every key get_rocket_image_url can assign.

    Scraped from the source rather than enumerated by hand, so a key added to
    the chain is covered without anyone remembering to list it here. The Vulcan
    keys are built from a regex match instead of a literal, so they are spelled
    out; the parametrised shape is the reason this cannot be a plain grep alone.

    Deliberately does NOT include BASE_KEY's own keys and values. Folding those
    in was the first version of this function, and it made the fallback checks
    below unable to fail: a typo in BASE_KEY entered the set of known keys by
    virtue of being in BASE_KEY, and then validated itself.
    """
    with open(os.path.join(ROOT, "scripts", "update_launch.py")) as f:
        source = f.read()
    keys = set(re.findall(r'key = "([a-z0-9_]+)"', source))
    keys |= {f"vulcan_vc{n}{size}" for n in "0246" for size in "sl"}
    return keys - {"empty", "generic"}


def art_files():
    return {f.rsplit(".", 1)[0] for f in os.listdir(ART) if "." in f}


def main():
    keys, art = resolver_keys(), art_files()
    failures = []

    # 1. Every drawing is reachable. The check that matters: a key with no
    #    drawing degrades to the generic rocket on purpose and there are
    #    dozens of those, so the useful direction is the other one.
    for name in sorted(art):
        if name in UNREACHABLE_BY_DESIGN:
            continue
        stem = name
        for suffix in SUFFIXES:
            if name.endswith(suffix):
                stem = name[:-len(suffix)]
                break
        if stem not in keys:
            failures.append(f"rockets/{name}.png is unreachable: no image key "
                            f"resolves to {stem!r}")

    # 2. No fallback loops. BASE_KEY is followed one step today, so a pair
    #    pointing at each other merely looks wrong; it would hang the day
    #    anyone makes the lookup walk the chain.
    for key, base in U.BASE_KEY.items():
        if base == key:
            failures.append(f"BASE_KEY[{key!r}] points at itself")
        elif U.BASE_KEY.get(base) == key:
            failures.append(f"BASE_KEY[{key!r}] and BASE_KEY[{base!r}] point at each other")

    # 3. Both ends of every fallback have to be keys the resolver can
    #    actually assign. A typo is otherwise silent in both directions: an
    #    unknown target means the alt URL is never emitted, and an unknown
    #    source means the entry is dead config nothing will ever look up.
    for key, base in U.BASE_KEY.items():
        if key not in keys:
            failures.append(f"BASE_KEY has an entry for {key!r}, which is not a "
                            f"key the resolver ever assigns")
        if base not in keys:
            failures.append(f"BASE_KEY[{key!r}] falls back to {base!r}, "
                            f"which is not a key the resolver ever assigns")

    # 4. Where a drawing exists, the resolver has to actually return it.
    #    Closing the loop through the real function, not just the tables.
    for rocket, expected in (("Long March 8A", "cz_8a_idle"),
                             ("Long March 8", "cz_8_idle"),
                             ("Falcon 9", "falcon9_idle"),
                             ("Long March 5", "cz_5_idle")):
        url, _ = U.get_rocket_image_url(rocket, "Go", None, "", "", "REPO")
        if f"/{expected}." not in url:
            failures.append(f"{rocket!r} resolves to {url!r}, expected {expected}")

    # 5. An idle drawing without its ascent counterpart means the rocket
    #    vanishes the moment it lifts off. Warned, not failed: it is a gap in
    #    the art rather than a broken mapping, and the page falls back.
    missing_ascent = sorted(
        name[:-len("_idle")] for name in art
        if name.endswith("_idle") and name[:-len("_idle")] + "_ascent" not in art
        and name not in UNREACHABLE_BY_DESIGN)

    print(f"{len(art)} drawings, {len(keys)} resolver keys")
    if missing_ascent:
        print(f"  note: idle art with no ascent variant: {', '.join(missing_ascent)}")
    drawn = sorted(k for k in keys if f"{k}_idle" in art)
    print(f"  note: {len(drawn)} of {len(keys)} keys have their own drawing; "
          f"the rest fall back by design")

    if failures:
        print(f"  FAIL {len(failures)} problem(s)")
        for item in failures:
            print(f"    - {item}")
        return 1
    print("  ok   every drawing is reachable and every fallback resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
