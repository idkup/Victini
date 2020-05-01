from DraftParticipant import DraftParticipant
from DraftPokemon import DraftPokemon
from Tier import Tier
import json
import pickle
import random


class DraftLeague:
    """Represents a Draft League."""
    def __init__(self):
        """Initializes the Draft League and tiers Pokemon."""
        self._participants = []
        self._discordlist = []
        self._missedpicks = []
        self._phase = 0
        self._picking = None
        self._pickorder = []
        with open('files/tiers.json', 'r') as file:
            d = json.load(file)
            file.close()
        self._t1_list = [DraftPokemon(x, Tier.T1) for x in d['1']]
        self._t2_list = [DraftPokemon(x, Tier.T2) for x in d['2']]
        self._t3_list = [DraftPokemon(x, Tier.T3) for x in d['3']]
        self._t4_list = [DraftPokemon(x, Tier.T4) for x in d['4']]
        self._t5_list = [DraftPokemon(x, Tier.T5) for x in d['5']]
        self._mt1_list = [DraftPokemon(x, Tier.MT1) for x in d['101']]
        self._mt2_list = [DraftPokemon(x, Tier.MT2) for x in d['102']]
        self._mt3_list = [DraftPokemon(x, Tier.MT3) for x in d['103']]

    def add_participant(self, user: DraftParticipant):
        """Adds a DraftParticipant object to _participants."""
        self._participants.append(user)

    def get_participants(self) -> list:
        """Returns the list of participants."""
        return self._participants

    def get_phase(self) -> int:
        """Returns the current phase."""
        return self._phase

    def next_phase(self):
        """Increments the phase by 1."""
        self._phase += 1

    def save(self):
        """Pickles and saves the league in a text file."""
        with open('files/league.txt', 'wb+') as file:
            pickle.dump(self, file)
            file.close()

    def shuffle(self):
        """Shuffles the order of the participants."""
        if self._phase == 0:
            random.shuffle(self._participants)
