from DraftParticipant import DraftParticipant
from DraftPokemon import DraftPokemon
from Tier import Tier

TapuKoko = DraftPokemon("Tapu Koko", Tier.T1)
Victini = DraftPokemon("Victini", Tier.T1)
bob = DraftParticipant(235325, "bob")
bob.set_mon(TapuKoko)
bob.set_mon(Victini)
print(bob)
bob.remove_mon(TapuKoko)
print(bob)
print(TapuKoko)