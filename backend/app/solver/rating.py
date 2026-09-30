"""Team rating formula. See docs/rating.md."""
from fractions import Fraction


def team_rating(ratings: list[int]) -> int:
    n = len(ratings)
    if n == 0:
        return 0
    s = sum(ratings)
    avg = Fraction(s, n)
    excess = sum((r - avg for r in ratings if r > avg), Fraction(0))
    total = s + excess
    rounded = int(total + Fraction(1, 2))  # round half up (total >= 0)
    return rounded // n


def meets_rating(ratings: list[int], target: int) -> bool:
    """Integer form used by the CP-SAT model; must agree with team_rating()."""
    n = len(ratings)
    s = sum(ratings)
    lhs = n * s + sum(max(n * r - s, 0) for r in ratings)
    return lhs >= n * n * target - n // 2
