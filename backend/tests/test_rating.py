import random

import pytest

from app.solver.rating import meets_rating, team_rating


@pytest.mark.parametrize("squad,expected", [
    ([84] * 11, 84),
    ([83] * 10 + [84], 83),
    ([85] * 2 + [84] * 7 + [83] * 2, 84),
    ([90] + [83] * 10, 84),
    ([86] * 3 + [82] * 8, 83),
    ([87] * 3 + [82] * 8, 84),
    ([75] * 11, 75),
    ([99] * 11, 99),
])
def test_known_squads(squad, expected):
    assert team_rating(squad) == expected


def test_integer_form_matches_formula():
    rng = random.Random(7)
    for _ in range(20000):
        n = rng.choice([11, 11, 11, 5, 7, 10])
        squad = [rng.randint(60, 95) for _ in range(n)]
        tr = team_rating(squad)
        for t in (tr - 1, tr, tr + 1):
            assert meets_rating(squad, t) == (tr >= t), (squad, t)
