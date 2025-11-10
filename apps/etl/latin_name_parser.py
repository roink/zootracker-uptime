from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

_LNUMBER_RE = re.compile(r"\bL\s*-?\s*(\d{1,3})\b", re.I)
# Regex used only to quickly check whether parentheses exist.
_SEGMENT_HINT_RE = re.compile(r"\(")


@dataclass
class ParsedLatinName:
    normalized: Optional[str]
    alternative_names: List[str]
    qualifier: Optional[str]
    qualifier_target: Optional[str]
    locality: Optional[str]
    trade_code: Optional[str]


def _top_level_segments(text: str) -> List[str]:
    """Extract top-level ``(...)`` segments from ``text`` supporting nesting."""

    segs: List[str] = []
    depth = 0
    buf: List[str] = []
    for ch in text:
        if ch == "(":
            if depth == 0:
                buf = []
            else:
                buf.append(ch)
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                segs.append("".join(buf))
            else:
                buf.append(ch)
        elif depth > 0:
            buf.append(ch)
    return segs


def _canonicalize_name(
    name: str,
    genus_context: Optional[str],
    species_context: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Return canonical form of ``name`` and updated contexts."""

    if not name:
        return None, genus_context, species_context, None, None

    name = name.replace("spec.", "sp.").strip()
    name = re.sub(r'"[^\"]+"', "", name)
    tokens = name.split()
    if not tokens:
        return None, genus_context, species_context, None, None

    genus = tokens[0]
    if genus.endswith(".") and len(genus) == 2 and genus_context and genus_context.startswith(genus[0]):
        genus = genus_context
    else:
        genus_context = genus

    qualifier = None
    qualifier_target = None
    species = None
    subspecies: List[str] = []
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t in {"cf.", "aff."}:
            if i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                if species is None:
                    species = next_tok
                elif species == "sp.":
                    pass
                species_context = next_tok
                qualifier = t[:-1]
                qualifier_target = next_tok
                i += 2
                continue
            i += 1
            continue
        elif t == "sp.":
            if species is None:
                species = "sp."
            i += 1
            continue
        elif t.endswith(".") and len(t) == 2 and species_context and species_context.startswith(t[0]):
            if species is None:
                species = species_context
            i += 1
            continue
        else:
            if species is None:
                species = t
                species_context = species
            else:
                subspecies.append(t)
        i += 1

    parts = [p for p in [genus, species, *subspecies] if p]
    return (
        " ".join(parts).strip(),
        genus_context,
        species_context,
        qualifier,
        qualifier_target,
    )


def parse_latin_name(name: Optional[str]) -> ParsedLatinName:
    """Parse a Latin name string and extract structured information."""

    if not name:
        return ParsedLatinName(None, [], None, None, None, None)

    locality = None
    trade_code = None
    qualifier = None
    qualifier_target = None
    alternative: List[str] = []

    segments = _top_level_segments(name) if _SEGMENT_HINT_RE.search(name) else []
    core = name
    for seg in segments:
        core = core.replace(f"({seg})", " ")

    quotes = re.findall(r'"([^\"]+)"', core)
    if quotes:
        locality = quotes[0]
    core = re.sub(r'"[^\"]+"', '', core).strip()

    m = _LNUMBER_RE.search(core)
    if m:
        trade_code = f"L{m.group(1)}"
        core = _LNUMBER_RE.sub('', core).strip()

    for raw_seg in segments:
        content = raw_seg.strip()
        if re.fullmatch(r"(cf|aff)\.", content):
            qualifier = content[:-1]
            continue
        m = re.match(r"(?i)(syn\.|misid\.|inkl\.|incl\.)\s*:?\s*(.+)", content)
        if m:
            alternative.append(m.group(2).strip())
            continue
        m = _LNUMBER_RE.search(content)
        if m:
            if not trade_code:
                trade_code = f"L{m.group(1)}"
            rest = _LNUMBER_RE.sub('', content).strip()
            if rest:
                if re.search(r"\b(Rio|River|Lago|Lake|See)\b", rest, re.I):
                    locality = locality or rest
                else:
                    alternative.append(rest)
            continue
        if content:
            alternative.append(content)

    normalized, genus_ctx, species_ctx, qual, qual_target = _canonicalize_name(core, None, None)
    alt_results: List[str] = []
    for alt in alternative:
        canon, genus_ctx, species_ctx, _, _ = _canonicalize_name(alt, genus_ctx, species_ctx)
        if canon and canon not in alt_results:
            alt_results.append(canon)

    if qualifier and not qualifier_target and species_ctx and species_ctx != "sp.":
        qualifier_target = species_ctx
    if qual and not qualifier:
        qualifier = qual
        qualifier_target = qualifier_target or qual_target

    return ParsedLatinName(normalized, alt_results, qualifier, qualifier_target, locality, trade_code)
