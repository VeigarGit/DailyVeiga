from __future__ import annotations

import unittest
from datetime import time

from dailyveiga.validation import (
    parse_time,
    parse_weekdays,
    validate_schedule,
    validate_timezone,
)


class ValidationTest(unittest.TestCase):
    def test_valid_values(self) -> None:
        self.assertEqual(parse_time("09:30"), time(9, 30))
        self.assertEqual(parse_weekdays("5,1,2,2"), (1, 2, 5))
        self.assertEqual(validate_timezone("America/Belem"), "America/Belem")
        validate_schedule(time(9), time(10))

    def test_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            parse_time("9h")
        with self.assertRaises(ValueError):
            parse_weekdays("0,8")
        with self.assertRaises(ValueError):
            validate_timezone("Planeta/Marte")
        with self.assertRaises(ValueError):
            validate_schedule(time(10), time(9))
