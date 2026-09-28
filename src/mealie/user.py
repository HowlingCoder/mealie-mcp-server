import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("mealie-mcp")


class UserMixin:
    """Mixin class for user-related API endpoints"""

    def get_current_user(self) -> Dict[str, Any]:
        """Get information about the currently logged in user.

        Returns:
            Dictionary containing user details such as id, username, email, and other profile information.
        """
        logger.info({"message": "Retrieving current user information"})
        return self._handle_request("GET", "/api/users/self")

    def get_current_user_id(self) -> str:
        """Return the ID of the user the API key belongs to (cached after first lookup)."""
        user_id = getattr(self, "_current_user_id", None)
        if not user_id:
            user_id = self.get_current_user()["id"]
            self._current_user_id = user_id
        return user_id

    def get_user_ratings(self) -> Dict[str, Any]:
        """Get all ratings (and favorite flags) of the logged in user.

        Returns:
            JSON response with a 'ratings' list. Each entry has recipeId, rating and isFavorite.
        """
        logger.info({"message": "Retrieving ratings of current user"})
        return self._handle_request("GET", "/api/users/self/ratings")

    def get_user_rating_for_recipe(self, recipe_id: str) -> Dict[str, Any]:
        """Get the rating of the logged in user for a single recipe.

        Args:
            recipe_id: The UUID (NOT the slug) of the recipe

        Returns:
            JSON response with recipeId, rating and isFavorite
        """
        if not recipe_id:
            raise ValueError("Recipe ID cannot be empty")

        logger.info({"message": "Retrieving rating for recipe", "recipe_id": recipe_id})
        return self._handle_request("GET", f"/api/users/self/ratings/{recipe_id}")

    def set_recipe_rating(
        self,
        slug: str,
        rating: Optional[float] = None,
        is_favorite: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Set the rating and/or favorite flag of the logged in user for a recipe.

        Args:
            slug: The slug identifier of the recipe
            rating: Star rating between 0 and 5 (half stars allowed). Omit to leave unchanged.
            is_favorite: Favorite flag. Omit to leave unchanged.

        Returns:
            JSON response confirming the update
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if rating is None and is_favorite is None:
            raise ValueError("Provide at least one of rating or is_favorite")
        if rating is not None and not 0 <= rating <= 5:
            raise ValueError("Rating must be between 0 and 5")

        payload: Dict[str, Any] = {}
        if rating is not None:
            payload["rating"] = rating
        if is_favorite is not None:
            payload["isFavorite"] = is_favorite

        user_id = self.get_current_user_id()
        logger.info({"message": "Setting recipe rating", "slug": slug})
        return self._handle_request(
            "POST", f"/api/users/{user_id}/ratings/{slug}", json=payload
        )
