class BattleParticipant:
    """One side of a parsed battle: the Showdown display name, the side id
    ('p1'/'p2'), and the team of BattlePokemon."""

    def __init__(self, psname, side):
        self.psname = psname
        self.side = side
        self.team = []

    def __repr__(self):
        return "{} ({}): {}".format(self.psname, self.side, self.team)
