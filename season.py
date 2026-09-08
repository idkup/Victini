"""Pure season helpers: round-robin scheduling, standings ranking, and
single-elimination bracket seeding/advancement. No I/O and no Discord/model
imports -- everything operates on duck-typed participants (objects exposing
get_discord(), get_pokemon(), and a `_wins` attribute) so it is unit-testable
with lightweight fakes.

A bye is represented by None wherever a participant would appear.
"""
from __future__ import annotations


# ---- round-robin schedule ---------------------------------------------------

def round_robin(participants, weeks=8):
    """Circle-method round-robin. Returns `weeks` rounds; each round is a list of
    (participant, participant-or-None) pairings (None = bye). Odd counts get one
    bye per round. The N-1 rotation is cycled (or truncated) to exactly `weeks`."""
    ps = list(participants)
    if len(ps) < 2:
        return [[] for _ in range(weeks)]
    if len(ps) % 2:
        ps.append(None)                      # bye slot
    n = len(ps)
    rounds = []
    arr = ps[:]
    for _ in range(n - 1):
        rounds.append([(arr[i], arr[n - 1 - i]) for i in range(n // 2)])
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]   # rotate all but the first
    return [rounds[i % len(rounds)] for i in range(weeks)]


# ---- standings --------------------------------------------------------------

def kill_diff(participant):
    return sum(m.get_kills() - m.get_deaths() for m in participant.get_pokemon())


def rank(participants, results):
    """Order participants by (wins desc, kill_diff desc), breaking any group still
    tied on both by head-to-head wins within that group. `results` is a list of
    (winner_id, loser_id, ...) tuples."""
    def wins(p):
        return getattr(p, "_wins", 0)

    base = sorted(participants, key=lambda p: (wins(p), kill_diff(p)), reverse=True)
    ordered = []
    i = 0
    while i < len(base):
        j = i
        while (j < len(base)
               and wins(base[j]) == wins(base[i])
               and kill_diff(base[j]) == kill_diff(base[i])):
            j += 1
        group = base[i:j]
        if len(group) > 1:
            gids = {p.get_discord() for p in group}
            group.sort(key=lambda p: sum(1 for r in results
                                         if r[0] == p.get_discord() and r[1] in gids),
                       reverse=True)
        ordered.extend(group)
        i = j
    return ordered


# ---- single-elimination bracket --------------------------------------------

def _next_pow2(n):
    p = 1
    while p < n:
        p *= 2
    return p


def _seed_order(size):
    """Standard single-elim seed positions for a power-of-two bracket, e.g.
    size 8 -> [1, 8, 4, 5, 2, 7, 3, 6]."""
    order = [1]
    while len(order) < size:
        m = len(order) * 2 + 1
        order = [x for o in order for x in (o, m - o)]
    return order


def _round1_pairs(seeds, size):
    """Round-1 (a, b) pairings for the top `size` seeds; the bracket is padded to
    the next power of two with byes (None) placed against the top seeds."""
    seeds = list(seeds)[:size]
    if not seeds:
        return []
    bsize = _next_pow2(len(seeds))
    slots = [seeds[s - 1] if s - 1 < len(seeds) else None for s in _seed_order(bsize)]
    return [(slots[i], slots[i + 1]) for i in range(0, bsize, 2)]


def bracket_from_seeds(seeds, size):
    """Full bracket as a list of rounds; each matchup is a mutable list
    [a, b, winner]. Round-1 byes are pre-resolved and propagated one level."""
    pairs = _round1_pairs(seeds, size)
    if not pairs:
        return []
    rounds = [[[a, b, (a if b is None else b if a is None else None)] for a, b in pairs]]
    m = len(pairs)
    while m > 1:
        m //= 2
        rounds.append([[None, None, None] for _ in range(m)])
    _propagate(rounds)
    return rounds


def _propagate(rounds):
    """Push each resolved winner into its slot in the next round."""
    for ri in range(len(rounds) - 1):
        for mi, match in enumerate(rounds[ri]):
            if match[2] is not None:
                rounds[ri + 1][mi // 2][mi % 2] = match[2]


def advance_bracket(rounds, winner_id, loser_id, id_of):
    """Resolve the first unfinished matchup whose two players' ids equal
    {winner_id, loser_id}, set its winner, and propagate. `id_of(participant)`
    returns a participant's discord id. Returns True if a matchup advanced."""
    for match in (m for rnd in rounds for m in rnd):
        a, b, w = match
        if w is not None or a is None or b is None:
            continue
        ids = {id_of(a), id_of(b)}
        if ids == {winner_id, loser_id}:
            match[2] = a if id_of(a) == winner_id else b
            _propagate(rounds)
            return True
    return False
