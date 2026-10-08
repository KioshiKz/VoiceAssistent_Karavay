import unittest
import uuid
from decimal import Decimal
from functools import reduce
from operator import xor
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from app.services.scale_service import Reading, ScaleService, parse_cas_frame, weight_parameters
from app.services import execution_service, recipe_service
from app.schemas.recipe_step import RecipeStepCreate, RecipeStepUpdate


PARAMS = {"target_weight_g": 1000, "tolerance_g": 10}


def frame(weight=b"01.000", status=b"S", sign=b" ", units=b"kg"):
    body = status + sign + weight + units
    return b"\x01\x02" + body + bytes([reduce(xor, body, 0)]) + b"\x03\x04"


class ScaleTests(unittest.TestCase):
    def setUp(self):
        self.service = ScaleService()
        self.service.check("plan", 0, PARAMS, now=100)

    def feed(self, time, weight=1000, stable=True):
        self.service.feed(Reading(Decimal(str(weight)), stable, time))

    def hold(self, start=100, end=105, weight=1000):
        for i in range(round((end - start) * 2) + 1):
            self.feed(start + i / 2, weight)

    def status(self, now=105, params=None):
        return self.service.check("plan", 0, params or PARAMS, now=now)

    def test_requires_full_five_seconds(self):
        self.hold(end=104.5)
        self.assertFalse(self.status(104.5)["ready"])
        self.feed(105)
        self.assertTrue(self.status()["ready"])

    def test_changes_inside_tolerance_reset_hold(self):
        self.hold()
        self.feed(105.5, 1005)
        result = self.status(105.5)
        self.assertTrue(result["in_range"])
        self.assertEqual(result["held_seconds"], 0)
        self.assertFalse(result["ready"])

    def test_alternating_in_range_weights_never_pass(self):
        for i in range(30):
            self.feed(100 + i / 2, 1000 if i % 2 else 1005)
        self.assertFalse(self.status(114.5)["ready"])

    def test_out_of_range_resets_hold(self):
        self.hold()
        self.feed(105.5, 1020)
        self.feed(106)
        self.assertEqual(self.status(106)["held_seconds"], 0)

    def test_unstable_marker_resets_even_same_weight(self):
        self.hold()
        self.feed(105.5, stable=False)
        self.assertFalse(self.status(105.5)["ready"])
        self.feed(106)
        self.assertEqual(self.status(106)["held_seconds"], 0)

    def test_removal_revokes_ready(self):
        self.hold()
        self.assertTrue(self.status()["ready"])
        self.feed(105.5, 0)
        self.assertFalse(self.status(105.5)["ready"])

    def test_stale_reading_cannot_pass(self):
        self.hold()
        result = self.status(106.01)
        self.assertFalse(result["connected"])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["weight_g"])

    def test_missing_samples_reset_hold(self):
        self.hold()
        self.feed(107)
        self.assertEqual(self.status(107)["held_seconds"], 0)

    def test_disconnect_requires_fresh_hold(self):
        self.hold()
        self.service.invalidate("Disconnected")
        self.assertFalse(self.status()["ready"])
        self.feed(105.5)
        self.assertEqual(self.status(105.5)["held_seconds"], 0)

    def test_before_activation_does_not_count(self):
        self.hold()
        result = self.service.check("another-plan", 0, PARAMS, now=105)
        self.assertFalse(result["ready"])
        self.assertEqual(result["held_seconds"], 0)

    def test_rewind_cannot_reuse_previous_confirmation(self):
        self.hold()
        self.service.reset_plan("plan")
        self.assertFalse(self.status()["ready"])
        self.feed(105.5)
        self.assertEqual(self.status(105.5)["held_seconds"], 0.5)

    def test_each_step_requires_new_hold(self):
        self.hold()
        self.assertFalse(self.service.check("plan", 1, PARAMS, now=105)["ready"])

    def test_tolerance_boundaries_are_inclusive(self):
        for weight in (990, 1010):
            self.service.invalidate("reset")
            self.hold(weight=weight)
            self.assertTrue(self.status()["ready"])

    def test_invalid_parameters_fail_closed(self):
        for params in ({}, {"target_weight_g": -1}, {"target_weight_g": 0},
                       {"target_weight_g": float("nan")}, {"target_weight_g": float("inf")},
                       {"target_weight_g": 1000, "tolerance_g": -1},
                       {"target_weight_g": 1000, "tolerance_g": "NaN"}):
            with self.subTest(params=params), self.assertRaises(HTTPException):
                weight_parameters(params)

    def test_client_cannot_shorten_hold(self):
        self.hold(end=101)
        self.assertFalse(self.status(101, {**PARAMS, "hold_seconds": 0, "ready": True})["ready"])

    def test_real_hardware_zero_frame(self):
        reading = parse_cas_frame(bytes.fromhex("01 02 53 20 30 30 2e 30 30 30 6b 67 61 03 04"), 100)
        self.assertEqual(reading.weight_g, 0)
        self.assertTrue(reading.stable)

    def test_grams_conversion_sign_and_stability(self):
        reading = parse_cas_frame(frame(b"01.235", b"U", b"-"), 100)
        self.assertEqual(reading.weight_g, -1235)
        self.assertFalse(reading.stable)

    def test_corrupt_overload_unknown_units_rejected(self):
        damaged = bytearray(frame())
        damaged[6] ^= 1
        for packet in (bytes(damaged), frame(status=b"X"), frame(sign=b"F"),
                       frame(weight=b"FFFFFF"), frame(units=b"lb"), frame()[:-1],
                       frame(weight=b"1e0000")):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                parse_cas_frame(packet, 100)

    def test_fragmented_serial_response(self):
        connection = Mock()
        connection.in_waiting = 0
        packet = frame()
        connection.read.side_effect = [b"\x06", packet[:5], packet[5:11], packet[11:]]
        reading = self.service._poll(connection)
        self.assertEqual(reading.weight_g, 1000)
        self.assertEqual([call.args[0] for call in connection.write.call_args_list], [b"\x05", b"\x11"])
        connection.reset_input_buffer.assert_called_once()


