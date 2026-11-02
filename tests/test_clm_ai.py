"""Offline tests for CLM-1's declarative custom-command validator."""
import unittest

from clm_ai import MAX_STEPS, MAX_TOTAL_MS, step_to_device_command, validate_definition


def make_step(action, **values):
    step = {
        "action": action,
        "led": None,
        "state": None,
        "color": None,
        "frequency_hz": None,
        "duration_ms": None,
        "strength": None,
        "count": None,
        "interval_ms": None,
    }
    step.update(values)
    return step


def make_definition(*steps, name="test_macro", description="A test macro"):
    return {"name": name, "description": description, "steps": list(steps)}


class ValidateDefinitionTests(unittest.TestCase):
    def test_valid_led_step_is_normalized(self):
        result = validate_definition(make_definition(
            make_step("led", led=1, state="on"),
            description="  A test macro  ",
        ))
        self.assertEqual(result["description"], "A test macro")
        self.assertEqual(result["steps"][0]["led"], 1)
        self.assertEqual(result["estimated_ms"], 80)

    def test_valid_color_step(self):
        result = validate_definition(make_definition(make_step("color", color="MAGENTA")))
        self.assertEqual(result["steps"][0]["color"], "MAGENTA")

    def test_valid_beep_step(self):
        result = validate_definition(make_definition(
            make_step("beep", frequency_hz=440, duration_ms=250)
        ))
        self.assertEqual(result["estimated_ms"], 290)

    def test_invalid_command_name_is_rejected(self):
        for name in ("A", "bad-name", "1macro", "contains spaces", "x" * 25):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_definition(make_definition(make_step("wait", duration_ms=100), name=name))

    def test_empty_or_too_many_steps_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_definition(make_definition())
        too_many = [make_step("wait", duration_ms=30) for _ in range(MAX_STEPS + 1)]
        with self.assertRaises(ValueError):
            validate_definition(make_definition(*too_many))

    def test_total_duration_limit_is_enforced(self):
        steps = [make_step("wait", duration_ms=1500) for _ in range(14)]
        with self.assertRaises(ValueError):
            validate_definition(make_definition(*steps))
        self.assertEqual(MAX_TOTAL_MS, 20_000)

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_definition(make_definition(make_step("shell", duration_ms=100)))

    def test_missing_or_extra_step_fields_are_rejected(self):
        missing = make_step("wait", duration_ms=100)
        del missing["duration_ms"]
        with self.assertRaises(ValueError):
            validate_definition(make_definition(missing))

        extra = make_step("wait", duration_ms=100)
        extra["command"] = "anything"
        with self.assertRaises(ValueError):
            validate_definition(make_definition(extra))

    def test_unused_fields_must_be_null(self):
        with self.assertRaises(ValueError):
            validate_definition(make_definition(
                make_step("beep", frequency_hz=440, duration_ms=200, led=1)
            ))

    def test_boolean_is_not_accepted_as_an_integer_led(self):
        with self.assertRaises(ValueError):
            validate_definition(make_definition(
                make_step("led", led=True, state="on")
            ))

    def test_invalid_ranges_and_colors_are_rejected(self):
        invalid_steps = [
            make_step("led", led=4, state="on"),
            make_step("beep", frequency_hz=100, duration_ms=200),
            make_step("motor", strength=200, duration_ms=200),
            make_step("color", color="ORANGE"),
            make_step("blink", led=1, count=7, interval_ms=100),
        ]
        for step in invalid_steps:
            with self.subTest(step=step), self.assertRaises(ValueError):
                validate_definition(make_definition(step))

    def test_step_translation(self):
        led_command, led_delay = step_to_device_command(
            make_step("led", led=2, state="on")
        )
        self.assertEqual(led_command, "LED 2 ON")
        self.assertAlmostEqual(led_delay, 0.08)

        wait_command, wait_delay = step_to_device_command(
            make_step("wait", duration_ms=300)
        )
        self.assertIsNone(wait_command)
        self.assertAlmostEqual(wait_delay, 0.3)


if __name__ == "__main__":
    unittest.main()
