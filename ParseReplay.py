"""Parses a Pokemon Showdown battle log into per-Pokemon kill/death stats for
draft-league scoring.

Rebuilt on the robust log-parsing approach used by the /ch battle-log analyzer:
uniform ``|``-splitting, forme-change identity tracking, nickname resolution,
and tolerance of the ``|split|`` protocol's absolute+percent duplicate lines.
On top of that spine it attributes KOs (kills) and faints (deaths):

  * DIRECT kills   -- a KO dealt by the attacker's most recent move.
  * INDIRECT kills -- a KO from an effect the attacker is responsible for:
                      poison/burn, hazards (Stealth Rock/Spikes), damaging
                      weather (Sandstorm/Hail) or Leech Seed.

Self-inflicted faints (Life Orb, recoil, confusion, crash damage) count as a
death for the victim but credit no one. Attribution prefers the protocol's
explicit ``[of]`` tag and otherwise falls back to state tracked from the log
(who set the status/hazard/weather/seed). The parser never raises on malformed
or unexpected lines -- an unrecognised line is skipped.

Nicknames, forme changes and Ditto's Imposter transform (which keeps the same
protocol ident) are all handled. Illusion (Zoroark/Zorua) is handled as far as
the protocol allows: Showdown reveals the true mon via ``|replace|`` the moment
it takes damage and before it faints, so faints and post-reveal KOs attribute
correctly; a KO dealt while still fully disguised is the one case the protocol
does not let us disentangle, and it lands on the disguise identity.
"""
from __future__ import annotations

import requests

from BattleParticipant import BattleParticipant
from BattlePokemon import BattlePokemon
from ParsedBattle import ParsedBattle

# [from] sources that damage the mon itself -- never credited to an opponent.
_SELF_SOURCES = {
    "Recoil", "recoil", "confusion", "steelbeam", "Struggle", "High Jump Kick",
    "Jump Kick", "Curse", "Belly Drum", "Pain Split", "Mind Blown", "chloroblast",
    "Life Orb",
}
_DAMAGING_STATUS = {"psn", "tox", "brn"}
_DAMAGING_WEATHER = {"Sandstorm", "Hail"}
_HAZARDS = {"Stealth Rock", "Spikes", "Toxic Spikes"}


def _parse_ident(token):
    """'p1a: Fluffy' -> ('p1', 'Fluffy'). The slot letter (a/b) is dropped."""
    token = token.strip()
    side = token[:2]
    name = token.split(": ", 1)[1].strip() if ": " in token else token[3:].strip()
    return side, name


def _species_of(details):
    """'Meowscarada, L50, M' -> 'Meowscarada'; strips a trailing '-*' marker."""
    species = details.split(",", 1)[0].strip()
    if species.endswith("-*"):
        species = species[:-2]
    return species


def _tag(parts, prefix):
    """Value after e.g. '[from] ' among a line's fields, or None."""
    for p in parts:
        p = p.strip()
        if p.startswith(prefix):
            return p[len(prefix):].strip()
    return None


def _is_faint_hp(hp_field):
    hp_field = hp_field.strip()
    return hp_field == "0" or "fnt" in hp_field


