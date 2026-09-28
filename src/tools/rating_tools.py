import logging
import traceback
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher
from mealie.client import MealieApiError

logger = logging.getLogger("mealie-mcp")


def register_rating_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all rating-related tools with the MCP server."""

    @mcp.tool()
    def set_recipe_rating(
        slug: str,
        rating: Optional[float] = None,
        is_favorite: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Set the star rating and/or favorite flag of a recipe for the current user.

        Args:
            slug: The unique text identifier for the recipe.
            rating: Star rating from 0 to 5 (half stars like 3.5 are allowed).
                Omit to leave the rating unchanged.
            is_favorite: Mark or unmark the recipe as favorite.
                Omit to leave the flag unchanged.

        Returns:
            Dict[str, Any]: Confirmation of the update. Use get_recipe_rating to verify.
        """
        try:
            logger.info({"message": "Setting recipe rating", "slug": slug})
            return mealie.set_recipe_rating(slug, rating=rating, is_favorite=is_favorite)
        except Exception as e:
            error_msg = f"Error setting rating for recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def get_recipe_rating(slug: str) -> Dict[str, Any]:
        """Get the current user's rating and favorite flag for a single recipe.

        Args:
            slug: The unique text identifier for the recipe.

        Returns:
            Dict[str, Any]: name, slug, rating (None if not rated) and isFavorite.
        """
        try:
            logger.info({"message": "Fetching recipe rating", "slug": slug})
            recipe = mealie.get_recipe(slug)
            try:
                user_rating = mealie.get_user_rating_for_recipe(recipe["id"])
            except MealieApiError as e:
                # Mealie answers 404 when the user never rated this recipe
                if e.status_code != 404:
                    raise
                user_rating = {}
            return {
                "name": recipe.get("name"),
                "slug": recipe.get("slug"),
                "rating": user_rating.get("rating"),
                "isFavorite": user_rating.get("isFavorite", False),
            }
        except Exception as e:
            error_msg = f"Error fetching rating for recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def get_rated_recipes(min_rating: Optional[float] = None) -> Dict[str, Any]:
        """List all recipes the current user has rated or favorited, best rated first.

        Args:
            min_rating: Only return recipes rated at least this high (0-5). Optional.

        Returns:
            Dict[str, Any]: 'items' with name, slug, rating and isFavorite per recipe.
        """
        try:
            logger.info({"message": "Fetching rated recipes"})
            ratings = mealie.get_user_ratings().get("ratings", [])

            # Ratings only carry recipe UUIDs, so resolve names/slugs via the recipe list
            recipes = mealie.get_recipes(per_page=-1).get("items", [])
            by_id = {r["id"]: r for r in recipes}

            items = []
            for entry in ratings:
                rating = entry.get("rating")
                if min_rating is not None and (rating is None or rating < min_rating):
                    continue
                recipe = by_id.get(entry.get("recipeId"), {})
                items.append(
                    {
                        "name": recipe.get("name"),
                        "slug": recipe.get("slug"),
                        "rating": rating,
                        "isFavorite": entry.get("isFavorite", False),
                    }
                )
            items.sort(key=lambda i: i["rating"] or 0, reverse=True)
            return {"items": items, "total": len(items)}
        except Exception as e:
            error_msg = f"Error fetching rated recipes: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)
