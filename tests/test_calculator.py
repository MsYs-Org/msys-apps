from __future__ import annotations

import unittest

from msys_apps.calculator import CalculationError, calculate, format_result


class CalculatorParserTests(unittest.TestCase):
    def test_precedence_parentheses_and_right_associative_power(self) -> None:
        self.assertEqual(calculate("2 + 3 * 4"), 14)
        self.assertEqual(calculate("(2 + 3) * 4"), 20)
        self.assertEqual(calculate("2**3**2"), 512)

    def test_unary_power_and_negative_exponent(self) -> None:
        self.assertEqual(calculate("-2**2"), -4)
        self.assertEqual(calculate("(-2)**2"), 4)
        self.assertEqual(calculate("2**-2"), 0.25)

    def test_all_supported_binary_operators(self) -> None:
        self.assertEqual(calculate("17 // 5"), 3)
        self.assertEqual(calculate("17 % 5"), 2)
        self.assertEqual(calculate("7 / 2"), 3.5)
        self.assertEqual(calculate("8 - 3 + 2"), 7)

    def test_decimal_and_scientific_literals(self) -> None:
        self.assertAlmostEqual(calculate(".5 + 1.5e1"), 15.5)
        self.assertEqual(format_result(calculate("10 / 4")), "2.5")
        self.assertEqual(format_result(-0.0), "0")

    def test_code_names_calls_and_containers_are_rejected(self) -> None:
        for expression in (
            "__import__('os')",
            "abs(1)",
            "name + 1",
            "[1, 2]",
            "1; 2",
            "{1: 2}",
        ):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError):
                    calculate(expression)

    def test_division_zero_and_non_real_power_are_typed_errors(self) -> None:
        for expression in ("1 / 0", "1 // 0", "1 % 0", "(-1)**.5", "0**-1"):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError):
                    calculate(expression)

    def test_resource_bounds_reject_large_inputs_and_results(self) -> None:
        for expression in ("1" * 257, "10**101", "100**100", "1e100 * 10"):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError):
                    calculate(expression)

    def test_syntax_errors_have_no_partial_result(self) -> None:
        for expression in ("", "1 2", "(1 + 2", "1 +", ")1(", "1..2"):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError):
                    calculate(expression)


if __name__ == "__main__":
    unittest.main()

