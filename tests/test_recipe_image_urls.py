"""Tests for the recipe image URL tools (Mealie serves images without auth)."""

import pytest

RECIPE_ID = "00000000-0000-0000-0000-000000000000"  # id of BASE_RECIPE
BASE = "https://mealie.example.test"


async def test_get_recipe_image_url_points_at_original(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "image": "qwFb"}

    url = await invoke("get_recipe_image_url", slug="test-recipe")

    assert url == f"{BASE}/api/media/recipes/{RECIPE_ID}/images/original.webp?version=qwFb"


async def test_get_recipe_thumbnail_url_points_at_tiny_variant(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "image": "qwFb"}

    url = await invoke("get_recipe_thumbnail_url", slug="test-recipe")

    assert url == (
        f"{BASE}/api/media/recipes/{RECIPE_ID}/images/tiny-original.webp?version=qwFb"
    )


async def test_url_tools_only_read_the_recipe(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "image": "qwFb"}

    await invoke("get_recipe_image_url", slug="test-recipe")
    await invoke("get_recipe_thumbnail_url", slug="test-recipe")

    assert {r["method"] for r in fetcher.requests} == {"GET"}
    assert all(r["url"] == "/api/recipes/test-recipe" for r in fetcher.requests)


@pytest.mark.parametrize("tool", ["get_recipe_image_url", "get_recipe_thumbnail_url"])
async def test_url_tools_fail_for_recipe_without_image(invoke, fetcher, tool):
    with pytest.raises(Exception, match="no image"):
        await invoke(tool, slug="test-recipe")


async def test_version_is_url_encoded(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "image": "a b&c"}

    url = await invoke("get_recipe_image_url", slug="test-recipe")

    assert url.endswith("?version=a%20b%26c")


async def test_uses_public_url_and_ignores_trailing_slash(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "image": "qwFb"}
    fetcher.public_url = "https://recipes.example.org"

    url = await invoke("get_recipe_image_url", slug="test-recipe")

    assert url.startswith("https://recipes.example.org/api/media/")


def test_client_public_url_defaults_to_base_url_without_trailing_slash(monkeypatch):
    import httpx

    from mealie.client import MealieClient

    monkeypatch.setattr(httpx.Client, "get", lambda self, url: httpx.Response(200, request=httpx.Request("GET", url)))

    default = MealieClient("https://mealie.example.test/", "key")
    explicit = MealieClient("http://mealie:9000", "key", public_url="https://pub.example.org/")

    assert default.public_url == "https://mealie.example.test"
    assert explicit.public_url == "https://pub.example.org"
