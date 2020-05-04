from aenum import Enum, NoAlias


class Tier(Enum):
    """Reference for tier values."""
    _settings_ = NoAlias
    T1 = 180
    T2 = 120
    T3 = 100
    T4 = 60
    T5 = 40

    MT1 = 40
    MT2 = 0
    MT3 = -40
