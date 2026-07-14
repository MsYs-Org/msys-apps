"""Bounded recursive-descent arithmetic parser used by Calculator.

This module deliberately never calls ``eval`` or ``exec``.  The accepted
language contains numeric literals, parentheses and seven arithmetic
operators only.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Final


MAX_EXPRESSION_LENGTH: Final = 256
MAX_TOKENS: Final = 128
MAX_MAGNITUDE: Final = 1e100
MAX_EXPONENT: Final = 100

_TOKEN = re.compile(
    r"\s*(?:(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)|"
    r"(?P<operator>\*\*|//|[+\-*/%()]))"
)


class CalculationError(ValueError):
    """The expression is invalid, unsafe, or outside calculator bounds."""


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    position: int


def _tokenise(expression: str) -> list[Token]:
    if not isinstance(expression, str):
        raise CalculationError("Expression must be text")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculationError("Expression is too long")
    source = expression.strip()
    if not source:
        raise CalculationError("Enter an expression")
    tokens: list[Token] = []
    position = 0
    while position < len(source):
        match = _TOKEN.match(source, position)
        if match is None:
            raise CalculationError(f"Unexpected character at position {position + 1}")
        kind = "number" if match.group("number") is not None else "operator"
        value = match.group(kind)
        tokens.append(Token(kind, value, match.start(kind)))
        if len(tokens) > MAX_TOKENS:
            raise CalculationError("Expression has too many tokens")
        position = match.end()
    tokens.append(Token("end", "", len(source)))
    return tokens


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def take(self, value: str | None = None) -> Token:
        token = self.current
        if value is not None and token.value != value:
            raise CalculationError(
                f"Expected {value!r} at position {token.position + 1}"
            )
        self.index += 1
        return token

    def parse(self) -> int | float:
        result = self.additive()
        if self.current.kind != "end":
            raise CalculationError(
                f"Unexpected token {self.current.value!r} at position "
                f"{self.current.position + 1}"
            )
        return result

    def additive(self) -> int | float:
        value = self.multiplicative()
        while self.current.value in {"+", "-"}:
            operator = self.take().value
            value = _apply(operator, value, self.multiplicative())
        return value

    def multiplicative(self) -> int | float:
        value = self.unary()
        while self.current.value in {"*", "/", "//", "%"}:
            operator = self.take().value
            value = _apply(operator, value, self.unary())
        return value

    def unary(self) -> int | float:
        if self.current.value in {"+", "-"}:
            operator = self.take().value
            value = self.unary()
            return _bounded(value if operator == "+" else -value)
        return self.power()

    def power(self) -> int | float:
        value = self.primary()
        if self.current.value == "**":
            self.take("**")
            value = _apply("**", value, self.unary())
        return value

    def primary(self) -> int | float:
        token = self.current
        if token.kind == "number":
            self.take()
            try:
                value: int | float = (
                    float(token.value)
                    if any(marker in token.value for marker in ".eE")
                    else int(token.value, 10)
                )
            except (OverflowError, ValueError) as exc:
                raise CalculationError("Invalid numeric literal") from exc
            return _bounded(value)
        if token.value == "(":
            self.take("(")
            value = self.additive()
            self.take(")")
            return value
        raise CalculationError(f"Expected a number at position {token.position + 1}")


def _bounded(value: int | float) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculationError("Result is not a real number")
    if isinstance(value, float) and not math.isfinite(value):
        raise CalculationError("Result is not finite")
    if abs(value) > MAX_MAGNITUDE:
        raise CalculationError("Result is too large")
    return value


def _power(left: int | float, right: int | float) -> int | float:
    if abs(right) > MAX_EXPONENT:
        raise CalculationError("Exponent is too large")
    if left == 0 and right < 0:
        raise CalculationError("Cannot raise zero to a negative power")
    if left < 0 and not float(right).is_integer():
        raise CalculationError("Result would not be a real number")
    if abs(left) > 1 and right > 0:
        if math.log10(abs(left)) * right > math.log10(MAX_MAGNITUDE):
            raise CalculationError("Result is too large")
    try:
        return _bounded(left**right)
    except (OverflowError, ZeroDivisionError) as exc:
        raise CalculationError("Power operation is outside supported bounds") from exc


def _apply(operator: str, left: int | float, right: int | float) -> int | float:
    try:
        if operator == "+":
            result = left + right
        elif operator == "-":
            result = left - right
        elif operator == "*":
            result = left * right
        elif operator == "/":
            result = left / right
        elif operator == "//":
            result = left // right
        elif operator == "%":
            result = left % right
        elif operator == "**":
            return _power(left, right)
        else:  # parser-owned invariant
            raise CalculationError(f"Unsupported operator: {operator}")
    except ZeroDivisionError as exc:
        raise CalculationError("Division by zero") from exc
    except OverflowError as exc:
        raise CalculationError("Result is outside supported bounds") from exc
    return _bounded(result)


def calculate(expression: str) -> int | float:
    """Parse and calculate one bounded arithmetic expression."""

    return _Parser(_tokenise(expression)).parse()


def format_result(value: int | float) -> str:
    value = _bounded(value)
    if isinstance(value, int):
        return str(value)
    if value == 0:
        return "0"
    if value.is_integer() and abs(value) < 1e16:
        return str(int(value))
    return format(value, ".12g")

