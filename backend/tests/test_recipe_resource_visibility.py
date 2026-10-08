import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException

from app.models.folder import Folder
from app.schemas.recipe_step import RecipeStepCreate
from app.services import recipe_service
from app.services.ingredient_service import recipe_resource_path_is_visible, recipe_scope_path


WORKSHOP = "11111111-1111-1111-1111-111111111111"
BUNS = "22222222-2222-2222-2222-222222222222"
CAKES = "33333333-3333-3333-3333-333333333333"
PRODUCTS = "44444444-4444-4444-4444-444444444444"
INGREDIENTS = "55555555-5555-5555-5555-555555555555"
NESTED = "66666666-6666-6666-6666-666666666666"


def folder_path(*parts: str) -> str:
    return "/" + "/".join(parts) + "/"


class RecipeResourceVisibilityTests(unittest.TestCase):
    def test_scope_is_the_first_category_below_the_workshop(self):
        target = folder_path(WORKSHOP, BUNS, PRODUCTS, NESTED)
        self.assertEqual(recipe_scope_path(target), folder_path(WORKSHOP, BUNS))

    def test_nested_ingredient_sibling_is_visible_to_product(self):
        target = folder_path(WORKSHOP, BUNS, PRODUCTS, NESTED)
        resource = folder_path(WORKSHOP, BUNS, INGREDIENTS, NESTED)
        self.assertTrue(recipe_resource_path_is_visible(target, resource))

    def test_other_category_stays_isolated(self):
        target = folder_path(WORKSHOP, BUNS, PRODUCTS)
        resource = folder_path(WORKSHOP, CAKES, INGREDIENTS, NESTED)
        self.assertFalse(recipe_resource_path_is_visible(target, resource))

    def test_workshop_level_resources_keep_legacy_inheritance(self):
        target = folder_path(WORKSHOP, BUNS, PRODUCTS)
        self.assertTrue(recipe_resource_path_is_visible(target, folder_path(WORKSHOP)))

    def test_workshop_root_does_not_share_all_child_branches(self):
        target = folder_path(WORKSHOP)
        resource = folder_path(WORKSHOP, BUNS, INGREDIENTS)
        self.assertIsNone(recipe_scope_path(target))
        self.assertFalse(recipe_resource_path_is_visible(target, resource))


class RecipeResourceEnforcementTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_step_rejects_ingredient_from_another_category(self):
        ingredient = SimpleNamespace(folder_id=uuid.UUID(INGREDIENTS))
        foreign_folder = SimpleNamespace(materialized_path=folder_path(WORKSHOP, CAKES, INGREDIENTS))
        db = SimpleNamespace(get=AsyncMock(side_effect=[ingredient, foreign_folder]))
        target_folder = SimpleNamespace(materialized_path=folder_path(WORKSHOP, BUNS, PRODUCTS))
        payload = RecipeStepCreate(
            step_type="ingredient",
            order_index=0,
            ingredient_id=uuid.uuid4(),
            quantity_canonical=100,
        )

        with self.assertRaises(HTTPException) as error:
            await recipe_service.create_step(
                db,
                uuid.uuid4(),
                payload,
                target_folder=target_folder,
            )

        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(error.exception.detail, "recipe_resource_outside_product_scope")
        db.get.assert_any_await(Folder, uuid.UUID(INGREDIENTS))

    async def test_create_step_rejects_event_from_another_category(self):
        event = SimpleNamespace(folder_id=uuid.UUID(INGREDIENTS), event_type="timer")
        foreign_folder = SimpleNamespace(materialized_path=folder_path(WORKSHOP, CAKES, INGREDIENTS))
        db = SimpleNamespace(get=AsyncMock(side_effect=[event, foreign_folder]))
        target_folder = SimpleNamespace(materialized_path=folder_path(WORKSHOP, BUNS, PRODUCTS))
        payload = RecipeStepCreate(
            step_type="event",
            order_index=0,
            event_template_id=uuid.uuid4(),
            event_params={"duration_seconds": 60},
        )

        with self.assertRaises(HTTPException) as error:
            await recipe_service.create_step(
                db,
                uuid.uuid4(),
                payload,
                target_folder=target_folder,
            )

        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(error.exception.detail, "recipe_resource_outside_product_scope")


if __name__ == "__main__":
    unittest.main()
