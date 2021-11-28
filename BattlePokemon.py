class BattlePokemon:
    def __init__(self, species):
        self.species = species
        self.nickname = species
        self.direct_kills = 0
        self.indirect_kills = 0
        self.ko = False
        self.status_induced = None

    def __repr__(self):
        return f"{self.nickname} ({self.species}), kills: {self.direct_kills} direct, {self.indirect_kills} indirect, fainted: {self.ko}"