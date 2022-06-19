from BattleParticipant import BattleParticipant
from BattlePokemon import BattlePokemon
from ParsedBattle import ParsedBattle
import json
import requests

def parse_replay(msg):
    url = msg + ".json"

    replay_file = requests.get(url).content.decode("UTF-8")
    replay_json = json.loads(replay_file)

    p1 = BattleParticipant(replay_json["p1"])
    p2 = BattleParticipant(replay_json["p2"])
    winner = None

    log = replay_json["log"].split('\n')

    line = 0
    damaging_weather = None
    for l in log:
        if '|poke|' in l:
            if '|p1|' in l:
                try:
                    p1.team.append(BattlePokemon(l[9:l.index(',')]))
                except ValueError:
                    p = l[9:l.index('|', 9)]
                    if p == "Silvally-*":
                        p = "Silvally"
                    elif p == "Arceus-*":
                        p = "Arceus"
                    elif p == "Urshifu-*":
                        p = "Urshifu"
                    p1.team.append(BattlePokemon(p))
            elif '|p2|' in l:
                try:
                    p2.team.append(BattlePokemon(l[9:l.index(',')]))
                except ValueError:
                    p = l[9:l.index('|', 9)]
                    if p == "Silvally-*":
                        p = "Silvally"
                    elif p == "Arceus-*":
                        p = "Arceus"
                    p2.team.append(BattlePokemon(p))
        elif '|switch|' in l or '|drag|' in l:
            ls = l.split('|')
            player = int(ls[2][1])
            nickname = ls[2][5:]
            species = ls[3].split(',')[0]
            pkmn = None
            if player == 1:
                for p in p1.team:
                    if p.species == species:
                        p.nickname = nickname
                        pkmn = p
                        break
            elif player == 2:
                for p in p2.team:
                    if p.species == species:
                        p.nickname = nickname
                        pkmn = p
                        break
            i = line + 1
            while log[i] != '|' and "|move|" not in log[i]:
                if "fnt|[from] Stealth Rock" in log[i]:
                    if player == 1:
                        p1.rocks_set.indirect_kills += 1
                    elif player == 2:
                        p2.rocks_set.indirect_kills += 1
                elif "fnt|[from] Spikes" in log[i]:
                    if player == 1:
                        p1.spikes_set.indirect_kills += 1
                    elif player == 2:
                        p2.spikes_set.indirect_kills += 1
                elif "|-status|" in log[i]:
                    if player == 1:
                        pkmn.status_induced = p1.tspikes_set
                    elif player == 2:
                        pkmn.status_induced = p2.tspikes_set
                elif "|-weather|Sandstorm|" in log[i] or "|-weather|Hail|" in log[i]:
                    damaging_weather = (pkmn, player)

                i += 1

        elif '|move|' in l:
            ls = l.split('|')
            attacker_name = ls[2][5:]
            attacking_player = int(ls[2][1])
            defender_name = ls[4][5:]

            attacker = None
            defender = None
            if attacking_player == 1:
                for p in p1.team:
                    if p.nickname == attacker_name:
                        attacker = p
                        break
                else:
                    raise Exception(f"Attacker not found: {l}")
                for p in p2.team:
                    if p.nickname == defender_name:
                        defender = p
                        break
            elif attacking_player == 2:
                for p in p2.team:
                    if p.nickname == attacker_name:
                        attacker = p
                        break
                else:
                    raise Exception(f"Attacker not found: {l}")
                for p in p1.team:
                    if p.nickname == defender_name:
                        defender = p
                        break

            if ls[3] == "Stealth Rock":
                if attacking_player == 1:
                    p2.rocks_set = attacker
                elif attacking_player == 2:
                    p1.rocks_set = attacker

            elif ls[3] == "Spikes":
                if attacking_player == 1:
                    p2.spikes_set = attacker
                elif attacking_player == 2:
                    p1.spikes_set = attacker

            elif ls[3] == "Toxic Spikes":
                if attacking_player == 1:
                    p2.tspikes_set = attacker
                elif attacking_player == 2:
                    p1.tspikes_set = attacker
            elif ls[3] == "Hail" or ls[3] == "Sandstorm":
                damaging_weather = (attacker, attacking_player)
            elif ls[3] == "Leech Seed":
                try:
                    defender.seeded = attacker
                except AttributeError:
                    pass

            i = line + 1
            while log[i] != '|' and "|move|" not in log[i]:
                if "|0 fnt" in log[i] and not ("|[from] recoil" in log[i] or "|[from] Recoil" in log[i] or "|[from] item: " in log[i]):
                    attacker.direct_kills += 1
                elif "|-status|" in log[i] and "move: Rest" not in log[i] or "|-start|" in log[i] and "Substitute" not in log[i]:
                    try:
                        defender.status_induced = attacker
                    except AttributeError:
                        pass
                i += 1
        elif "|detailschange|" in l:
            ls = l.split('|')
            player = int(ls[2][1])
            nickname = ls[2][5:]
            new_species = ls[3].split(',')[0]
            if player == 1:
                for p in p1.team:
                    if p.nickname == nickname:
                        p.species = new_species
                        break
            elif player == 2:
                for p in p2.team:
                    if p.nickname == nickname:
                        p.species = new_species
                        break
        elif "0 fnt" in l:
            ls = l.split('|')
            player = int(ls[2][1])
            nickname = ls[2][5:]
            if player == 1:
                for p in p1.team:
                    if p.nickname == nickname:
                        p.ko = True
                        break
            elif player == 2:
                for p in p2.team:
                    if p.nickname == nickname:
                        p.ko = True
                        break
            if "0 fnt|[from] psn" in l or "0 fnt|[from] brn" in l or "0 fnt|[from] confusion" in l:
                if player == 1:
                    for p in p1.team:
                        if p.nickname == nickname:
                            if p.status_induced:
                                p.status_induced.indirect_kills += 1
                            break
                elif player == 2:
                    for p in p2.team:
                        if p.nickname == nickname:
                            if p.status_induced:
                                p.status_induced.indirect_kills += 1
                            break
            elif "0 fnt|[from] Sandstorm" in l or "0 fnt|[from] Hail" in l:
                if player != damaging_weather[1]:
                    damaging_weather[0].indirect_kills += 1
            elif "0 fnt|[from] Leech Seed|" in l:
                ls = l.split('|')
                nickname = ls[2][5:]
                if player == 1:
                    for p in p1.team:
                        if p.nickname == nickname:
                            if p.seeded:
                                p.seeded.indirect_kills += 1
                            break
                elif player == 2:
                    for p in p2.team:
                        if p.nickname == nickname:
                            if p.seeded:
                                p.seeded.indirect_kills += 1
                            break

        elif "|faint|" in l:
            ls = l.split('|')
            player = int(ls[2][1])
            nickname = ls[2][5:]
            if player == 1:
                for p in p1.team:
                    if p.nickname == nickname:
                        p.ko = True
                        break
            elif player == 2:
                for p in p2.team:
                    if p.nickname == nickname:
                        p.ko = True
                        break
        elif "|win|" in l:
            winner = l.split('|')[-1]
        line += 1
    battle = ParsedBattle()
    if winner == p1.psname:
        battle.winner = p1
        battle.loser = p2
    elif winner == p2.psname:
        battle.winner = p2
        battle.loser = p1
    return battle
