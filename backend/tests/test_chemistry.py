from app.solver.evaluate import chemistry
from app.solver.formations import slots_for
from app.solver.types import CardKind

from .factory import card

F = slots_for("4-4-2")


def squad(**kw):
    return [card(i, 80, pos=(p,), **kw) for i, p in enumerate(F)]


def test_full_link_is_33():
    assert sum(chemistry(F, squad())) == 33


def test_all_different_is_0():
    cards = [card(i, 80, pos=(p,), nation=i, league=i, club=i) for i, p in enumerate(F)]
    assert sum(chemistry(F, cards)) == 0


def test_out_of_position_gets_zero_and_does_not_count():
    cards = squad()
    cards[10] = card(10, 80, pos=("GK",))  # striker slot, GK card
    chem = chemistry(F, cards)
    assert chem[10] == 0 and sum(chem) == 30


def test_thresholds():
    # 3 players share a league only -> +1 league each; 2 share a club -> +1 club
    cards = [card(i, 80, pos=(p,), nation=100 + i, league=50 + i, club=500 + i)
             for i, p in enumerate(F)]
    for i in (0, 1, 2):
        cards[i] = card(i, 80, pos=(F[i],), nation=100 + i, league=1, club=500 + i)
    cards[1] = card(1, 80, pos=(F[1],), nation=101, league=1, club=7)
    cards[2] = card(2, 80, pos=(F[2],), nation=102, league=1, club=7)
    chem = chemistry(F, cards)
    assert chem[:3] == [1, 2, 2]


def test_icon_rules_by_version():
    # icon + 1 same-nation player: fc26 icon counts 2 -> nation count 3 (+1); fc27 counts 1 -> 2 (+1)
    # icon + 4 same-nation players: fc26 -> 6 (+2), fc27 -> 5 (+2); with 3: fc26 5 (+2), fc27 4 (+1)
    cards = [card(i, 80, pos=(p,), nation=100 + i, league=50 + i, club=500 + i)
             for i, p in enumerate(F)]
    cards[0] = card(0, 90, pos=(F[0],), nation=1, league=2118, club=112658, kind=CardKind.ICON)
    for i in (1, 2, 3):
        cards[i] = card(i, 80, pos=(F[i],), nation=1, league=50 + i, club=500 + i)
    assert chemistry(F, cards, "fc26")[1] == 2
    assert chemistry(F, cards, "fc27")[1] == 1
    assert chemistry(F, cards)[0] == 3


def test_icon_adds_to_every_league():
    # 2 players in league 1 + icon -> league count 3 -> +1
    cards = [card(i, 80, pos=(p,), nation=100 + i, league=50 + i, club=500 + i)
             for i, p in enumerate(F)]
    cards[0] = card(0, 90, pos=(F[0],), nation=99, league=2118, club=112658, kind=CardKind.ICON)
    cards[1] = card(1, 80, pos=(F[1],), nation=101, league=1, club=501)
    cards[2] = card(2, 80, pos=(F[2],), nation=102, league=1, club=502)
    assert chemistry(F, cards)[1:3] == [1, 1]


def test_hero_league_weight_by_version():
    cards = [card(i, 80, pos=(p,), nation=100 + i, league=50 + i, club=500 + i)
             for i, p in enumerate(F)]
    cards[0] = card(0, 88, pos=(F[0],), nation=98, league=1, club=99999, kind=CardKind.HERO)
    cards[1] = card(1, 80, pos=(F[1],), nation=101, league=1, club=501)
    cards[2] = card(2, 80, pos=(F[2],), nation=102, league=1, club=502)
    # fc26 hero counts 2 in league -> 4 (+1); fc27 -> 3 (+1); drop one normal player:
    assert chemistry(F, cards, "fc26")[1] == 1 and chemistry(F, cards, "fc27")[1] == 1
    cards[2] = card(2, 80, pos=(F[2],), nation=102, league=77, club=502)
    assert chemistry(F, cards, "fc26")[1] == 1 and chemistry(F, cards, "fc27")[1] == 0
