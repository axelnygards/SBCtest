"""Known FC 27 SBCs, each with its source. Requirements are copied from the cited pages
(retrieved 2026-10-01); verify in game, EA changes SBCs often.

kind "puzzle":      traditional squad SBC (chemistry, ratings, leagues, nations)
kind "streamlined": FC 27 Item Score SBC (target score, optional minimum OVR per card)
"""
from ..solver.types import Op, ReqType as T

# FUT nation / league ids (from EA's ratings database)
ITALY, BELGIUM, NORWAY, PORTUGAL, NETHERLANDS, GERMANY, ENGLAND, SPAIN = 27, 7, 36, 38, 34, 21, 14, 45

DEXERTO_LN = "https://www.dexerto.com/wikis/ea-fc-27/how-to-complete-league--nation-advanced-sbcs/"
FUTMIND_MM = ("https://futmind.com/articles/18405/"
              "fc-27-marquee-matchups-sbc-guide-complete-every-challenge-for-big-rewards")
ALLTHINGS = "https://allthings.how/fc-27-streamlined-sbcs-how-the-item-score-system-works/"


def r(type_, value, op=Op.MIN, attr=None, values=(), label=""):
    return {"type": type_.value, "value": value, "op": op.value, "attr": attr,
            "values": list(values), "label": label}


GOLD_ONLY = r(T.COUNT, 11, Op.EXACT, "quality", ["gold"], "Spelarnivå: exakt guld")
NO_BRONZE = r(T.COUNT, 0, Op.MAX, "quality", ["bronze"], "Spelarkvalitet: min. silver")

