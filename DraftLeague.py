from DraftParticipant import DraftParticipant
from DraftPokemon import DraftPokemon
from Tier import Tier
import datetime
import json
import pickle
import random


class DraftLeague:
    """Represents a Draft League."""
    def __init__(self):
        """Initializes the Draft League and tiers Pokemon."""
        self._participants = []
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

    def add_missed_pick(self, user: DraftParticipant):
        """Adds a missed pick tor a user."""
        self._missedpicks.append(user)

    def add_participant(self, user: DraftParticipant):
        """Adds a DraftParticipant object to _participants."""
        self._participants.append(user)

    def available_pokemon(self, tier: Tier) -> list:
        """Returns a list of the available Pokemon in the given tier."""
        mon_list = []
        if tier == Tier.T1:
            for m in self._t1_list:
                if m.get_owner() is None:
                    mon_list.append(m)
        elif tier == Tier.T2:
            for m in self._t2_list:
                if m.get_owner() is None:
                    mon_list.append(m)
        elif tier == Tier.T3:
            for m in self._t3_list:
                if m.get_owner() is None:
                    mon_list.append(m)
        elif tier == Tier.T4:
            for m in self._t4_list:
                if m.get_owner() is None:
                    mon_list.append(m)
        elif tier == Tier.T5:
            for m in self._t5_list:
                if m.get_owner() is None:
                    mon_list.append(m)
        elif tier == Tier.MT1:
            for m in self._mt1_list:
                if m.get_owner() is None:
                    mon_list.append(m)
        elif tier == Tier.MT2:
            for m in self._mt2_list:
                if m.get_owner() is None:
                    mon_list.append(m)
        elif tier == Tier.MT3:
            for m in self._mt3_list:
                if m.get_owner() is None:
                    mon_list.append(m)
        return mon_list

    def draft(self, user: DraftParticipant, mon: DraftPokemon) -> bool:
        """Handling for adding Pokemon to a user across all phases of the draft.
        Returns True if successful, False if not."""
        if mon.get_owner() is not None:
            return False
        if self._phase == 0 or self._phase >= 3:
            return False
        elif self._phase == 2:
            return user.set_mon(mon)
        elif self._phase == 1:
            if user.set_mon(mon) is True:
                self.next_pick()
                return True
            return False

    def get_missed_picks(self) -> list:
        """Returns the list of missed draft picks."""
        return self._missedpicks

    def get_participants(self) -> list:
        """Returns the list of participants."""
        return self._participants

    def get_picking(self) -> (int, datetime):
        """During the draft phase, returns the current pick and the time it became current."""
        if self._phase == 1:
            return self._picking

    def get_phase(self) -> int:
        """Returns the current phase."""
        return self._phase

    def next_phase(self):
        """Increments the phase by 1."""
        self._phase += 1

    def next_pick(self):
        """Moves the draft to the next pick."""
        if len(self._pickorder) == 0:
            return
        self._picking[0] += 1
        self._picking[1] = datetime.datetime.now().replace(microsecond=0)

    def save(self):
        """Pickles and saves the league in a text file."""
        with open('files/league.txt', 'wb+') as file:
            pickle.dump(self, file)
            file.close()

    def set_pick_order(self):
        """Sets the pick order for the draft."""
        self._pickorder = 5 * (self._participants + self._participants[::-1])
        self._picking = (0, datetime.datetime.now().replace(microsecond=0))

    def shuffle(self):
        """Shuffles the order of the participants."""
        if self._phase == 0:
            random.shuffle(self._participants)

