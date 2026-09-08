class BattlePokemon:
    """A single Pokemon within a parsed battle, with the kills/deaths it earned."""

    def __init__(self, species):
        self.species = species
        self.nickname = None          # bound when the mon first switches in
        self.direct_kills = 0         # KOs dealt by this mon's own moves
        self.indirect_kills = 0       # KOs from hazards/status/weather/seed it caused
        self.ko = False               # whether this mon fainted

    @property
    def kills(self):
        return self.direct_kills + self.indirect_kills

    def __repr__(self):
        return "{}: {} KO(s) ({} direct, {} indirect), {}".format(
            self.species, self.kills, self.direct_kills, self.indirect_kills,
            "fainted" if self.ko else "alive")
