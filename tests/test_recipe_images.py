"""Tests for the recipe image tools (full-size image and thumbnail download)."""

import base64

import pytest

RECIPE_ID = "00000000-0000-0000-0000-000000000000"  # id of BASE_RECIPE


def _image_block(result):
    block = result[0] if isinstance(result, list) else result
    assert block.type == "image"
    assert block.mimeType == "image/webp"
    return base64.b64decode(block.data)


async def test_get_recipe_image_downloads_original(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "image": "abcd"}

    result = await invoke("get_recipe_image", slug="test-recipe")

    assert _image_block(result) == b"fake-webp-bytes"
    assert (
        fetcher.last("GET", "/api/media/")["url"]
        == f"/api/media/recipes/{RECIPE_ID}/images/original.webp"
    )


async def test_get_recipe_thumbnail_downloads_min_variant(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "image": "abcd"}

    result = await invoke("get_recipe_thumbnail", slug="test-recipe")

    assert _image_block(result) == b"fake-webp-bytes"
    assert (
        fetcher.last("GET", "/api/media/")["url"]
        == f"/api/media/recipes/{RECIPE_ID}/images/min-original.webp"
    )


@pytest.mark.parametrize("tool", ["get_recipe_image", "get_recipe_thumbnail"])
async def test_image_tools_fail_for_recipe_without_image(invoke, fetcher, tool):
    with pytest.raises(Exception, match="no image"):
        await invoke(tool, slug="test-recipe")

    assert fetcher.last("GET", "/api/media/") is None


async def test_image_tool_fails_on_empty_download(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "image": "abcd"}
    fetcher.image_bytes = b""

    with pytest.raises(Exception, match="empty image"):
        await invoke("get_recipe_image", slug="test-recipe")


def test_mixin_rejects_unknown_image_file(fetcher):
    with pytest.raises(ValueError, match="Unsupported image file name"):
        fetcher.get_recipe_image(RECIPE_ID, "../secret.txt")

    assert fetcher.requests == []


def test_mixin_rejects_empty_recipe_id(fetcher):
    with pytest.raises(ValueError, match="Recipe ID cannot be empty"):
        fetcher.get_recipe_image("")


def _client_with(handler):
    import httpx

    from mealie.client import MealieClient

    client = object.__new__(MealieClient)  # skip the connection test in __init__
    client._client = httpx.Client(
        base_url="http://mealie.test", transport=httpx.MockTransport(handler)
    )
    return client


def test_client_raw_returns_response_bytes():
    import httpx

    client = _client_with(lambda request: httpx.Response(200, content=b"\x00\x01webp"))

    assert client._handle_request("GET", "/img", raw=True) == b"\x00\x01webp"


def test_client_raw_still_raises_api_error_on_404():
    import httpx

    from mealie.client import MealieApiError

    client = _client_with(lambda request: httpx.Response(404, text="not found"))

    with pytest.raises(MealieApiError) as exc:
        client._handle_request("GET", "/img", raw=True)
    assert exc.value.status_code == 404


async def test_image_tool_reports_missing_file_on_server(invoke, fetcher):
    from mealie.client import MealieApiError

    fetcher.recipe = {**fetcher.recipe, "image": "abcd"}

    def missing(recipe_id, file_name):
        raise MealieApiError(404, "not found")

    fetcher.get_recipe_image = missing

    with pytest.raises(Exception, match="not found on the Mealie server"):
        await invoke("get_recipe_thumbnail", slug="test-recipe")


async def test_image_tool_passes_through_other_api_errors(invoke, fetcher):
    from mealie.client import MealieApiError

    fetcher.recipe = {**fetcher.recipe, "image": "abcd"}

    def broken(recipe_id, file_name):
        raise MealieApiError(500, "boom")

    fetcher.get_recipe_image = broken

    with pytest.raises(Exception, match="boom"):
        await invoke("get_recipe_image", slug="test-recipe")