class BackendEnforcementTests(unittest.IsolatedAsyncioTestCase):
    async def test_verified_advance_records_weight_and_consumes_hold(self):
        step = SimpleNamespace(event_type_snapshot="weight_check", event_params_snapshot=PARAMS,
                               status="pending", completed_at=None, order_index=0)
        plan = SimpleNamespace(id=uuid.uuid4(), status="not_started", current_step_index=0, steps=[step])
        line = SimpleNamespace(id=uuid.uuid4(), order_id=uuid.uuid4(), product_name_raw="Test", status="pending")
        order = SimpleNamespace(force_completed_at=None)
        db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock(), add=Mock())
        service = ScaleService()
        service.check(str(plan.id), 0, PARAMS, now=100)
        for i in range(11):
            service.feed(Reading(Decimal(1000), True, 100 + i / 2))
        with patch.object(execution_service, "_lock_plan_context", AsyncMock(return_value=(plan, line, order))), \
                patch.object(execution_service, "scale_service", service), \
                patch("app.services.scale_service.time.monotonic", return_value=105):
            await execution_service.advance_step(db, plan.id, None)
        self.assertEqual(step.status, "done")
        self.assertEqual(plan.status, "completed")
        self.assertEqual(plan.current_step_index, 1)
        db.commit.assert_awaited_once()
        verification = db.add.call_args.args[0].new_value["weight_verification"]
        self.assertEqual(verification["weight_g"], 1000)
        self.assertEqual(verification["held_seconds"], 5)
        self.assertFalse(service.check(str(plan.id), 0, PARAMS, now=105)["ready"])

    async def test_direct_advance_cannot_bypass_scale(self):
        step = SimpleNamespace(event_type_snapshot="weight_check", event_params_snapshot=PARAMS,
                               status="pending", completed_at=None, order_index=0)
        plan = SimpleNamespace(id=uuid.uuid4(), status="not_started", current_step_index=0, steps=[step])
        line = SimpleNamespace(status="pending")
        order = SimpleNamespace(force_completed_at=None)
        db = AsyncMock()
        with patch.object(execution_service, "_lock_plan_context", AsyncMock(return_value=(plan, line, order))), \
                patch.object(execution_service, "scale_service", ScaleService()):
            with self.assertRaises(HTTPException) as error:
                await execution_service.advance_step(db, plan.id, None)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(step.status, "pending")
        self.assertEqual(plan.current_step_index, 0)
        db.commit.assert_not_awaited()

    async def test_create_weight_event_requires_valid_target(self):
        db = AsyncMock()
        db.get.return_value = SimpleNamespace(event_type="weight_check")
        payload = RecipeStepCreate(step_type="event", order_index=0,
                                   event_template_id=uuid.uuid4(), event_params={"target_weight_g": 0})
        with self.assertRaises(HTTPException):
            await recipe_service.create_step(db, uuid.uuid4(), payload)
        db.commit.assert_not_awaited()

    async def test_update_cannot_erase_weight_parameters(self):
        db = AsyncMock()
        db.get.return_value = SimpleNamespace(event_type="weight_check")
        step = SimpleNamespace(event_template_id=uuid.uuid4(), event_params=PARAMS)
        with self.assertRaises(HTTPException):
            await recipe_service.update_step(db, step, RecipeStepUpdate(event_params=None))
        self.assertEqual(step.event_params, PARAMS)
        db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