PRESETS = [
    # --- League & Nation Advanced (foundations, puzzle) ---------------------------------
    {"id": "ln-adv-1", "kind": "puzzle", "group": "League & Nation Advanced",
     "name": "3 Leagues & 2 Nations", "formation": "4-4-2", "source": DEXERTO_LN, "expires": None,
     "requirements": [
         r(T.DISTINCT, 3, Op.EXACT, "league", label="Ligor: exakt 3"),
         r(T.DISTINCT, 2, Op.EXACT, "nation", label="Nationer: exakt 2"),
         r(T.SAME, 6, Op.MAX, "league", label="Samma liga: max 6"),
         r(T.SAME, 6, Op.MAX, "nation", label="Samma nation: max 6"),
         GOLD_ONLY, r(T.TEAM_CHEM, 30, label="Chemistry: min 30")]},
    {"id": "ln-adv-2", "kind": "puzzle", "group": "League & Nation Advanced",
     "name": "4 Leagues & 5 Nations", "formation": "4-4-2", "source": DEXERTO_LN, "expires": None,
     "requirements": [
         r(T.DISTINCT, 4, Op.EXACT, "league", label="Ligor: exakt 4"),
         r(T.DISTINCT, 5, Op.EXACT, "nation", label="Nationer: exakt 5"),
         r(T.SAME, 4, Op.MAX, "league", label="Samma liga: max 4"),
         r(T.SAME, 3, Op.MAX, "nation", label="Samma nation: max 3"),
         r(T.TEAM_RATING, 78, label="Lagbetyg: min 78"), r(T.TEAM_CHEM, 25, label="Chemistry: min 25")]},
    {"id": "ln-adv-3", "kind": "puzzle", "group": "League & Nation Advanced",
     "name": "5 Leagues & 6 Nations", "formation": "4-4-2", "source": DEXERTO_LN, "expires": None,
     "requirements": [
         r(T.DISTINCT, 5, Op.EXACT, "league", label="Ligor: exakt 5"),
         r(T.DISTINCT, 6, Op.EXACT, "nation", label="Nationer: exakt 6"),
         r(T.SAME, 2, Op.MAX, "club", label="Samma klubb: max 2"),
         r(T.TEAM_RATING, 81, label="Lagbetyg: min 81"), r(T.TEAM_CHEM, 25, label="Chemistry: min 25")]},
    # --- Marquee Matchups (weekly, puzzle) ------------------------------------------------
    {"id": "mm-ita-bel", "kind": "puzzle", "group": "Marquee Matchups", "name": "Italy v Belgium",
     "formation": "4-4-2", "source": FUTMIND_MM, "expires": "2026-10-01T18:00:00Z",
     "requirements": [
         r(T.COUNT, 1, Op.MIN, "nation", [ITALY, BELGIUM], "Min. 1 spelare Italien eller Belgien"),
         r(T.DISTINCT, 3, Op.MIN, "club", label="Klubbar i truppen: min 3"),
         r(T.COUNT, 3, Op.MIN, "quality", ["silver"], "Min. 3 silverspelare"),
         r(T.TEAM_CHEM, 14, label="Chemistry: min 14")]},
    {"id": "mm-nor-por", "kind": "puzzle", "group": "Marquee Matchups", "name": "Norway v Portugal",
     "formation": "4-4-2", "source": FUTMIND_MM, "expires": "2026-10-01T18:00:00Z",
     "requirements": [
         r(T.COUNT, 1, Op.MIN, "nation", [NORWAY, PORTUGAL], "Min. 1 spelare Norge eller Portugal"),
         r(T.SAME, 3, Op.MIN, "club", label="Samma klubb: min 3"),
         r(T.DISTINCT, 5, Op.MAX, "league", label="Ligor i truppen: max 5"),
         r(T.COUNT, 2, Op.MIN, "quality", ["gold"], "Min. 2 guldspelare"), NO_BRONZE,
         r(T.TEAM_CHEM, 18, label="Chemistry: min 18")]},
    {"id": "mm-ned-ger", "kind": "puzzle", "group": "Marquee Matchups", "name": "Netherlands v Germany",
     "formation": "4-4-2", "source": FUTMIND_MM, "expires": "2026-10-01T18:00:00Z",
     "requirements": [
         r(T.COUNT, 2, Op.MIN, "nation", [NETHERLANDS, GERMANY], "Min. 2 spelare Nederländerna eller Tyskland"),
         r(T.SAME, 2, Op.MAX, "club", label="Samma klubb: max 2"),
         r(T.SAME, 4, Op.MIN, "league", label="Samma liga: min 4"),
         r(T.COUNT, 2, Op.MIN, "quality", ["gold"], "Min. 2 guldspelare"), NO_BRONZE,
         r(T.TEAM_CHEM, 22, label="Chemistry: min 22")]},
    {"id": "mm-eng-esp", "kind": "puzzle", "group": "Marquee Matchups", "name": "England v Spain",
     "formation": "4-4-2", "source": FUTMIND_MM, "expires": "2026-10-01T18:00:00Z",
     "requirements": [
         r(T.COUNT, 2, Op.MIN, "nation", [ENGLAND, SPAIN], "Min. 2 spelare England eller Spanien"),
         r(T.SAME, 4, Op.MIN, "nation", label="Samma nation: min 4"),
         r(T.SAME, 3, Op.MAX, "club", label="Samma klubb: max 3"),
         r(T.DISTINCT, 5, Op.MAX, "league", label="Ligor i truppen: max 5"),
         r(T.TEAM_RATING, 75, label="Lagbetyg: min 75"), r(T.TEAM_CHEM, 26, label="Chemistry: min 26")]},
    # --- Streamlined (Item Score) ---------------------------------------------------------
    {"id": "st-83-upgrade", "kind": "streamlined", "group": "Upgrades", "name": "83+ Upgrade",
     "target": 2500, "min_ovr": 0, "source": ALLTHINGS, "expires": None},
    {"id": "st-otw-bouaddi", "kind": "streamlined", "group": "Players", "name": "Ones to Watch: Bouaddi",
     "target": 20000, "min_ovr": 0, "source": ALLTHINGS, "expires": None},
]
