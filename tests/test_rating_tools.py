"""Tests for the rating tools (set/get the current user's star rating and favorite)."""

import pytest

RECIPE_ID = "00000000-0000-0000-0000-000000000000"  # id of BASE_RECIPE


async def test_set_rating_resolves_user_and_posts_rating(invoke, fetcher):
    await invoke("set_recipe_rating", slug="test-recipe", rating=4.5)

    assert fetcher.last("GET", "/api/users/self")["url"] == "/api/users/self"
    post = fetcher.last("POST", "/ratings/")
    assert post["url"] == f"/api/users/{fetcher.user_id}/ratings/test-recipe"
    # only provided fields are sent; isFavorite stays out of the body
    assert post["json"] == {"rating": 4.5}


async def test_set_rating_favorite_only_omits_rating(invoke, fetcher):
    await invoke("set_recipe_rating", slug="test-recipe", is_favorite=True)

    assert fetcher.last("POST", "/ratings/")["json"] == {"isFavorite": True}


async def test_set_rating_sends_both_fields(invoke, fetcher):
    await invoke("set_recipe_rating", slug="test-recipe", rating=5, is_favorite=False)

    assert fetcher.last("POST", "/ratings/")["json"] == {
        "rating": 5,
        "isFavorite": False,
    }


async def test_set_rating_looks_up_user_only_once(invoke, fetcher):
    await invoke("set_recipe_rating", slug="test-recipe", rating=3)
    await invoke("set_recipe_rating", slug="test-recipe", rating=4)

    lookups = [r for r in fetcher.requests if r["url"] == "/api/users/self"]
    assert len(lookups) == 1


@pytest.mark.parametrize("bad_rating", [-1, 5.5, 6])
async def test_set_rating_rejects_out_of_range(invoke, fetcher, bad_rating):
    with pytest.raises(Exception, match="between 0 and 5"):
        await invoke("set_recipe_rating", slug="test-recipe", rating=bad_rating)

    assert fetcher.last("POST", "/ratings/") is None


async def test_set_rating_requires_a_field(invoke, fetcher):
    with pytest.raises(Exception, match="at least one of rating or is_favorite"):
        await invoke("set_recipe_rating", slug="test-recipe")

    assert fetcher.last("POST", "/ratings/") is None


async def test_set_rating_rejects_empty_slug(invoke, fetcher):
    with pytest.raises(Exception, match="slug cannot be empty"):
        await invoke("set_recipe_rating", slug="", rating=3)

    assert fetcher.last("POST", "/ratings/") is None


async def test_get_recipe_rating_returns_existing_rating(invoke, fetcher):
    fetcher.ratings = [{"recipeId": RECIPE_ID, "rating": 4.0, "isFavorite": True}]

    result = await invoke("get_recipe_rating", slug="test-recipe")

    assert fetcher.last("GET", "/api/users/self/ratings/")["url"].endswith(RECIPE_ID)
    assert result == {
        "name": "Test Recipe",
        "slug": "test-recipe",
        "rating": 4.0,
        "isFavorite": True,
    }


async def test_get_recipe_rating_unrated_recipe_returns_none(invoke, fetcher):
    result = await invoke("get_recipe_rating", slug="test-recipe")

    assert result["rating"] is None
    assert result["isFavorite"] is False


async def test_get_rated_recipes_resolves_names_and_sorts(invoke, fetcher):
    fetcher.ratings = [
        {"recipeId": "unknown-id", "rating": 5.0, "isFavorite": False},
        {"recipeId": RECIPE_ID, "rating": 3.0, "isFavorite": True},
    ]

    result = await invoke("get_rated_recipes")

    # perPage=-1 asks Mealie for all recipes so every rating id can be resolved
    assert fetcher.last("GET", "/api/recipes")["params"]["perPage"] == -1
    assert result["total"] == 2
    # best rating first; unknown recipe ids keep their rating but have no name
    assert result["items"][0] == {
        "name": None,
        "slug": None,
        "rating": 5.0,
        "isFavorite": False,
    }
    assert result["items"][1] == {
        "name": "Test Recipe",
        "slug": "test-recipe",
        "rating": 3.0,
        "isFavorite": True,
    }


async def test_get_rated_recipes_min_rating_filters(invoke, fetcher):
    fetcher.ratings = [
        {"recipeId": RECIPE_ID, "rating": 3.0, "isFavorite": False},
        {"recipeId": "other-id", "rating": None, "isFavorite": True},
    ]

    result = await invoke("get_rated_recipes", min_rating=4)

    assert result == {"items": [], "total": 0}
