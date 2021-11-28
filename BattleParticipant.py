class BattleParticipant:
    def __init__(self, psname):
        self.psname = psname
        self.team = []
        self.rocks_set = None
        self.spikes_set = None
        self.tspikes_set = None

    def __repr__(self):
        return f"""{self.psname}: {self.team}"""
