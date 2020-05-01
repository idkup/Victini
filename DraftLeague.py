from DraftParticipant import DraftParticipant
from DraftPokemon import DraftPokemon
from Tier import Tier


class DraftLeague():
    def __init__(self):
        self.participants = []
        self.idlist = []
        self.missedpicks = []
        self.phase = 0
        self.picking = None
        self.pickorder = []
