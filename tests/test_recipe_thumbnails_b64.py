"""Tests for get_recipe_thumbnails_b64 (batch thumbnails as base64 JPEG data URLs)."""

import base64
import io
import threading
import time

import pytest
from PIL import Image as PILImage

PREFIX = "data:image/jpeg;base64,"


def _webp(size=(400, 300), mode="RGB", color=(200, 30, 30)):
    buffer = io.BytesIO()
    PILImage.new(mode, size, color).save(buffer, format="WEBP")
    return buffer.getvalue()


def _decode(data_url):
    assert data_url.startswith(PREFIX)
    image = PILImage.open(io.BytesIO(base64.b64decode(data_url[len(PREFIX):])))
    assert image.format == "JPEG"
    return image


@pytest.fixture
def recipes(fetcher):
    """Serve several recipes by slug; individual tests set image bytes per recipe id."""
    store = {}
    images = {}

    def add(slug, image_bytes=None, has_image=True):
        recipe = {**fetcher.recipe, "slug": slug, "id": f"id-{slug}"}
        recipe["image"] = "abcd" if has_image else None
        store[slug] = recipe
        images[recipe["id"]] = image_bytes

    fetcher.get_recipe = lambda slug: store[slug]
    fetcher.get_recipe_image = lambda recipe_id, file_name: images[recipe_id]
    return add


async def test_returns_jpeg_data_urls_with_aspect_ratio_kept(invoke, recipes):
    recipes("a", _webp((400, 300)))

    result = await invoke("get_recipe_thumbnails_b64", slugs=["a"])

    image = _decode(result["a"])
    assert image.size == (150, 113)  # 400x300 scaled so the long edge is 150


async def test_does_not_upscale_small_images(invoke, recipes):
    recipes("a", _webp((100, 80)))

    result = await invoke("get_recipe_thumbnails_b64", slugs=["a"])

    assert _decode(result["a"]).size == (100, 80)


async def test_failures_only_affect_their_own_slug(invoke, recipes, fetcher):
    recipes("ok", _webp())
    recipes("no-image", has_image=False)
    recipes("broken", b"this is not an image")
    recipes("empty", b"")

    result = await invoke(
        "get_recipe_thumbnails_b64", slugs=["ok", "no-image", "broken", "empty", "missing"]
    )

    assert _decode(result["ok"])
    assert result["no-image"] is None
    assert result["broken"] is None
    assert result["empty"] is None
    assert result["missing"] is None  # get_recipe raises KeyError -> None
    assert list(result) == ["ok", "no-image", "broken", "empty", "missing"]


async def test_http_error_yields_none(invoke, recipes, fetcher):
    from mealie.client import MealieApiError

    recipes("a", _webp())

    def boom(recipe_id, file_name):
        raise MealieApiError(500, "boom")

    fetcher.get_recipe_image = boom

    result = await invoke("get_recipe_thumbnails_b64", slugs=["a"])

    assert result == {"a": None}


async def test_uses_the_thumbnail_variant(invoke, recipes, fetcher):
    recipes("a", _webp())
    seen = []
    original = fetcher.get_recipe_image
    fetcher.get_recipe_image = lambda rid, name: (seen.append(name), original(rid, name))[1]

    await invoke("get_recipe_thumbnails_b64", slugs=["a"])

    assert seen == ["min-original.webp"]


async def test_transparent_images_are_flattened_onto_white(invoke, recipes):
    recipes("a", _webp((64, 64), mode="RGBA", color=(0, 0, 0, 0)))

    result = await invoke("get_recipe_thumbnails_b64", slugs=["a"])

    image = _decode(result["a"]).convert("RGB")
    r, g, b = image.getpixel((10, 10))
    assert min(r, g, b) > 240


async def test_too_many_slugs_raise_clear_error(invoke, recipes, fetcher):
    slugs = [f"s{i}" for i in range(26)]

    with pytest.raises(Exception, match="At most 25 slugs"):
        await invoke("get_recipe_thumbnails_b64", slugs=slugs)

    assert fetcher.requests == []


async def test_exactly_25_slugs_are_allowed(invoke, recipes):
    slugs = [f"s{i}" for i in range(25)]
    for slug in slugs:
        recipes(slug, _webp((64, 64)))

    result = await invoke("get_recipe_thumbnails_b64", slugs=slugs)

    assert len(result) == 25 and all(v for v in result.values())


async def test_empty_and_duplicate_slugs(invoke, recipes):
    recipes("a", _webp())

    assert await invoke("get_recipe_thumbnails_b64", slugs=[]) == {}
    result = await invoke("get_recipe_thumbnails_b64", slugs=["a", "a"])
    assert list(result) == ["a"] and result["a"]


async def test_edge_is_clamped(invoke, recipes):
    recipes("a", _webp((1000, 500)))

    small = await invoke("get_recipe_thumbnails_b64", slugs=["a"], max_edge=1)
    large = await invoke("get_recipe_thumbnails_b64", slugs=["a"], max_edge=9999)

    assert max(_decode(small["a"]).size) == 32
    assert max(_decode(large["a"]).size) == 512


async def test_quality_is_clamped(invoke, recipes):
    # noisy image so JPEG quality visibly changes the output
    noise = PILImage.effect_noise((300, 300), 60).convert("RGB")
    buffer = io.BytesIO()
    noise.save(buffer, format="WEBP", lossless=True)
    recipes("a", buffer.getvalue())

    low = await invoke("get_recipe_thumbnails_b64", slugs=["a"], max_edge=300, quality=1)
    floor = await invoke("get_recipe_thumbnails_b64", slugs=["a"], max_edge=300, quality=30)
    high = await invoke("get_recipe_thumbnails_b64", slugs=["a"], max_edge=300, quality=100)
    ceiling = await invoke("get_recipe_thumbnails_b64", slugs=["a"], max_edge=300, quality=95)

    assert low["a"] == floor["a"]
    assert high["a"] == ceiling["a"]
    assert len(floor["a"]) < len(ceiling["a"])


async def test_at_most_five_requests_run_concurrently(invoke, recipes, fetcher):
    slugs = [f"s{i}" for i in range(12)]
    for slug in slugs:
        recipes(slug, _webp((64, 64)))

    lock = threading.Lock()
    state = {"now": 0, "peak": 0}
    original = fetcher.get_recipe_image

    def slow(recipe_id, file_name):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return original(recipe_id, file_name)

    fetcher.get_recipe_image = slow

    result = await invoke("get_recipe_thumbnails_b64", slugs=slugs)

    assert all(result.values())
    assert 1 < state["peak"] <= 5


async def test_result_is_text_not_image_content(server, recipes):
    mcp, _ = server
    recipes("a", _webp())

    content = await mcp.call_tool("get_recipe_thumbnails_b64", {"slugs": ["a"]})
    blocks = content[0] if isinstance(content, tuple) else content

    assert blocks and all(block.type == "text" for block in blocks)
    assert PREFIX in blocks[0].text
