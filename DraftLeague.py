from DraftParticipant import DraftParticipant
from DraftPokemon import DraftPokemon
import datetime
import json
import pickle
import random
from typing import Union


class DraftLeague:
    """Represents a Draft League."""

    def __init__(self, league_id, tierlist, channel, timer_start, increment, pts):
        """Initializes the Draft League and tiers Pokemon."""
        self._league_id = league_id
        self._participants = []
        self._missedpicks = []
        self._phase = 0
        self._picking = None
        self._pickorder = []
        self._points_per_participant = pts
        self._timer_start = int(timer_start)
        self._increment = int(increment)
        self._channel = channel
        self._replay_channel = None
        with open('files/{}.json'.format(tierlist), 'r') as file:
            d = json.load(file)
            file.close()
        self._tierlist = [DraftPokemon(k, v, "-Mega" in k or "Mega " in k) for k, v in d.items()]

    def add_missed_pick(self, user: DraftParticipant):
        """Adds a missed pick to a user."""
        self._missedpicks.append(user)

    def add_participant(self, user: DraftParticipant):
        """Adds a DraftParticipant object to _participants."""
        self._participants.append(user)

    def add_pokemon(self, name: str, cost: int):
        """Adds a DraftPokemon object to _tierlist."""
        self._tierlist.append(DraftPokemon(name, cost, "-Mega" in name))

    def available_pokemon(self, cost: int) -> list:
        """Returns a list of the available Pokemon in the given tier."""
        mon_list = []
        for m in self._tierlist:
            if m.get_cost() == cost and m.get_owner() is None:
                mon_list.append(str(m))
        return mon_list

    def check_pick_deadline(self) -> str:
        """Checks if the current picker has run out of time, calls add_missed_pick() and next_pick() if so.
        Returns message to be sent."""
        current_picker = self._pickorder[self._picking[0]]
        if self._phase != 1:
            return "It is no longer the drafting phase."
        if datetime.datetime.now() - self._picking[1] > current_picker.get_timer():
            self.add_missed_pick(current_picker)
            return "<@{}> has missed their pick! ".format(
                current_picker.get_discord()) + self.next_pick()
        elif current_picker.get_points() == 0:
            return "{} has used all their points. ".format(current_picker.get_name()) + self.next_pick()
        elif current_picker.get_next_pick():
            for p in current_picker.get_next_pick():
                for mon in self.get_all_pokemon():
                    if str(mon).lower() == p[0].strip().lower():
                        if p[1] == 0 or p[1] == self._picking[0] // len(self._participants) + 1:
                            to_draft = mon
                            break
                else:
                    continue
                if current_picker.set_mon(to_draft) is True:
                    new_predrafts = []
                    for p in current_picker.get_next_pick():
                        if p[1] == 0 or p[1] > (self._picking[0] // len(self._participants) + 1):
                            new_predrafts.append(p)
                    current_picker.set_next_pick(new_predrafts)
                    return "<@{}> has drafted {}! ".format(current_picker.get_discord(),
                                                           str(to_draft)) + self.next_pick()

    def clear_participants(self):
        """Deletes all participants. Debug use only."""
        self._participants = []

    def draft(self, user: DraftParticipant, mon: DraftPokemon) -> str:
        """Handling for adding Pokemon to a user across all phases of the draft.
        Returns message to be sent."""
        if mon.get_owner() is not None:
            return "{} has already been drafted!".format(str(mon))
        if self._phase == 0 or self._phase >= 3:
            return "You cannot draft in this phase."
        elif self._phase == 2:
            if user.set_mon(mon) is True:
                return "<@{}> has drafted {}!".format(user.get_discord(), str(mon))
            return "Could not draft {}.".format(str(mon))
        elif self._phase == 1:
            if user in self._missedpicks:
                if user.set_mon(mon) is True:
                    self._missedpicks.remove(user)
                    return "<@{}> has drafted {}!".format(user.get_discord(), str(mon))
            elif user != self._pickorder[self._picking[0]]:
                return "It is not your turn to pick!"
            if user.set_mon(mon) is True:
                return "<@{}> has drafted {}! {}".format(user.get_discord(), str(mon), self.next_pick())
            return "Could not draft {}.".format(str(mon))

    def find_mon(self, mon: DraftPokemon) -> str:
        """Returns basic information about a DraftPokemon object."""
        if mon.get_owner():
            return "{} ({}-{}) costs {} and is owned by {}.".format(str(mon), mon.get_kills(), mon.get_deaths(),
                                                                    mon.get_cost(), mon.get_owner().get_name())
        return "{} ({}-{}) costs {} and is currently unowned.".format(str(mon), mon.get_kills(), mon.get_deaths(),
                                                                      mon.get_cost())

    def get_all_pokemon(self) -> list:
        """Returns the list of all Pokemon in the league."""
        return self._tierlist

    def get_channel(self) -> int:
        """Returns the Discord channel for the draft of this league."""
        return self._channel

    def get_id(self) -> int:
        """Returns the league ID."""
        return self._league_id

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

    def get_pickorder(self) -> list:
        """Returns the pick order."""
        return self._pickorder

    def get_phase(self) -> int:
        """Returns the current phase."""
        return self._phase

    def get_replay_channel(self) -> int:
        """Returns the Discord channel for the replays of this league."""
        return self._replay_channel

    def get_user(self, name) -> Union[DraftParticipant, bool]:
        """Returns the DraftParticipant of the given name."""
        for p in self._participants:
            if p.get_name().lower() == name.lower():
                return p
        else:
            return False

    def get_start_points(self) -> int:
        """Returns the starting points per player of the league."""
        return self._points_per_participant

    def get_start_timer(self) -> int:
        """Returns league timer starter."""
        return self._timer_start

    def next_phase(self):
        """Increments the phase by 1."""
        self._phase += 1

    def next_pick(self) -> str:
        """Moves the draft to the next pick. Moves draft to phase 2 if draft is over. Returns message to be sent."""
        if not self._pickorder:
            return "No pick order set."
        if self._picking[0] >= len(self._pickorder) - 1:
            self.next_phase()
            return "The draft has been completed."

        old_picker = self._pickorder[self._picking[0]]
        minutes = (datetime.datetime.now() - self._picking[1]).total_seconds() / 60
        old_picker.add_time_to_timer(minutes, remove=True)  # remove = True means remove time

        self._picking[0] += 1
        self._picking[1] = datetime.datetime.now().replace(microsecond=0)

        current_picker = self._pickorder[self._picking[0]]
        current_picker.add_time_to_timer(self._increment)  # add 3 hours to user's timer

        return "Now picking: <@{}>. Deadline: {} ({} minutes)".format(
            self._pickorder[self._picking[0]].get_discord(),
            (self._picking[1] + current_picker.get_timer()).replace(microsecond=0),
            round(current_picker.get_timer().total_seconds() / 60))

    def save(self):
        """Pickles and saves the league in a text file."""
        with open('files/league.txt', 'wb+') as file:
            pickle.dump(self, file)
            file.close()

    def set_increment(self, s: int):
        """Changes the increment for the drafting phase."""
        self._increment = s / 60

    def set_phase(self, phase: int):
        """Sets the phase of the draft. DEBUG ONLY."""
        self._phase = phase

    def set_pick_order(self):
        """Sets the pick order for the draft."""
        self._pickorder = 6 * (self._participants + self._participants[::-1])
        self._picking = [0, datetime.datetime.now().replace(microsecond=0)]

    def set_replay_channel(self, channel: int):
        """Sets the replay channel for the draft."""
        self._replay_channel = channel

    def shuffle(self):
        """Shuffles the order of the participants."""
        if self._phase == 0:
            random.shuffle(self._participants)