def parse_battle(log):
    """Parse a list of raw protocol lines into a ParsedBattle."""
    sides = {"p1": BattleParticipant("", "p1"), "p2": BattleParticipant("", "p2")}
    by_nick = {"p1": {}, "p2": {}}          # nickname -> BattlePokemon
    active = {"p1": None, "p2": None}        # current mon per side
    # (direct, indirect) kills the active mon had when it entered, so a KO earned
    # while an Illusion (Zoroark/Zorua) is disguised can be moved to the real mon
    # when the disguise breaks (see the 'replace' handler).
    stint_start = {"p1": (0, 0), "p2": (0, 0)}

    status_source = {}                       # victim mon -> source mon
    seed_source = {}                         # victim mon -> source mon
    hazard_setter = {"p1": {}, "p2": {}}     # side hazards sit ON -> {hazard: setter}
    weather_source = None                    # mon that set the current damaging weather
    last_move = None                         # (side, attacker mon)
    winner_name = None

    def opp(side):
        return "p2" if side == "p1" else "p1"

    def resolve(token):
        side, nick = _parse_ident(token)
        mon = by_nick.get(side, {}).get(nick) or active.get(side)
        return side, mon

    def bind_switch(side, nick, species):
        """Attach an incoming nickname to a team slot, matching by species."""
        team = sides[side].team
        base = species.split("-", 1)[0]
        chosen = None
        for m in team:                       # exact species, still unbound
            if m.species == species and m.nickname is None:
                chosen = m
                break
        if chosen is None:                   # base-name match, still unbound
            for m in team:
                if m.nickname is None and m.species.split("-", 1)[0] == base:
                    chosen = m
                    break
        if chosen is None:                   # already-seen nickname (re-entry)
            chosen = by_nick[side].get(nick)
        if chosen is None:                   # any unbound slot, else append
            chosen = next((m for m in team if m.nickname is None), None)
            if chosen is None:
                chosen = BattlePokemon(species)
                team.append(chosen)
        chosen.nickname = nick
        if species and species != chosen.species:
            chosen.species = species          # prefer the revealed forme
        by_nick[side][nick] = chosen
        active[side] = chosen
        return chosen

    for line in log:
        if not line or line[0] != "|":
            continue
        parts = line.split("|")
        kind = parts[1] if len(parts) > 1 else ""

        if kind == "player" and len(parts) > 3 and parts[3]:
            # Showdown re-emits '|player|pX|' with a blank name when a player
            # leaves at the end of a battle; ignore those so the real name set
            # earlier is not clobbered with "".
            side = parts[2]
            if side in sides:
                sides[side].psname = parts[3]

        elif kind == "poke" and len(parts) > 3:
            side = parts[2]
            if side in sides:
                sides[side].team.append(BattlePokemon(_species_of(parts[3])))

        elif kind in ("switch", "drag") and len(parts) > 3:
            side, nick = _parse_ident(parts[2])
            if side in sides:
                mon = bind_switch(side, nick, _species_of(parts[3]))
                stint_start[side] = (mon.direct_kills, mon.indirect_kills)

        elif kind == "replace" and len(parts) > 3:
            # Illusion (Zoroark/Zorua) breaks: the mon that has been active this
            # whole stint under a disguised identity is revealed here. Any KO it
            # earned while disguised was credited to the copied mon, so move this
            # stint's kills to the real Zoroark, then rebind the field identity.
            side, nick = _parse_ident(parts[2])
            if side in sides:
                disguise = active[side]
                snap_d, snap_i = stint_start[side]
                real = bind_switch(side, nick, _species_of(parts[3]))
                if disguise is not None and disguise is not real:
                    d = disguise.direct_kills - snap_d
                    ind = disguise.indirect_kills - snap_i
                    if d > 0:
                        real.direct_kills += d
                        disguise.direct_kills -= d
                    if ind > 0:
                        real.indirect_kills += ind
                        disguise.indirect_kills -= ind
                stint_start[side] = (real.direct_kills, real.indirect_kills)

        elif kind in ("detailschange", "-formechange", "-mega", "-primal") and len(parts) > 3:
            side, mon = resolve(parts[2])
            if mon is not None:
                mon.species = _species_of(parts[3])

        elif kind == "move" and len(parts) > 3:
            side, attacker = resolve(parts[2])
            move_name = parts[3]
            if attacker is not None:
                last_move = (side, attacker)
                if move_name in _HAZARDS:
                    hazard_setter[opp(side)][move_name] = attacker

        elif kind == "-weather" and len(parts) > 2:
            weather = parts[2].strip()
            of_tok = _tag(parts, "[of] ")
            if weather in _DAMAGING_WEATHER:
                if of_tok:
                    weather_source = resolve(of_tok)[1]
                elif last_move is not None:
                    weather_source = last_move[1]
            elif weather in ("none", ""):
                weather_source = None

        elif kind == "-status" and len(parts) > 3:
            side, victim = resolve(parts[2])
            status = parts[3].strip()
            if victim is not None and status in _DAMAGING_STATUS:
                from_txt = _tag(parts, "[from] ")
                of_tok = _tag(parts, "[of] ")
                if from_txt and (from_txt.startswith("move: Rest") or from_txt.startswith("item:")):
                    status_source.pop(victim, None)
                elif of_tok:
                    status_source[victim] = resolve(of_tok)[1]
                elif last_move is not None and last_move[0] == opp(side):
                    status_source[victim] = last_move[1]
                else:
                    status_source[victim] = hazard_setter[side].get("Toxic Spikes")

        elif kind == "-start" and len(parts) > 3 and "Leech Seed" in parts[3]:
            side, victim = resolve(parts[2])
            if victim is not None:
                of_tok = _tag(parts, "[of] ")
                src = resolve(of_tok)[1] if of_tok else (last_move[1] if last_move else None)
                if src is not None:
                    seed_source[victim] = src

        elif kind == "-damage" and len(parts) > 3 and _is_faint_hp(parts[3]):
            side, victim = resolve(parts[2])
            if victim is None or victim.ko:
                continue
            victim.ko = True
            from_txt = _tag(parts, "[from] ")
            of_tok = _tag(parts, "[of] ")
            of_mon = resolve(of_tok)[1] if of_tok else None

            source = None
            direct = False
            if from_txt is None:                          # KO from the last move
                if last_move is not None and last_move[0] == opp(side):
                    source, direct = last_move[1], True
            elif from_txt in _SELF_SOURCES or from_txt.startswith("item:"):
                source = None                             # self-inflicted (recoil, Life Orb, ...)
            elif from_txt in _DAMAGING_STATUS:
                source = of_mon or status_source.get(victim)
            elif from_txt in _DAMAGING_WEATHER:
                source = of_mon or weather_source
            elif from_txt == "Leech Seed":
                source = of_mon or seed_source.get(victim)
            elif from_txt in _HAZARDS:
                source = of_mon or hazard_setter[side].get(from_txt)
            else:                                          # ability chip, etc.
                source = of_mon

            if source is not None and source not in sides[side].team:
                if direct:
                    source.direct_kills += 1
                else:
                    source.indirect_kills += 1

        elif kind == "faint" and len(parts) > 2:
            side, victim = resolve(parts[2])
            if victim is not None:
                victim.ko = True

        elif kind in ("win", "tie"):
            winner_name = parts[2].strip() if len(parts) > 2 else None

    battle = ParsedBattle()
    if winner_name is not None:
        for side, participant in sides.items():
            if participant.psname == winner_name:
                battle.winner = participant
                battle.loser = sides[opp(side)]
                break
    return battle


def parse_replay(msg):
    """Fetch a Showdown replay by URL and parse it. Accepts the page URL
    (the '.json' suffix is added if missing)."""
    url = msg if msg.endswith(".json") else msg + ".json"
    replay_json = requests.get(url).json()
    log = replay_json.get("log", "").split("\n")
    return parse_battle(log)
