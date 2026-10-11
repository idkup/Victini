"""Tests for the manual scoring helpers: adjusting game differential (forfeits)
and attributing a replay's teams to named participants (mid-week roster changes)."""
import unittest

from BattlePokemon import BattlePokemon
from DraftLeague import DraftLeague
from DraftParticipant import DraftParticipant


def _bmon(species, kills=0, ko=False):
    m = BattlePokemon(species)
    m.direct_kills = kills
    m.ko = ko
    return m


class _Setup(unittest.TestCase):
    def setUp(self):
        self.lg = DraftLeague(1, "9", 111, 540, 180, 1000)
        self.mons = {str(m): m for m in self.lg.get_all_pokemon()}
        self.a = DraftParticipant(self.lg, 1, "alice", 540, 1000)
        self.b = DraftParticipant(self.lg, 2, "bob", 540, 1000)
        for p in (self.a, self.b):
            self.lg.add_participant(p)
        self.a_names = ["Garchomp", "Rotom-Wash", "Kingambit", "Toxapex", "Great Tusk", "Weavile"]
        self.b_names = ["Gholdengo", "Iron Valiant", "Skeledirge", "Corviknight", "Rotom", "Dragapult"]
        for p, names in ((self.a, self.a_names), (self.b, self.b_names)):
            for n in names:
                self.assertIs(p.set_mon(self.mons[n]), True, n)


class AdjustDiff(_Setup):
    def test_single_player(self):
        self.lg.adjust_diff(self.a, 3)
        self.assertEqual((self.a.get_diff(), self.b.get_diff()), (3, 0))

    def test_with_opponent_is_zero_sum(self):
        self.lg.adjust_diff(self.a, 4, self.b)
        self.lg.adjust_diff(self.a, -1, self.b)
        self.assertEqual((self.a.get_diff(), self.b.get_diff()), (3, -3))

    def test_find_participant(self):
        for token in ("<@1>", "<@!1>", "1", "ALICE"):
            self.assertIs(self.lg.find_participant(token), self.a, token)
        self.assertIsNone(self.lg.find_participant("nobody"))
        self.assertIsNone(self.lg.find_participant("999"))


class ManualAttribution(_Setup):
    def test_auto_identify_full_roster(self):
        team = [_bmon(n) for n in self.a_names]
        p, pairs = self.lg.identify_team(team)
        self.assertIs(p, self.a)
        self.assertEqual(len(pairs), 6)

    def test_traded_mon_breaks_auto_but_manual_credits_it(self):
        # alice played Weavile, then released it (mid-week change) before the
        # replay was submitted: auto-identification no longer matches her.
        weavile = self.mons["Weavile"]
        self.a.remove_mon(weavile)
        team = [_bmon(n, kills=1) for n in self.a_names]
        self.assertEqual(self.lg.identify_team(team), (None, []))

        pairs = self.lg.match_for_participant(self.a, team)
        self.assertEqual(len(pairs), 6)
        self.assertIn(weavile, [d for d, _ in pairs])     # falls back to league mon
        self.lg.credit_kills(pairs)
        self.assertEqual(weavile.get_kills(), 1)
        self.assertEqual(self.mons["Garchomp"].get_kills(), 1)

    def test_roster_preferred_and_exact_match_wins(self):
        # "Rotom-Wash" must map to the drafted Rotom-Wash, not a substring like Rotom
        team = [_bmon("Rotom-Wash")]
        (drafted, _), = self.lg.match_for_participant(self.a, team)
        self.assertIs(drafted, self.mons["Rotom-Wash"])

    def test_each_drafted_mon_used_once(self):
        team = [_bmon("Garchomp"), _bmon("Garchomp")]
        self.assertEqual(len(self.lg.match_mons(self.a.get_pokemon(), team)), 1)


class UnplayedGame(_Setup):
    def setUp(self):
        super().setUp()
        self.c = DraftParticipant(self.lg, 3, "carol", 540, 1000)
        self.lg.add_participant(self.c)

    def test_unscheduled_pair_has_no_game(self):
        self.assertFalse(self.lg.has_unplayed_game(self.a, self.b))   # no schedule yet
        self.lg._schedule = [[(self.a, self.b), (self.c, None)]]
        self.assertFalse(self.lg.has_unplayed_game(self.a, self.c))

    def test_game_consumed_by_result(self):
        self.lg._schedule = [[(self.a, self.b), (self.c, None)]]
        self.assertTrue(self.lg.has_unplayed_game(self.b, self.a))
        self.lg.record_result(1, 2, None, 6)
        self.assertFalse(self.lg.has_unplayed_game(self.a, self.b))

    def test_playoff_rematch_counts_as_new_game(self):
        self.lg._schedule = [[(self.a, self.b), (self.c, None)]]
        self.lg.record_result(1, 2, None, 6)
        self.lg._bracket = [[[self.a, self.b, None]]]
        self.assertTrue(self.lg.has_unplayed_game(self.a, self.b))


if __name__ == "__main__":
    unittest.main(verbosity=2)
