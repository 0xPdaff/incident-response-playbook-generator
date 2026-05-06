"""File-based prompt/response cache."""

import json
import logging
import time
from pathlib import Path

from src.utils.config import PROJECT_ROOT, get_model_config
from src.utils.helpers import compute_cache_key, ensure_directory

logger = logging.getLogger(__name__)


class CacheManager:
    """Simple file-based cache for LLM prompts and responses."""

    def __init__(self):
        """Initialize the cache manager."""
        config = get_model_config()
        cache_config = config.get("cache", {})
        self.enabled = cache_config.get("enabled", True)
        self.ttl = cache_config.get("ttl_seconds", 3600)
        cache_dir = cache_config.get("directory", "data/cache")
        self.cache_dir = PROJECT_ROOT / cache_dir

        if self.enabled:
            ensure_directory(self.cache_dir)

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{key}.json"

    def get(self, system_prompt: str, user_prompt: str) -> str | None:
        """Look up a cached response.

        Args:
            system_prompt: System message.
            user_prompt: User message.

        Returns:
            Cached response text or None if not found/expired.
        """
        if not self.enabled:
            return None

        key = compute_cache_key(system_prompt, user_prompt)
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                entry = json.load(f)

            # Check TTL
            cached_at = entry.get("timestamp", 0)
            if time.time() - cached_at > self.ttl:
                logger.debug("Cache entry expired: %s", key)
                cache_path.unlink(missing_ok=True)
                return None

            logger.info("Cache hit: %s", key)
            return entry.get("response")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read cache entry %s: %s", key, e)
            return None

    def set(
        self,
        system_prompt: str,
        user_prompt: str,
        response: str,
    ) -> None:
        """Store a response in cache.

        Args:
            system_prompt: System message.
            user_prompt: User message.
            response: LLM response to cache.
        """
        if not self.enabled:
            return

        key = compute_cache_key(system_prompt, user_prompt)
        cache_path = self._get_cache_path(key)

        entry = {
            "key": key,
            "timestamp": time.time(),
            "system_prompt_hash": compute_cache_key(system_prompt),
            "user_prompt_hash": compute_cache_key(user_prompt),
            "response": response,
        }

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)
            logger.debug("Cached response: %s", key)
        except OSError as e:
            logger.warning("Failed to write cache entry %s: %s", key, e)

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        if not self.cache_dir.exists():
            return 0

        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1

        logger.info("Cleared %d cache entries", count)
        return count
