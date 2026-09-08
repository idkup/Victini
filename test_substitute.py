"""A mid-season !substitute mutates a participant's discord id/name in place.
These tests confirm the season logic (results, standings, result_for, and
later-recorded games) stays correct across a substitution, because season state
keys on participant *objects*, not ids."""
import unittest

from DraftLeague import DraftLeague
from DraftParticipant import DraftParticipant


class SubstituteMidSeason(unittest.TestCase):
    def setUp(self):
        self.lg = DraftLeague(1, "9", 111, 540, 180, 110)
        cheap = [m for m in self.lg.get_all_pokemon() if m.get_cost() == 1]
        self.ps = {}
        for i, name in enumerate("abcd"):
            p = DraftParticipant(self.lg, i + 1, name, 540, 110)
            self.lg.add_participant(p)
            p.set_mon(cheap[i])
            self.ps[name] = p
        # a beat b, then c beat a
        self.lg.record_result(1, 2, "u1")
        self.lg.record_result(3, 1, "u2")

    def test_results_survive_substitution(self):
        a, b, c, d = (self.ps[x] for x in "abcd")
        self.assertEqual(a.get_record(), "1-1")
        pre = [p.get_name() for p in self.lg.standings()]

        # substitute the manager of team 'a': id 1 -> 99, name -> 'a2'
        a.substitute("a2", 99)

        # the object is unchanged in the schedule/results, only its id/name differ
        self.assertIs(self.lg._participant_by_id(99), a)
        self.assertIsNone(self.lg._participant_by_id(1))
        # pre-substitution games are still attributed to the same team object
        self.assertEqual(self.lg.result_for(a, b), (a, b, "u1"))
        self.assertEqual(self.lg.result_for(c, a), (c, a, "u2"))
        # record/standings carry over unchanged (only the name updates)
        self.assertEqual(a.get_record(), "1-1")
        self.assertEqual([("a2" if n == "a" else n) for n in pre],
                         [p.get_name() for p in self.lg.standings()])

    def test_later_game_records_under_new_id(self):
        a, d = self.ps["a"], self.ps["d"]
        a.substitute("a2", 99)
        # a previously-unplayed game for this team, played after the sub, resolves
        # to the same object via its new id and attaches to the right pairing
        self.assertTrue(self.lg.record_result(99, 4, "u3"))
        self.assertEqual(a.get_record(), "2-1")
        self.assertEqual(self.lg.result_for(a, d), (a, d, "u3"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
