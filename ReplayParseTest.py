import unittest
import ParseReplay


class MyTestCase(unittest.TestCase):
    def test_something(self):
        pb = ParseReplay.parse_replay("https://replay.pokemonshowdown.com/dl-gen9paldeadexterapreview-75828")
        print(pb.winner.team)
        print(pb.loser.team)


if __name__ == '__main__':
    unittest.main()
