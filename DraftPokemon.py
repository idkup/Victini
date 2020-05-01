from Tier import Tier


class DraftPokemon:
    """Represents a draftable Pokemon."""
    def __init__(self, name: str, tier: Tier):
        """Initializes the Pokemon."""
        self._name = name
        self._tier = tier
        self._kills = 0
        self._deaths = 0
        self._owner = None

    def __str__(self):
        """Behavior when stringified."""
        return self._name

    def add_kills(self, k: int):
        """Adds k to self._kills."""
        self._kills += k

    def add_deaths(self, d: int):
        """Adds d to self._deaths."""
        self._deaths += d

    def get_deaths(self) -> int:
        """Returns self._deaths."""
        return self._deaths

    def get_kills(self) -> int:
        """Returns self._kills."""
        return self._kills

    def get_tier(self) -> Tier:
        """Returns self._tier."""
        return self._tier

    def set_owner(self, owner=None):
        """Returns self._owner."""
        self._owner = owner
