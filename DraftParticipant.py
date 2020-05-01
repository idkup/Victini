from DraftPokemon import DraftPokemon
from Tier import Tier
from typing import Union


class DraftParticipant:
    """Represents a participant in a DraftLeague."""
    def __init__(self, discord_id, name, points=400):
        """Initializes the participant."""
        self._name = name
        self._discord_id = discord_id
        self._showdown_id = []
        self._points = points
        self._mega = None
        self._tier1 = None
        self._tier2 = None
        self._tier3 = None
        self._tier4 = None
        self._tier5 = None
        self._free = []

    def __str__(self):
        """Behavior when stringified."""
        return """{}'s Draft ({} points remaining):
        ---
        Mega: {}
        T1: {}
        T2: {}
        T3: {}
        T4: {}
        T5: {}
        Flex: {}""".format(self._name, self._points, self._mega, self._tier1, self._tier2, self._tier3,
                           self._tier4, self._tier5, ", ".join([str(x) for x in self._free]))

    def add_points(self, points: int):
        """Adds points to a participant."""
        self._points += points

    def add_showdown(self, s_id: str):
        """Adds a Showdown ID to a participant."""
        self._showdown_id.append(s_id)

    def get_discord(self) -> int:
        """Returns the participant's Discord ID."""
        return self._discord_id

    def get_name(self) -> str:
        """Returns the participant's name."""
        return self._name

    def get_sd(self) -> list:
        """Returns a list of the participant's Showdown IDs."""
        return self._showdown_id

    def remove_mon(self, mon: DraftPokemon) -> Union[DraftPokemon, bool]:
        """Removes a Pokemon from a participant, and refunds points if applicable.
        Returns the removed Pokemon if successful, False if not."""
        if self._mega == mon:
            if mon.get_tier().value + self._points < 0:
                return False
            self._points += mon.get_tier().value
            self._mega = None
            mon.set_owner(None)
            return mon
        elif mon in self._free:
            self._points += mon.get_tier().value
            self._free.remove(mon)
            mon.set_owner(None)
            return mon
        if self._tier1 == mon:
            self._tier1 = None
            tier = Tier.T1
        elif self._tier2 == mon:
            self._tier2 = None
            tier = Tier.T2
        elif self._tier3 == mon:
            self._tier3 = None
            tier = Tier.T3
        elif self._tier4 == mon:
            self._tier4 = None
            tier = Tier.T4
        elif self._tier5 == mon:
            self._tier5 = None
            tier = Tier.T5
        else:
            return False
        for m in self._free:
            if m.get_tier() == tier:
                self._points += tier.value
                self._free.remove(m)
                if tier == Tier.T1:
                    self._tier1 = m
                elif tier == Tier.T2:
                    self._tier2 = m
                elif tier == Tier.T3:
                    self._tier3 = m
                elif tier == Tier.T4:
                    self._tier4 = m
                else:
                    self._tier5 = m
                break
        mon.set_owner(None)
        return mon

    def remove_sd(self, s_id: str) -> bool:
        """Removes a previously assigned Showdown ID. Returns True if successful, False if not."""
        if s_id in self._showdown_id:
            self._showdown_id.remove(s_id)
            return True
        return False

    def set_mon(self, mon: DraftPokemon) -> bool:
        """Adds a Pokemon to a participant, and charges points if applicable.
        Returns True if successful, False if not."""
        tier = mon.get_tier()
        if tier in [Tier.MT1, Tier.MT2, Tier.MT3]:
            if not self._mega and self._points >= tier.value:
                self._points -= tier.value
                self._mega = mon
                mon.set_owner(self)
                return True
            else:
                return False
        elif tier == Tier.T1:
            if not self._tier1:
                self._tier1 = mon
                mon.set_owner(self)
                return True
        elif tier == Tier.T2:
            if not self._tier2:
                self._tier2 = mon
                mon.set_owner(self)
                return True
        elif tier == Tier.T3:
            if not self._tier3:
                self._tier3 = mon
                mon.set_owner(self)
                return True
        elif tier == Tier.T4:
            if not self._tier4:
                self._tier4 = mon
                mon.set_owner(self)
                return True
        else:
            if not self._tier5:
                self._tier5 = mon
                mon.set_owner(self)
                return True
        if len(self._free) > 3 or self._points < tier.value:
            return False
        self._points -= tier.value
        self._free.append(mon)
        mon.set_owner(self)
        return True

    def substitute(self, name, d_id):
        """Substitutes in a different player, replacing name and Discord ID while wiping the Showdown ID list."""
        self._discord_id = d_id
        self._name = name
        self._showdown_id = []
