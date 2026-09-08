"""Shared PokeAPI helpers: map a drafted Pokemon to its Base Speed and to a
sprite image, with on-disk caches so each species is fetched at most once. All
network calls are synchronous (requests) and are run off the event loop by the
async wrappers here via run_in_executor.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import unicodedata

import requests

SPEED_CACHE_FILE = "files/speeds.json"
SPRITE_DIR = "files/sprites"
SLUGS_CACHE_FILE = "files/pokeapi_slugs.json"  # every valid PokeAPI slug

# Optional preferred sprite host: a URL template containing "{slug}". When set,
# it is tried before falling back to PokeAPI's front_default sprite. Left as None
# by default (the centropkmn gen9-sprites path returns 404 to direct requests).
SPRITE_URL_TEMPLATE = None

try:
    with open(SPEED_CACHE_FILE) as _f:
        _speed_cache = json.load(_f)
except (FileNotFoundError, json.JSONDecodeError):
    _speed_cache = {}


class SpeedLookupError(Exception):
    """Raised when PokeAPI has no usable entry for a species."""


# Draft names abbreviate formes with short codes (Diglett-A, Deoxys-D, Ogerpon-H,
# ...). A code can mean different things per species (-A is Alola for Diglett but
# Attack for Deoxys), so each maps to a list of candidate forme names and the
# resolver keeps the first that is an actual PokeAPI slug.
_CODE_EXPANSIONS = {
    "a": ["alola", "attack"], "b": ["bloodmoon"], "c": ["crowned", "cornerstone-mask"],
    "d": ["defense"], "e": ["eternal"], "g": ["galar", "galar-standard"],
    "h": ["hisui", "hearthflame-mask"], "i": ["incarnate"], "m": ["male"], "n": ["normal"],
    "p": ["paldea-combat-breed", "paldea", "pom-pom", "pirouette"], "r": ["rapid-strike"],
    "s": ["single-strike", "speed", "sensu"], "t": ["therian"], "u": ["unbound"],
    "w": ["wellspring-mask", "wash"], "aqua": ["paldea-aqua-breed"], "blaze": ["paldea-blaze-breed"],
    "day": ["midday"], "night": ["midnight"],
}
# Bare names whose default battle forme has a suffixed PokeAPI slug.
_DEFAULT_FORME = {
    "aegislash": "aegislash-shield", "basculin": "basculin-red-striped",
    "darmanitan": "darmanitan-standard", "dudunsparce": "dudunsparce-two-segment",
    "eiscue": "eiscue-ice", "frillish": "frillish-male", "gourgeist": "gourgeist-average",
    "jellicent": "jellicent-male", "maushold": "maushold-family-of-four",
    "meloetta": "meloetta-aria", "meowstic": "meowstic-male", "mimikyu": "mimikyu-disguised",
    "minior": "minior-red-meteor", "morpeko": "morpeko-full-belly", "oinkologne": "oinkologne-male",
    "pumpkaboo": "pumpkaboo-average", "pyroar": "pyroar-male", "shaymin": "shaymin-land",
    "squawkabilly": "squawkabilly-green-plumage", "tatsugiri": "tatsugiri-curly",
    "toxtricity": "toxtricity-amped", "wishiwashi": "wishiwashi-solo", "wormadam": "wormadam-plant",
    "zygarde": "zygarde-50", "basculegion": "basculegion-male", "indeedee": "indeedee-male",
    "urshifu": "urshifu-single-strike", "oricorio": "oricorio-baile", "keldeo": "keldeo-ordinary",
    "palafin": "palafin-zero", "terapagos": "terapagos-terastal", "enamorus": "enamorus-incarnate",
    "tornadus": "tornadus-incarnate", "thundurus": "thundurus-incarnate", "landorus": "landorus-incarnate",
}
_slugs = None


def _valid_slugs():
    """The set of every valid PokeAPI slug, loaded from a bundled cache (fetched
    once from PokeAPI if the cache is missing). Empty set on total failure -- the
    resolver then falls back to the naive normalised name."""
    global _slugs
    if _slugs is None:
        try:
            with open(SLUGS_CACHE_FILE) as f:
                _slugs = set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            try:
                data = requests.get("https://pokeapi.co/api/v2/pokemon?limit=100000", timeout=20).json()
                _slugs = set(r["name"] for r in data["results"])
                with open(SLUGS_CACHE_FILE, "w") as f:
                    json.dump(sorted(_slugs), f)
            except (requests.RequestException, ValueError, KeyError, TypeError):
                _slugs = set()
    return _slugs


def _normalize(species: str) -> str:
    s = unicodedata.normalize("NFKD", species).encode("ascii", "ignore").decode().lower()
    s = s.replace(" ", "-").replace("'", "").replace(".", "").replace(":", "").replace("%", "")
    return re.sub("-+", "-", s).strip("-")


def pokeapi_name(species: str) -> str:
    """Resolve a drafted Pokemon's display name to a valid PokeAPI slug, choosing
    among candidate forme expansions by checking them against the real slug set."""
    slugs = _valid_slugs()
    base = _normalize(species)
    if not slugs:
        return base
    if base in slugs:
        return base
    # gendered megas: PokeAPI orders gender before "mega" (meowstic-male-mega)
    gm = re.match(r"(.+)-mega-([mf])$", base)
    if gm:
        cand = "{}-{}-mega".format(gm.group(1), "male" if gm.group(2) == "m" else "female")
        if cand in slugs:
            return cand
    if base.endswith("-mega"):
        stem = base[:-len("-mega")]
        for g in ("male", "female"):
            if f"{stem}-{g}-mega" in slugs:
                return f"{stem}-{g}-mega"
    parts = base.split("-")
    if len(parts) >= 2:
        stem, last = "-".join(parts[:-1]), parts[-1]
        for exp in _CODE_EXPANSIONS.get(last, []):
            if f"{stem}-{exp}" in slugs:
                return f"{stem}-{exp}"
        if stem in slugs:  # e.g. absol-mega-z -> absol-mega
            return stem
    if base in _DEFAULT_FORME and _DEFAULT_FORME[base] in slugs:
        return _DEFAULT_FORME[base]
    prefixed = sorted((s for s in slugs if s.startswith(base + "-")), key=len)
    return prefixed[0] if prefixed else base


def speed_at_50(base: int) -> int:
    """Max Level-50 Speed: 31 IV, 252 EV, positive nature.
    floor((2*base+94)*50/100)+5 = base+52, then *1.1."""
    return int((base + 52) * 1.1)


def speed_at_100(base: int) -> int:
    """Max Level-100 Speed: 31 IV, 252 EV, positive nature."""
    return int((2 * base + 99) * 1.1)


def _save_speed_cache():
    with open(SPEED_CACHE_FILE, "w") as f:
        json.dump(_speed_cache, f)


def _fetch_pokemon(slug: str):
    return requests.get(f"https://pokeapi.co/api/v2/pokemon/{slug}", timeout=15).json()


async def base_speed(species: str) -> int:
    """Base Speed stat for a species, cached across calls and persisted to disk."""
    if species in _speed_cache:
        return _speed_cache[species]
    slug = pokeapi_name(species)
    loop = asyncio.get_running_loop()
    try:
        data = await loop.run_in_executor(None, _fetch_pokemon, slug)
        spe = data["stats"][5]["base_stat"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, requests.RequestException):
        raise SpeedLookupError(slug)
    _speed_cache[species] = spe
    _save_speed_cache()
    return spe


async def team_base_speeds(mons) -> dict:
    """{species: base speed} for a team, sorted fastest first."""
    speeds = {str(p): await base_speed(str(p)) for p in mons}
    return dict(sorted(speeds.items(), key=lambda item: item[1], reverse=True))


def _download_sprite(slug: str):
    """Return sprite PNG bytes for a slug, or None. Tries SPRITE_URL_TEMPLATE
    first (if set), then PokeAPI's front_default."""
    if SPRITE_URL_TEMPLATE:
        try:
            r = requests.get(SPRITE_URL_TEMPLATE.format(slug=slug), timeout=15)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                return r.content
        except requests.RequestException:
            pass
    try:
        data = _fetch_pokemon(slug)
        url = (data.get("sprites") or {}).get("front_default")
        if url:
            r = requests.get(url, timeout=15)
            if r.ok:
                return r.content
    except (json.JSONDecodeError, requests.RequestException, AttributeError):
        pass
    return None


async def sprite_bytes(species: str):
    """PNG bytes for a species' sprite (cached under SPRITE_DIR), or None."""
    slug = pokeapi_name(species)
    path = os.path.join(SPRITE_DIR, slug + ".png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, _download_sprite, slug)
    if data:
        os.makedirs(SPRITE_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return data
