"""Strict exact inputs for isolated synthetic analytical fixtures."""

from fractions import Fraction


def require_rational(value: Fraction, name: str, *, allow_zero: bool = False) -> None:
    if type(value) is not Fraction or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(
            f"{name} must be an exact {'nonnegative' if allow_zero else 'positive'} Fraction"
        )


def require_count(value: int, name: str, *, allow_zero: bool = False) -> None:
    if type(value) is not int or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be a {'nonnegative' if allow_zero else 'positive'} integer")


def require_tuple(value: object, name: str) -> None:
    if type(value) is not tuple:
        raise ValueError(f"{name} must be an immutable tuple")
