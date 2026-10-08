import unittest
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.routers import events
from app.schemas.event_template import EventTemplateCreate, EventTemplateUpdate
from app.schemas.recipe_step import RecipeStepCreate
from app.schemas.weight_check import WeightCheckSettings, merge_weight_params
from app.services import recipe_service
from app.services.scale_service import Reading, ScaleService, weight_parameters


SETTINGS = {"tolerance_unit": "percent", "tolerance_below": 2, "tolerance_above": 3, "duration_seconds": 10, "enforce_minimum_weight": True}


class WeightSettingsTests(unittest.TestCase):
    def test_event_defaults_do_not_require_a_recipe_target(self):
        event = EventTemplateCreate(name="Weigh 10 seconds", event_type="weight_check", default_params=SETTINGS)
        self.assertEqual(event.default_params, SETTINGS)

    def test_legacy_recipe_still_uses_symmetric_grams_and_five_seconds(self):
        config = weight_parameters({"target_weight_g": 1000, "tolerance_g": 10})
        self.assertEqual((config.below_g, config.above_g, config.settings.duration_seconds), (10, 10, 5))

    def test_percentages_are_relative_to_target(self):
        config = weight_parameters({**SETTINGS, "target_weight_g": 1000})
        self.assertEqual((config.below_g, config.above_g), (20, 30))

    def test_decimal_percentages_keep_precise_boundaries(self):
        config = weight_parameters({**SETTINGS, "target_weight_g": "333.3", "tolerance_below": 0.5})
        self.assertEqual(config.target - config.below_g, Decimal("331.6335"))

    def test_invalid_defaults_rejected_on_event_creation(self):
        for overrides in ({"tolerance_unit": "kg"}, {"tolerance_below": -1},
                          {"tolerance_above": float("nan")}, {"tolerance_below": float("inf")},
                          {"duration_seconds": 0}, {"duration_seconds": -1},
                          {"duration_seconds": 1.5}, {"duration_seconds": 86401}):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                EventTemplateCreate(name="Test", event_type="weight_check", default_params={**SETTINGS, **overrides})

    def test_explicit_legacy_tolerance_overrides_template_percentages(self):
        merged = merge_weight_params(SETTINGS, {"target_weight_g": 1000, "tolerance_g": 5})
        config = weight_parameters(merged)
        self.assertEqual((config.below_g, config.above_g), (5, 5))
        self.assertEqual(config.settings.duration_seconds, 10)


