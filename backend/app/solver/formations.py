"""Ultimate Team formations with EA's names, slot by slot.

Slot order: goalkeeper, then each line from right to left, defence to attack (the order the
pitch layout in the frontend expects). Names follow the game, including the numbered
variants: 4-2-3-1 has three CAMs, 4-2-3-1(2) has RM/CAM/LM; 4-1-2-1-2 is wide (RM/LM),
4-1-2-1-2(2) narrow (CM/CM).

Verified against FC 27 SBC pages (FUTBIN, 2026-10-01) for the formations used by the
current presets: 3-4-3, 4-1-4-1, 3-1-4-2, 4-4-2, 4-5-1, 5-3-2, 5-2-1-2. The other slot
lists follow the game's formations as of FC 24-26 and should be checked against FC 27.
"""

D4 = ("RB", "CB", "CB", "LB")
D3 = ("CB", "CB", "CB")
D5 = ("RWB", "CB", "CB", "CB", "LWB")

FORMATIONS: dict[str, tuple[str, ...]] = {
    # back four
    "4-4-2": ("GK", *D4, "RM", "CM", "CM", "LM", "ST", "ST"),
    "4-4-2(2)": ("GK", *D4, "RM", "CDM", "CDM", "LM", "ST", "ST"),
    "4-1-4-1": ("GK", *D4, "CDM", "RM", "CM", "CM", "LM", "ST"),
    "4-5-1": ("GK", *D4, "RM", "CM", "LM", "CAM", "CAM", "ST"),
    "4-5-1(2)": ("GK", *D4, "RM", "CM", "CM", "CM", "LM", "ST"),
    "4-3-3": ("GK", *D4, "CM", "CM", "CM", "RW", "ST", "LW"),
    "4-3-3(2)": ("GK", *D4, "CDM", "CM", "CM", "RW", "ST", "LW"),
    "4-3-3(3)": ("GK", *D4, "CDM", "CDM", "CM", "RW", "ST", "LW"),
    "4-3-3(4)": ("GK", *D4, "CM", "CM", "CAM", "RW", "ST", "LW"),
    "4-2-3-1": ("GK", *D4, "CDM", "CDM", "CAM", "CAM", "CAM", "ST"),
    "4-2-3-1(2)": ("GK", *D4, "CDM", "CDM", "RM", "CAM", "LM", "ST"),
    "4-2-2-2": ("GK", *D4, "CDM", "CDM", "CAM", "CAM", "ST", "ST"),
    "4-2-1-3": ("GK", *D4, "CDM", "CDM", "CAM", "RW", "ST", "LW"),
    "4-2-4": ("GK", *D4, "CM", "CM", "RW", "ST", "ST", "LW"),
    "4-1-2-1-2": ("GK", *D4, "CDM", "RM", "LM", "CAM", "ST", "ST"),
    "4-1-2-1-2(2)": ("GK", *D4, "CDM", "CM", "CM", "CAM", "ST", "ST"),
    "4-1-3-2": ("GK", *D4, "CDM", "RM", "CM", "LM", "ST", "ST"),
    "4-3-1-2": ("GK", *D4, "CM", "CM", "CM", "CAM", "ST", "ST"),
    # back three
    "3-4-3": ("GK", *D3, "RM", "CM", "CM", "LM", "RW", "ST", "LW"),
    "3-1-4-2": ("GK", *D3, "CDM", "RM", "CM", "CM", "LM", "ST", "ST"),
    "3-4-1-2": ("GK", *D3, "RM", "CM", "CM", "LM", "CAM", "ST", "ST"),
    "3-5-2": ("GK", *D3, "CDM", "CDM", "RM", "LM", "CAM", "ST", "ST"),
    # back five
    "5-2-1-2": ("GK", *D5, "CM", "CM", "CAM", "ST", "ST"),
    "5-3-2": ("GK", *D5, "CM", "CDM", "CM", "ST", "ST"),
    "5-2-3": ("GK", *D5, "CM", "CM", "RW", "ST", "LW"),
    "5-4-1": ("GK", *D5, "RM", "CM", "CM", "LM", "ST"),
}


def slots_for(formation: str) -> tuple[str, ...]:
    try:
        return FORMATIONS[formation]
    except KeyError:
        raise ValueError(f"unknown formation {formation!r}; known: {sorted(FORMATIONS)}")
