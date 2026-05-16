#!/usr/bin/env python3
"""buddy fight: simulate a turn-based battle vs a wild buddy, apply rewards,
emit a round-by-round JSON log for Claude to narrate."""
import sys, os, json, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
from data import DROP_CHANCE_ON_WIN

# Each stat is a fighting style.
MOVES = {
    "STRIKE":      {"stat": "debugging", "flavor": "a precise, reliable hit"},
    "CHAOS_BLAST": {"stat": "chaos",     "flavor": "a wild, unpredictable blast"},
    "GUARD":       {"stat": "wisdom",    "flavor": "a defensive stance + counter"},
    "TAUNT":       {"stat": "snark",     "flavor": "a morale-crushing taunt"},
}
MAX_ROUNDS = 10


def gen_wild(player_level):
    lvl = max(1, player_level + random.randint(-2, 2))
    wp = core.gen_pet({"next_id": 0}, core.random_rng())
    wp["id"] = "wild"
    wp["level"] = lvl
    for _ in range(2, lvl + 1):
        core.grow_stats(wp, random.Random())
    return wp


def hp_max(pet):
    return 50 + core.total_stats(pet)["patience"] + pet["level"] * 8


def pick_move(st, rng):
    weights = [("STRIKE", st["debugging"]), ("CHAOS_BLAST", st["chaos"]),
               ("GUARD", st["wisdom"]), ("TAUNT", st["snark"])]
    total = sum(w for _, w in weights) or 1
    r = rng.random() * total
    acc = 0
    for name, w in weights:
        acc += w
        if r <= acc:
            return name
    return weights[-1][0]


def simulate(player, wild):
    rng = random.Random()
    stats = {"player": core.total_stats(player), "wild": core.total_stats(wild)}
    pets = {"player": player, "wild": wild}
    hp = {"player": hp_max(player), "wild": hp_max(wild)}
    hpmax = dict(hp)
    fx = {"player": {"guard": False, "morale": 1.0},
          "wild": {"guard": False, "morale": 1.0}}
    rounds = []

    def initiative(side):
        s = stats[side]
        return s["debugging"] + s["chaos"] + pets[side]["level"]

    def act(actor, target, rnum):
        a_st, d_st = stats[actor], stats[target]
        move = pick_move(a_st, rng)
        entry = {"n": rnum, "actor": actor, "actor_name": pets[actor]["name"],
                 "move": move, "hit": True, "damage": 0, "counter": 0, "note": ""}

        if move == "GUARD":
            fx[actor]["guard"] = True
            entry["note"] = "braces, ready to counter"
            rounds.append(entry)
            return

        stat_name = MOVES[move]["stat"]
        # hit rolls
        if move == "STRIKE" and rng.random() > 0.95:
            entry["hit"] = False; entry["note"] = "missed"
            rounds.append(entry); return
        if move == "CHAOS_BLAST" and rng.random() > 0.70:
            entry["hit"] = False; entry["note"] = "whiffed wildly"
            rounds.append(entry); return

        if move == "STRIKE":
            base = a_st["debugging"] * 0.45 * rng.uniform(0.85, 1.15)
        elif move == "CHAOS_BLAST":
            base = a_st["chaos"] * 0.65 * rng.uniform(0.30, 1.80)
        else:  # TAUNT
            base = a_st["snark"] * 0.18

        base *= fx[actor]["morale"]
        fx[actor]["morale"] = 1.0
        base *= (1 - min(0.40, d_st["wisdom"] / 400.0))  # wisdom passive

        if fx[target]["guard"]:
            base *= (1 - min(0.60, d_st["wisdom"] / 200.0))
            fx[target]["guard"] = False
            counter = max(1, round(d_st["wisdom"] * 0.30))
            entry["counter"] = counter
            hp[actor] -= counter
            entry["note"] = "blocked + countered"

        dmg = max(1, round(base))
        entry["damage"] = dmg
        hp[target] -= dmg
        if move == "TAUNT":
            fx[target]["morale"] = 1 - min(0.50, a_st["snark"] / 250.0)
            if not entry["note"]:
                entry["note"] = "morale shaken"
        rounds.append(entry)

    for rnum in range(1, MAX_ROUNDS + 1):
        order = sorted(["player", "wild"], key=initiative, reverse=True)
        for actor in order:
            if hp["player"] <= 0 or hp["wild"] <= 0:
                break
            target = "wild" if actor == "player" else "player"
            act(actor, target, rnum)
            rounds[-1]["player_hp"] = round(max(0, hp["player"]))
            rounds[-1]["wild_hp"] = round(max(0, hp["wild"]))
        # end-of-round patience regen
        for side in ("player", "wild"):
            if hp[side] > 0:
                hp[side] = min(hpmax[side], hp[side] + stats[side]["patience"] * 0.04)
        if hp["player"] <= 0 or hp["wild"] <= 0:
            break

    if hp["wild"] <= 0 and hp["player"] > 0:
        winner = "player"
    elif hp["player"] <= 0 and hp["wild"] > 0:
        winner = "wild"
    else:
        # timeout: higher HP fraction wins, player wins ties
        pf = hp["player"] / hpmax["player"]
        wf = hp["wild"] / hpmax["wild"]
        winner = "wild" if wf > pf else "player"

    return rounds, winner, hpmax


def main():
    sv = core.load()
    core.ensure_first_pet(sv)
    player = core.active_pet(sv)
    wild = gen_wild(player["level"])

    rounds, winner, hpmax = simulate(player, wild)
    result = "win" if winner == "player" else "loss"

    if result == "win":
        bonus = 4000 + wild["level"] * 3500
    else:
        bonus = 800 + wild["level"] * 600
    events = core.apply_xp(sv, player, bonus)

    win_drop = None
    if result == "win":
        player["wins"] = player.get("wins", 0) + 1
        if random.random() < DROP_CHANCE_ON_WIN:
            win_drop = core.make_drop(sv, random.Random())
            sv["inventory"].append(win_drop)
    else:
        player["losses"] = player.get("losses", 0) + 1

    core.save(sv)

    out = {
        "player": {
            "name": player["name"], "species": player["species"],
            "level_before": player["level"] - sum(1 for e in events if e["type"] == "levelup"),
            "level": player["level"], "color": core.color_for_level(player["level"]),
            "hp_max": hpmax["player"], "stats": core.total_stats(player),
            "eyes": player["eyes"],
        },
        "wild": {
            "name": wild["name"], "species": wild["species"], "level": wild["level"],
            "hp_max": hpmax["wild"], "stats": core.total_stats(wild), "eyes": wild["eyes"],
        },
        "rounds": rounds,
        "winner": winner,
        "result": result,
        "rewards": {
            "xp": bonus,
            "levelups": [e for e in events if e["type"] == "levelup"],
            "level_drops": [e["drop"] for e in events if e["type"] == "drop"],
            "win_drop": win_drop,
        },
        "pet_after": {"level": player["level"], "xp": player["xp"],
                      "wins": player.get("wins", 0), "losses": player.get("losses", 0)},
        "move_legend": MOVES,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