class ConfigurableScaleTests(unittest.TestCase):
    def hold(self, params, weight, duration):
        service = ScaleService()
        service.check("plan", 0, params, now=100)
        for i in range(duration * 2 + 1):
            service.feed(Reading(Decimal(str(weight)), True, 100 + i / 2))
        return service.check("plan", 0, params, now=100 + duration)

    def test_asymmetric_gram_boundaries(self):
        params = {"target_weight_g": 500, "tolerance_below": 5, "tolerance_above": 20, "duration_seconds": 1}
        for weight, expected in ((495, True), (520, True), (494.999, False), (520.001, False)):
            with self.subTest(weight=weight):
                status = self.hold(params, weight, 1)
                self.assertEqual(status["ready"], expected)
                self.assertEqual((status["minimum_weight_g"], status["maximum_weight_g"]), (495, 520))

    def test_asymmetric_percent_boundaries(self):
        params = {**SETTINGS, "target_weight_g": 1000}
        for weight, expected in ((980, True), (1030, True), (979.99, False), (1030.01, False)):
            with self.subTest(weight=weight):
                status = self.hold(params, weight, 10)
                self.assertEqual(status["ready"], expected)
                self.assertEqual(status["required_seconds"], 10)

    def test_small_percent_target_accepts_both_five_gram_boundaries(self):
        params = {"target_weight_g": 12, "tolerance_unit": "percent", "tolerance_below": 3,
                  "tolerance_above": 3, "duration_seconds": 1}
        for weight, expected in ((10, True), (15, True), (9.999, False), (15.001, False)):
            with self.subTest(weight=weight):
                status = self.hold(params, weight, 1)
                self.assertEqual((status["minimum_weight_g"], status["maximum_weight_g"]), (10, 15))
                self.assertEqual(status["target_weight_g"], 12)
                self.assertEqual(status["ready"], expected)

    def test_gram_and_legacy_tolerances_round_outwards(self):
        for tolerances in ({"tolerance_below": 1, "tolerance_above": 2}, {"tolerance_g": 1}):
            with self.subTest(tolerances=tolerances):
                status = self.hold({"target_weight_g": 17, "duration_seconds": 1, **tolerances}, 15, 1)
                self.assertEqual((status["minimum_weight_g"], status["maximum_weight_g"]), (15, 20))
                self.assertTrue(status["ready"])

    def test_zero_tolerance_preserves_exact_ticks_and_brackets_fractional_target(self):
        for target, expected in ((15, (15, 15)), (12, (10, 15)), ("10.0001", (10, 15))):
            with self.subTest(target=target):
                status = self.hold({"target_weight_g": target, "duration_seconds": 1}, expected[0], 1)
                self.assertEqual((status["minimum_weight_g"], status["maximum_weight_g"]), expected)
                self.assertTrue(status["ready"])

    def test_rounded_lower_limit_respects_optional_ten_gram_protection(self):
        for protected, expected in ((True, 10), (False, 5)):
            with self.subTest(protected=protected):
                params = {"target_weight_g": 10, "tolerance_unit": "percent", "tolerance_below": 3,
                          "tolerance_above": 3, "duration_seconds": 1, "enforce_minimum_weight": protected}
                status = self.hold(params, 5, 1)
                self.assertEqual((status["minimum_weight_g"], status["maximum_weight_g"]), (expected, 15))
                self.assertEqual(status["ready"], not protected)

    def test_rounding_does_not_bypass_minimum_target_protection(self):
        status = self.hold({"target_weight_g": 5.1, "duration_seconds": 1}, 10, 1)
        self.assertEqual(status["target_weight_g"], 5.1)
        self.assertTrue(status["minimum_weight_blocked"])
        self.assertFalse(status["ready"])

    def test_changed_weight_within_rounded_interval_restarts_hold(self):
        params = {"target_weight_g": 12, "tolerance_unit": "percent", "tolerance_below": 3,
                  "tolerance_above": 3, "duration_seconds": 1}
        service = ScaleService()
        service.check("plan", 0, params, now=100)
        for timestamp in (100, 100.5, 101):
            service.feed(Reading(Decimal(10), True, timestamp))
        self.assertTrue(service.check("plan", 0, params, now=101)["ready"])
        service.feed(Reading(Decimal(15), True, 101.5))
        status = service.check("plan", 0, params, now=101.5)
        self.assertTrue(status["in_range"])
        self.assertEqual(status["held_seconds"], 0)
        self.assertFalse(status["ready"])

    def test_ten_seconds_cannot_finish_after_five(self):
        params = {**SETTINGS, "target_weight_g": 1000}
        status = self.hold(params, 1000, 5)
        self.assertFalse(status["ready"])
        self.assertEqual(status["held_seconds"], 5)
        self.assertTrue(self.hold(params, 1000, 10)["ready"])

    def test_long_duration_not_limited_to_old_256_samples(self):
        params = {**SETTINGS, "target_weight_g": 1000, "duration_seconds": 180}
        status = self.hold(params, 1000, 180)
        self.assertTrue(status["ready"])
        self.assertEqual(status["held_seconds"], 180)

    def test_instability_resets_configured_countdown(self):
        params = {**SETTINGS, "target_weight_g": 1000}
        service = ScaleService()
        service.check("plan", 0, params, now=100)
        for i in range(20):
            service.feed(Reading(Decimal(1000), True, 100 + i / 2))
        service.feed(Reading(Decimal(1000), False, 110))
        service.feed(Reading(Decimal(1000), True, 110.5))
        status = service.check("plan", 0, params, now=110.5)
        self.assertEqual(status["held_seconds"], 0)
        self.assertFalse(status["ready"])


class EventSettingsPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_recipe_copies_defaults_and_allows_step_overrides(self):
        for overrides, expected_duration in (({}, 10), ({"duration_seconds": 15}, 15)):
            db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(event_type="weight_check", default_params=SETTINGS)),
                                 add=Mock(), commit=AsyncMock(), refresh=AsyncMock(),
                                 execute=AsyncMock(side_effect=[SimpleNamespace(scalar_one_or_none=lambda: uuid.uuid4()), SimpleNamespace(scalar_one=lambda: None)]))
            payload = RecipeStepCreate(step_type="event", order_index=0, event_template_id=uuid.uuid4(),
                                       event_params={"target_weight_g": 1000, **overrides})
            step = await recipe_service.create_step(db, uuid.uuid4(), payload)
            self.assertEqual(step.event_params["duration_seconds"], expected_duration)
            self.assertEqual(step.event_params["tolerance_above"], 3)
            self.assertEqual(step.event_params["target_weight_g"], 1000)
            step.event_params["tolerance_above"] = 99
            self.assertEqual(SETTINGS["tolerance_above"], 3)

    async def test_event_create_saves_defaults(self):
        db = SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
        payload = EventTemplateCreate(name="Weigh 10 seconds", event_type="weight_check", default_params=SETTINGS)
        event = await events.create_event(uuid.uuid4(), payload, db, None)
        self.assertEqual(event.default_params, SETTINGS)
        db.commit.assert_awaited_once()

    async def test_event_update_saves_defaults_and_rejects_invalid_duration(self):
        event = SimpleNamespace(event_type="weight_check", folder_id=uuid.uuid4(), default_params=None)
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
        with patch.object(events, "_get_event_or_404", AsyncMock(return_value=event)), \
                patch.object(events.folder_service, "get_folder_or_404", AsyncMock()), \
                patch.object(events.permission_service, "has_folder_permission", AsyncMock(return_value=True)):
            await events.update_event(uuid.uuid4(), EventTemplateUpdate(default_params=SETTINGS), db, None)
            self.assertEqual(event.default_params, SETTINGS)
            db.commit.reset_mock()
            with self.assertRaises(HTTPException) as error:
                await events.update_event(uuid.uuid4(), EventTemplateUpdate(default_params={"duration_seconds": 0}), db, None)
            self.assertEqual(error.exception.status_code, 422)
            self.assertEqual(event.default_params, SETTINGS)
            db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
