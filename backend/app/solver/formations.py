FORMATIONS: dict[str, tuple[str, ...]] = {
    "4-4-2": ("GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"),
    "4-3-3": ("GK", "RB", "CB", "CB", "LB", "CM", "CM", "CM", "RW", "ST", "LW"),
    "4-3-3(4)": ("GK", "RB", "CB", "CB", "LB", "CM", "CM", "CAM", "RW", "ST", "LW"),
    "4-2-3-1": ("GK", "RB", "CB", "CB", "LB", "CDM", "CDM", "CAM", "RM", "LM", "ST"),
    "4-1-2-1-2": ("GK", "RB", "CB", "CB", "LB", "CDM", "CM", "CM", "CAM", "ST", "ST"),
    "4-2-2-2": ("GK", "RB", "CB", "CB", "LB", "CDM", "CDM", "CAM", "CAM", "ST", "ST"),
    "3-5-2": ("GK", "CB", "CB", "CB", "CDM", "CDM", "RM", "LM", "CAM", "ST", "ST"),
    "3-4-3": ("GK", "CB", "CB", "CB", "RM", "CM", "CM", "LM", "RW", "ST", "LW"),
    "5-2-1-2": ("GK", "RWB", "CB", "CB", "CB", "LWB", "CM", "CM", "CAM", "ST", "ST"),
    "5-3-2": ("GK", "RWB", "CB", "CB", "CB", "LWB", "CM", "CM", "CM", "ST", "ST"),
}


def slots_for(formation: str) -> tuple[str, ...]:
    try:
        return FORMATIONS[formation]
    except KeyError:
        raise ValueError(f"unknown formation {formation!r}; known: {sorted(FORMATIONS)}")
