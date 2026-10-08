import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import jwt
from fastapi import HTTPException, Response

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.routers.auth import refresh
from app.schemas.recipe_step import RecipeStepCreate, RecipeStepUpdate
from app.services import execution_service, recipe_service
from app.services.scale_service import Reading, ScaleService


class SessionRefreshTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid.uuid4(), email="test@example.com", full_name="Test", is_active=True, voice_assistant_enabled=True)
        self.db = SimpleNamespace(get=AsyncMock(return_value=self.user))

    async def test_refresh_returns_new_access_token_and_http_only_cookie(self):
        response = Response()
        result = await refresh(response, self.db, create_refresh_token(self.user.id))
        token = decode_token(result.access_token)
        self.assertEqual(token["type"], "access")
        self.assertEqual(token["sub"], str(self.user.id))
        self.assertGreater(result.expires_in, 0)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])

    async def test_missing_malformed_expired_and_access_tokens_cannot_refresh(self):
        expired = jwt.encode({"sub": str(self.user.id), "type": "refresh", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, settings.jwt_secret, algorithm="HS256")
        for token in (None, "invalid", expired, create_access_token(self.user.id)[0]):
            with self.subTest(token_type=type(token).__name__), self.assertRaises(HTTPException) as error:
                await refresh(Response(), self.db, token)
            self.assertEqual(error.exception.status_code, 401)

    async def test_inactive_user_cannot_restore_session(self):
        self.user.is_active = False
        with self.assertRaises(HTTPException) as error:
            await refresh(Response(), self.db, create_refresh_token(self.user.id))
        self.assertEqual(error.exception.status_code, 401)


class BatchWeightTests(unittest.TestCase):
    def test_linked_1_7_grams_scales_to_5_1_for_triple_batch(self):
        result = execution_service.execution_event_params("weight_check", {"target_weight_g": 1.7, "use_ingredient_weight": True}, Decimal(3), Decimal("5.100"))
        self.assertEqual(result["target_weight_g"], 5.1)
        self.assertEqual(result["weight_target_basis"], "batch")

    def test_manual_target_is_scaled_and_never_scaled_twice(self):
        result = execution_service.execution_event_params("weight_check", {"target_weight_g": 1.7, "use_ingredient_weight": False}, Decimal(3), Decimal("9"))
        self.assertEqual(result["target_weight_g"], 5.1)
        self.assertEqual(execution_service.execution_event_params("weight_check", result, Decimal(3)), result)

    def test_existing_pending_plan_corrected_once_and_completed_step_unchanged(self):
        def step(status):
            return SimpleNamespace(status=status, step_type="ingredient_event", event_type_snapshot="weight_check", measure_type_snapshot="weight",
                                   quantity_canonical_computed=Decimal("5.1"), event_params_snapshot={"target_weight_g": 1.7})
        pending, done = step("pending"), step("done")
        plan = SimpleNamespace(id=uuid.uuid4(), multiplier=3, steps=[pending, done])
        with patch.object(execution_service.scale_service, "reset_plan") as reset:
            self.assertTrue(execution_service.normalize_plan_weight_targets(plan))
            self.assertEqual(pending.event_params_snapshot["target_weight_g"], 5.1)
            self.assertEqual(done.event_params_snapshot["target_weight_g"], 1.7)
            self.assertFalse(execution_service.normalize_plan_weight_targets(plan))
            reset.assert_called_once()

    def test_small_weight_protection_can_be_disabled_and_does_not_change_target(self):
        for protected, target, ready in ((True, 5.1, False), (False, 5.1, True), (True, 10, True)):
            with self.subTest(protected=protected, target=target):
                service = ScaleService()
                params = {"target_weight_g": target, "duration_seconds": 1, "enforce_minimum_weight": protected}
                service.check("plan", 0, params, now=100)
                for timestamp in (100, 100.5, 101):
                    service.feed(Reading(Decimal(str(target)), True, timestamp))
                result = service.check("plan", 0, params, now=101)
                self.assertEqual(result["target_weight_g"], target)
                self.assertEqual(result["ready"], ready)
                self.assertEqual(result["minimum_weight_blocked"], protected and target < 10)


class RecipeAppendAndLinkedWeightTests(unittest.IsolatedAsyncioTestCase):
    def db(self, objects, last_index=10):
        return SimpleNamespace(get=AsyncMock(side_effect=objects), add=Mock(), commit=AsyncMock(), refresh=AsyncMock(),
                               execute=AsyncMock(side_effect=[SimpleNamespace(scalar_one_or_none=lambda: uuid.uuid4()), SimpleNamespace(scalar_one=lambda: last_index)]))

    async def test_stale_position_does_not_duplicate_existing_step(self):
        db = self.db([SimpleNamespace(measure_type="weight")])
        payload = RecipeStepCreate(step_type="ingredient", order_index=10, ingredient_id=uuid.uuid4(), quantity_canonical=1.7)
        step = await recipe_service.create_step(db, uuid.uuid4(), payload)
        self.assertEqual(step.order_index, 11)
        self.assertIn("FOR UPDATE", str(db.execute.call_args_list[0].args[0]))

    async def test_linked_weight_uses_ingredient_quantity_without_manual_target(self):
        db = self.db([SimpleNamespace(measure_type="weight"), SimpleNamespace(event_type="weight_check", default_params=None)], None)
        payload = RecipeStepCreate(step_type="ingredient_event", order_index=0, ingredient_id=uuid.uuid4(), quantity_canonical=1.7,
                                   event_template_id=uuid.uuid4(), event_params={"use_ingredient_weight": True})
        step = await recipe_service.create_step(db, uuid.uuid4(), payload)
        self.assertEqual(step.event_params["target_weight_g"], 1.7)
        self.assertTrue(step.event_params["use_ingredient_weight"])

    async def test_non_weight_ingredient_cannot_supply_scale_target(self):
        db = self.db([SimpleNamespace(measure_type="volume"), SimpleNamespace(event_type="weight_check", default_params=None)])
        payload = RecipeStepCreate(step_type="ingredient_event", order_index=0, ingredient_id=uuid.uuid4(), quantity_canonical=2,
                                   event_template_id=uuid.uuid4(), event_params={"use_ingredient_weight": True})
        with self.assertRaises(HTTPException) as error:
            await recipe_service.create_step(db, uuid.uuid4(), payload)
        self.assertEqual(error.exception.status_code, 422)
        db.commit.assert_not_awaited()

    async def test_editing_ingredient_quantity_updates_linked_target(self):
        db = self.db([SimpleNamespace(event_type="weight_check"), SimpleNamespace(measure_type="weight")])
        step = SimpleNamespace(step_type="ingredient_event", ingredient_id=uuid.uuid4(), event_template_id=uuid.uuid4(), quantity_canonical=1.7,
                               event_params={"use_ingredient_weight": True, "target_weight_g": 1.7})
        await recipe_service.update_step(db, step, RecipeStepUpdate(quantity_canonical=2.5))
        self.assertEqual(step.event_params["target_weight_g"], 2.5)


if __name__ == "__main__":
    unittest.main()
