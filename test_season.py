"""Unit tests for season.py (round-robin, standings ranking, single-elim bracket).
Pure and network-free -- uses lightweight fake participants."""
import unittest

import season


class _Mon:
    def __init__(self, kills, deaths):
        self._k, self._d = kills, deaths

    def get_kills(self):
        return self._k

    def get_deaths(self):
        return self._d


class _P:
    def __init__(self, pid, wins=0, mons=()):
        self._id = pid
        self._wins = wins
        self._mons = list(mons)

    def get_discord(self):
        return self._id

    def get_pokemon(self):
        return self._mons


class RoundRobin(unittest.TestCase):
    def test_even_count_is_full_round_robin(self):
        ps = [_P(i) for i in range(8)]
        sched = season.round_robin(ps, 8)
        self.assertEqual(len(sched), 8)
        self.assertTrue(all(len(w) == 4 for w in sched))
        pairs = {frozenset((a.get_discord(), b.get_discord())) for w in sched for a, b in w}
        self.assertEqual(len(pairs), 28)             # every pair among 8 meets once
        for w in sched:
            for a, b in w:
                self.assertIsNot(a, b)               # nobody plays themselves

    def test_odd_count_has_one_bye_per_week(self):
        ps = [_P(i) for i in range(9)]
        for week in season.round_robin(ps, 8):
            self.assertEqual(sum(1 for a, b in week if a is None or b is None), 1)

    def test_weeks_length_is_respected(self):
        self.assertEqual(len(season.round_robin([_P(i) for i in range(6)], 8)), 8)
        self.assertEqual(len(season.round_robin([_P(i) for i in range(6)], 3)), 3)

    def test_fewer_than_two(self):
        self.assertEqual(season.round_robin([_P(1)], 8), [[] for _ in range(8)])


class Ranking(unittest.TestCase):
    def test_wins_then_killdiff_then_h2h(self):
        a = _P(1, wins=3, mons=[_Mon(10, 2)])   # +8
        b = _P(2, wins=3, mons=[_Mon(5, 5)])     # 0
        c = _P(3, wins=3, mons=[_Mon(10, 2)])    # +8, tied with a -> head-to-head
        results = [(c, a, "url")]                # c beat a (participant objects)
        self.assertEqual([p.get_discord() for p in season.rank([a, b, c], results)], [3, 1, 2])

    def test_wins_dominate_killdiff(self):
        a = _P(1, wins=1, mons=[_Mon(0, 9)])     # -9 but more wins
        b = _P(2, wins=0, mons=[_Mon(9, 0)])     # +9
        self.assertEqual([p.get_discord() for p in season.rank([a, b], [])], [1, 2])


class Bracket(unittest.TestCase):
    def test_top8_standard_seeding(self):
        seeds = [_P(i) for i in range(1, 9)]
        br = season.bracket_from_seeds(seeds, 8)
        self.assertEqual([len(r) for r in br], [4, 2, 1])
        self.assertEqual([(m[0].get_discord(), m[1].get_discord()) for m in br[0]],
                         [(1, 8), (4, 5), (2, 7), (3, 6)])

    def test_non_power_of_two_gives_top_seeds_byes(self):
        br = season.bracket_from_seeds([_P(i) for i in range(1, 7)], 6)   # 6 -> bracket of 8
        bye_seeds = {m[0].get_discord() for m in br[0] if m[1] is None}
        self.assertEqual(bye_seeds, {1, 2})
        # the two byes are pre-advanced into round 2
        r2_ids = {x.get_discord() for m in br[1] for x in m[:2] if x is not None}
        self.assertEqual(r2_ids, {1, 2})

    def test_advance(self):
        seeds = [_P(i) for i in range(1, 9)]
        br = season.bracket_from_seeds(seeds, 8)
        self.assertTrue(season.advance_bracket(br, 1, 8, lambda p: p.get_discord()))
        self.assertEqual(br[1][0][0].get_discord(), 1)   # winner into round 2
        self.assertFalse(season.advance_bracket(br, 1, 5, lambda p: p.get_discord()))  # not a live pair


if __name__ == "__main__":
    unittest.main(verbosity=2)
