from DraftPokemon import DraftPokemon
from typing import Union
import datetime


class DraftParticipant:
    """Represents a participant in a DraftLeague."""
    def __init__(self, league, discord_id, name, timer_start, points=120):
        """Initializes the participant."""
        self._league = league
        self._name = name
        self._discord_id = discord_id
        self._showdown_id = []
        self._next_pick = []
        self._points = points
        self._pokemon = []
        self._mega = False
        self._timer = datetime.timedelta(minutes=timer_start)

    def __str__(self):
        """Behavior when stringified."""
        return """{}'s draft in league {} ({} points remaining):
---
{}""".format(self._name, self._league.get_id(), self._points,
             "\n".join(["{} ({}-{}) [{}p]".format(x, x.get_kills, x.get_deaths, x.get_cost()) for x in self._pokemon]))

    def add_showdown(self, s_id: str):
        """Adds a Showdown ID to a participant."""
        self._showdown_id.append(s_id)

    def get_discord(self) -> int:
        """Returns the participant's Discord ID."""
        return self._discord_id

    def get_name(self) -> str:
        """Returns the participant's name."""
        return self._name

    def get_next_pick(self) -> list:
        """Returns the participant's next pick."""
        return self._next_pick

    def get_points(self) -> int:
        """Returns the participant's available points."""
        return self._points

    def get_pokemon(self) -> list:
        """Returns the participant's Pokemon."""
        return self._pokemon

    def get_sd(self) -> list:
        """Returns a list of the participant's Showdown IDs."""
        return self._showdown_id

    def get_timer(self):
        """Returns the participant's timer."""
        return self._timer

    def add_time_to_timer(self, mins_to_add: int, remove=False):
        """Remove time from the user's timer."""
        if remove:
            if datetime.timedelta(minutes=round(mins_to_add, 2)) > self._timer:
                self._timer = datetime.timedelta(minutes=0)
            else:
                self._timer -= datetime.timedelta(minutes=round(mins_to_add, 2))
        else:
            self._timer += datetime.timedelta(minutes=round(mins_to_add, 2))
        return self._timer

    def remove_mon(self, mon: DraftPokemon) -> Union[DraftPokemon, str]:
        """Removes a Pokemon from a participant and refunds points.
        Returns the removed Pokemon if successful, error message if not."""
        if mon not in self._pokemon:
            return "Cannot release an unowned Pokemon."
        if mon.is_mega():
            self._mega = False
        self._pokemon.remove(mon)
        self._points += mon.get_cost()
        mon.set_owner(None)
        return mon

    def remove_sd(self, s_id: str) -> bool:
        """Removes a previously assigned Showdown ID. Returns True if successful, False if not."""
        if s_id in self._showdown_id:
            self._showdown_id.remove(s_id)
            return True
        return False

    def set_mon(self, mon: DraftPokemon) -> Union[bool, str]:
        """Adds a Pokemon to the participant, and charges points if applicable.
        Returns True if successful, error message if not."""
        cost = mon.get_cost()
        if mon.get_owner() is not None:
            return "This Pokemon has already been drafted!"
        if self._points - cost < 9 - len(self._pokemon) or self._points - cost < 0:
            return "You do not have enough points to draft this Pokemon."
        if mon.is_mega():
            if self._mega:
                return "You have already drafted a Mega Evolution."
            self._mega = True
        if len(self._pokemon) >= 12:
            return "You have already drafted 12 Pokemon."
        self._pokemon.append(mon)
        self._points -= cost
        mon.set_owner(self)
        return True

    def set_next_pick(self, picks: list):
        """Modifies self._next_picks"""
        self._next_pick = picks

    def set_points(self, points: int):
        """Sets the participant's points."""
        self._points = points

    def substitute(self, name: str, d_id: int):
        """Substitutes in a different player, replacing name and Discord ID while wiping the Showdown ID list."""
        self._discord_id = d_id
        self._name = name
        self._showdown_id = []
