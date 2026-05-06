"""LLM inference engine with multi-provider support and fallback."""

import logging
import time
from typing import Any

import litellm

from src.utils.config import (
    get_env,
    get_model_config,
)

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True


class InferenceEngine:
    """Multi-provider LLM inference with fallback chain and retry logic."""

    def __init__(self, provider_override: str | None = None):
        """Initialize the inference engine.

        Args:
            provider_override: Override the default provider for this session.
        """
        self.config = get_model_config()
        self.fallback_chain = self.config.get("fallback_chain", ["openai"])
        self.retry_config = self.config.get("retry", {})
        self.provider_override = provider_override

    def _get_active_chain(self) -> list[str]:
        """Get the provider chain, starting with override or default."""
        if self.provider_override:
            chain = [self.provider_override]
            # Add fallbacks that aren't the override
            for p in self.fallback_chain:
                if p != self.provider_override:
                    chain.append(p)
            return chain
        return list(self.fallback_chain)

    def _get_provider_config(self, provider: str) -> dict[str, Any]:
        """Get configuration for a specific provider."""
        providers = self.config.get("providers", {})
        return providers.get(provider, {})

    def _get_api_key(self, provider: str) -> str | None:
        """Get API key for a provider from environment."""
        prov_config = self._get_provider_config(provider)
        env_var = prov_config.get("api_key_env", "")
        if not env_var:
            return None
        return get_env(env_var)

    def _build_model_string(self, provider: str) -> str:
        """Build the litellm model string for a provider."""
        prov_config = self._get_provider_config(provider)
        model = prov_config.get("model", "gpt-4o")

        # litellm uses provider/model format for some providers
        # Ollama and local providers need special handling
        if provider == "ollama" and not model.startswith("ollama/"):
            model = f"ollama/{model}"

        return model

    def _call_llm(
        self,
        messages: list[dict[str, str]],
        provider: str,
    ) -> str | None:
        """Make a single LLM call to a specific provider.

        Args:
            messages: Chat messages in OpenAI format.
            provider: Provider name to use.

        Returns:
            Response text or None on failure.
        """
        prov_config = self._get_provider_config(provider)
        model = self._build_model_string(provider)
        api_key = self._get_api_key(provider)
        api_base = prov_config.get("api_base")

        # Build kwargs
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": prov_config.get("max_tokens", 4096),
            "temperature": prov_config.get("temperature", 0.3),
            "timeout": prov_config.get("timeout", 60),
        }

        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base

        try:
            logger.info("Calling LLM provider: %s (model: %s)", provider, model)
            response = litellm.completion(**kwargs)
            content = response.choices[0].message.content
            logger.info("LLM call successful: %s (%d chars)", provider, len(content or ""))
            return content
        except litellm.AuthenticationError as e:
            logger.warning("Authentication failed for %s: %s", provider, e)
            return None
        except litellm.RateLimitError as e:
            logger.warning("Rate limited by %s: %s", provider, e)
            return None
        except litellm.APIError as e:
            logger.warning("API error from %s: %s", provider, e)
            return None
        except Exception as e:
            logger.error("Unexpected error from %s: %s", provider, e)
            return None

    def _call_with_retry(
        self,
        messages: list[dict[str, str]],
        provider: str,
    ) -> str | None:
        """Call LLM with exponential backoff retry."""
        max_retries = self.retry_config.get("max_retries", 3)
        backoff_factor = self.retry_config.get("backoff_factor", 2)

        for attempt in range(max_retries):
            result = self._call_llm(messages, provider)
            if result is not None:
                return result

            if attempt < max_retries - 1:
                wait_time = backoff_factor ** (attempt + 1)
                logger.info(
                    "Retrying %s in %ds (attempt %d/%d)",
                    provider,
                    wait_time,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(wait_time)

        return None

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """Generate text using the LLM with fallback chain.

        Args:
            system_prompt: System message.
            user_prompt: User message.
            provider: Optional provider override for this call.

        Returns:
            Dict with 'text', 'provider_used', 'success', and 'error'.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Build the provider chain
        chain = self._get_active_chain()
        if provider and provider != self.provider_override:
            chain = [provider] + [p for p in chain if p != provider]

        # Check for API keys before trying
        available_providers = []
        for p in chain:
            prov_config = self._get_provider_config(p)
            env_var = prov_config.get("api_key_env", "")
            if not env_var or get_env(env_var):
                available_providers.append(p)
            else:
                logger.debug("Skipping %s: no API key configured", p)

        if not available_providers:
            return {
                "text": None,
                "provider_used": None,
                "success": False,
                "error": (
                    "No LLM providers available. Configure at least one API key "
                    "in your .env file. Required variables:\n"
                    "  - OPENAI_API_KEY\n"
                    "  - ANTHROPIC_API_KEY\n"
                    "  - DEEPSEEK_API_KEY\n"
                    "  - MINIMAX_API_KEY\n"
                    "  - KIMI_API_KEY\n"
                    "  - QWEN_API_KEY\n"
                    "  - GLM_API_KEY\n"
                    "  - Or run Ollama locally (no key needed)."
                ),
            }

        # Try each available provider in the fallback chain
        last_error = ""
        for p in available_providers:
            logger.info("Attempting generation with provider: %s", p)
            result = self._call_with_retry(messages, p)

            if result is not None:
                return {
                    "text": result,
                    "provider_used": p,
                    "success": True,
                    "error": None,
                }

            logger.warning("Provider %s failed, trying next in chain", p)

        return {
            "text": None,
            "provider_used": None,
            "success": False,
            "error": f"All providers failed. Last error: {last_error}",
        }

    def check_provider_health(self) -> dict[str, bool]:
        """Check which providers have valid API keys configured.

        Returns:
            Dict mapping provider names to availability status.
        """
        health = {}
        for provider in self.fallback_chain:
            api_key = self._get_api_key(provider)
            prov_config = self._get_provider_config(provider)

            # Ollama doesn't need a key
            if provider == "ollama":
                # Check if Ollama is running by checking the API base
                import httpx
                api_base = prov_config.get("api_base", "http://localhost:11434")
                try:
                    resp = httpx.get(f"{api_base}/api/tags", timeout=5)
                    health[provider] = resp.status_code == 200
                except Exception:
                    health[provider] = False
            else:
                health[provider] = bool(api_key)

        return health
