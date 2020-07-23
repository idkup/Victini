class DraftPokemon:
    """Represents a draftable Pokemon."""
    def __init__(self, name: str, cost: int, is_mega=False):
        """Initializes the Pokemon."""
        self._name = name
        self._cost = cost
        self._is_mega = is_mega
        self._kills = 0
        self._deaths = 0
        self._owner = None

    def __str__(self):
        """Behavior when stringified."""
        return self._name

    def add_deaths(self, d: int):
        """Adds d to self._deaths."""
        self._deaths += d

    def add_kills(self, k: int):
        """Adds k to self._kills."""
        self._kills += k

    def get_deaths(self) -> int:
        """Returns self._deaths."""
        return self._deaths

    def get_kills(self) -> int:
        """Returns self._kills."""
        return self._kills

    def get_cost(self) -> int:
        """Returns self._tier."""
        return self._cost

    def get_owner(self):
        """Returns self._owner.."""
        return self._owner

    def is_mega(self) -> bool:
        """Returns self._is_mega."""
        return self._is_mega

    def set_owner(self, owner):
        """Sets self._owner."""
        self._owner = owner
