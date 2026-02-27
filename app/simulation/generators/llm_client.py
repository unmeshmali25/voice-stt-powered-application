"""
Multi-provider LLM client for persona generation and agent decisions.

Supports OpenRouter, OpenAI, Anthropic (Claude), and Ollama APIs.
Provides unified interface with retry logic, batching, and error handling.

Optimized for qwen3:4b local inference with configurable batch sizes and timeouts.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import aiohttp
from openai import AsyncOpenAI

from app.simulation.config import SimulationConfig

logger = logging.getLogger(__name__)


@dataclass
class CostTracker:
    """Track API usage and costs across persona generation."""

    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_time_seconds: float = 0.0
    per_persona_costs: List[dict] = field(default_factory=list)

    def add(self, agent_id: str, usage_info: dict) -> None:
        """
        Add usage info for a persona.

        Args:
            agent_id: The agent identifier
            usage_info: Dict with model, tokens, cost_usd, time_seconds
        """
        self.total_cost_usd += usage_info["cost_usd"]
        self.total_tokens += usage_info["total_tokens"]
        self.total_time_seconds += usage_info["time_seconds"]
        self.per_persona_costs.append({"agent_id": agent_id, **usage_info})

    def get_summary(self) -> dict:
        """Get summary of all tracked usage."""
        return {
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "total_time_seconds": self.total_time_seconds,
            "avg_cost_per_persona": self.total_cost_usd / len(self.per_persona_costs)
            if self.per_persona_costs
            else 0,
            "avg_time_per_persona": self.total_time_seconds
            / len(self.per_persona_costs)
            if self.per_persona_costs
            else 0,
            "per_persona_details": self.per_persona_costs,
        }


class LLMClient:
    """
    Multi-provider LLM client supporting OpenRouter, OpenAI, Claude, and Ollama.

    Usage:
        config = SimulationConfig()
        client = LLMClient(config)
        response = await client.complete("Generate a persona...")

        # Batch processing with Ollama
        responses = await client.batch_complete([prompt1, prompt2, ...], batch_size=8)
    """

    # Ollama-optimized settings for qwen3:4b
    OLLAMA_CONFIG = {
        "temperature": 0.1,  # Low for consistent JSON parsing
        "max_tokens": 200,  # Short responses for decisions
        "timeout": 30,  # Generous timeout for local LLM
        "batch_size": 8,  # Concurrent requests (balance speed vs memory)
        "context_window": 8192,  # Safe limit for 4B model
        "base_url": "http://localhost:11434",  # Default Ollama URL
    }

    def __init__(self, config: SimulationConfig):
        self.config = config
        self._openai_client: Optional[AsyncOpenAI] = None
        self._ollama_session: Optional[aiohttp.ClientSession] = None

    def _get_openai_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client (also works for OpenRouter)."""
        if self._openai_client is None:
            if self.config.llm_provider == "openrouter":
                # OpenRouter uses OpenAI-compatible API
                base_url = "https://openrouter.ai/api/v1"
                api_key = self.config.llm_api_key
            else:  # openai
                base_url = None
                api_key = self.config.llm_api_key

            self._openai_client = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
            )
        return self._openai_client

    async def complete(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Tuple[str, dict]:
        """
        Generate a completion using the configured LLM provider.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in response (default: from config)
            temperature: Sampling temperature (default: from config)

        Returns:
            Tuple of (response_text, usage_info) where usage_info contains:
            - model: str
            - prompt_tokens: int
            - completion_tokens: int
            - total_tokens: int
            - cost_usd: float
            - time_seconds: float

        Raises:
            ValueError: If API key is not configured
            RuntimeError: If generation fails after all retries and fallbacks
        """
        self.config.validate()

        max_tokens = max_tokens or self.config.llm_max_tokens
        temperature = temperature or self.config.llm_temperature

        # Try with fallback cascade (for OpenRouter)
        for fallback_attempt in range(len(self.config.fallback_models)):
            current_model = self.config.model
            logger.info(f"Using model: {current_model}")

            for retry_attempt in range(self.config.max_retries):
                start_time = time.time()

                try:
                    if self.config.llm_provider in ("openrouter", "openai"):
                        response = await self._openai_complete_with_model(
                            current_model, prompt, max_tokens, temperature
                        )
                        # Extract usage from response
                        usage_info = self._extract_usage(
                            response, current_model, start_time
                        )
                        return response.choices[0].message.content, usage_info
                    elif self.config.llm_provider == "claude":
                        response = await self._claude_complete_with_model(
                            current_model, prompt, max_tokens, temperature
                        )
                        # Claude response has different structure
                        usage_info = self._extract_usage(
                            response, current_model, start_time
                        )
                        # Extract text from Claude's content array
                        response_text = ""
                        if hasattr(response, "content") and response.content:
                            response_text = (
                                response.content[0].text
                                if hasattr(response.content[0], "text")
                                else str(response.content[0])
                            )
                        return response_text, usage_info
                    else:
                        raise ValueError(
                            f"Unknown provider: {self.config.llm_provider}"
                        )

                except Exception as e:
                    if retry_attempt == self.config.max_retries - 1:
                        logger.warning(
                            f"All retries failed for model {current_model}: {e}"
                        )
                        # Try next fallback model
                        if not self.config.advance_fallback_model():
                            raise RuntimeError(
                                f"LLM generation failed. All models exhausted. Last error: {e}"
                            ) from e
                        logger.info(f"Falling back to next model: {self.config.model}")
                        break
                    else:
                        # Exponential backoff for retry
                        delay = self.config.retry_delay * (2**retry_attempt)
                        logger.warning(
                            f"Retry {retry_attempt + 1}/{self.config.max_retries} for {current_model} in {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)

        # Should never reach here
        raise RuntimeError("Unexpected state in retry/fallback loop")

    async def _openai_complete_with_model(
        self, model: str, prompt: str, max_tokens: int, temperature: float
    ):
        """Generate completion using OpenAI/OpenRouter API with specified model."""
        client = self._get_openai_client()

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a persona generation assistant. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return response

    async def _claude_complete_with_model(
        self, model: str, prompt: str, max_tokens: int, temperature: float
    ):
        """Generate completion using Anthropic Claude API with specified model."""
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.config.llm_api_key)

        # Claude has a different max_tokens parameter name
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system="You are a persona generation assistant. Respond only with valid JSON.",
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        return response

    def _get_ollama_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session for Ollama."""
        # Check if session exists and is usable (bound to current event loop)
        if self._ollama_session is not None:
            try:
                # Check if session is closed
                if self._ollama_session.closed:
                    self._ollama_session = None
                else:
                    # Check if session is bound to current event loop
                    # by accessing internal _loop attribute
                    current_loop = asyncio.get_running_loop()
                    if (
                        hasattr(self._ollama_session, "_loop")
                        and self._ollama_session._loop != current_loop
                    ):
                        # Session bound to different event loop, need to recreate
                        logger.debug("Recreating Ollama session for new event loop")
                        self._ollama_session = None
            except RuntimeError:
                # No running event loop, can't use this session
                self._ollama_session = None

        if self._ollama_session is None:
            self._ollama_session = aiohttp.ClientSession()

        return self._ollama_session

    async def _ollama_complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[str, dict]:
        """
        Generate completion using local Ollama API.

        Optimized for qwen3:4b with proper timeout handling.

        Args:
            model: Ollama model name (e.g., "qwen3:4b")
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            system: Optional system message
            timeout: Request timeout in seconds (default: 30)

        Returns:
            Tuple of (response_text, usage_info)
        """
        session = self._get_ollama_session()
        url = f"{self.OLLAMA_CONFIG['base_url']}/api/generate"

        # Build prompt with system message if provided
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"

        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        request_timeout = timeout or self.OLLAMA_CONFIG["timeout"]
        start_time = time.time()

        try:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=request_timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(
                        f"Ollama API error {response.status}: {error_text}"
                    )

                data = await response.json()
                response_text = data.get("response", "")

                # Estimate tokens (Ollama doesn't always return token counts)
                # Rough estimate: 1 token ≈ 4 characters for English
                estimated_prompt_tokens = len(full_prompt) // 4
                estimated_completion_tokens = len(response_text) // 4

                latency = time.time() - start_time

                usage_info = {
                    "model": model,
                    "prompt_tokens": estimated_prompt_tokens,
                    "completion_tokens": estimated_completion_tokens,
                    "total_tokens": estimated_prompt_tokens
                    + estimated_completion_tokens,
                    "cost_usd": 0.0,  # Local LLM is free
                    "time_seconds": latency,
                }

                return response_text, usage_info

        except asyncio.TimeoutError:
            raise RuntimeError(f"Ollama request timed out after {request_timeout}s")
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    async def _ollama_batch_complete(
        self,
        model: str,
        prompts: List[str],
        max_tokens: int,
        temperature: float,
        system: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> List[Tuple[str, dict]]:
        """
        Process multiple prompts with Ollama using concurrent requests.

        Ollama doesn't natively support batching, so we simulate it with
        asyncio.gather() for concurrent processing.

        Args:
            model: Ollama model name
            prompts: List of prompts to process
            max_tokens: Maximum tokens per response
            temperature: Sampling temperature
            system: Optional system message
            batch_size: Max concurrent requests (default: 8)

        Returns:
            List of (response_text, usage_info) tuples
        """
        batch_size = batch_size or self.OLLAMA_CONFIG["batch_size"]
        results = []

        # Process in chunks to avoid overwhelming Ollama
        for i in range(0, len(prompts), batch_size):
            chunk = prompts[i : i + batch_size]

            # Create tasks for concurrent execution
            tasks = [
                self._ollama_complete(
                    model=model,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                )
                for prompt in chunk
            ]

            # Execute concurrently
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle results and errors
            for result in chunk_results:
                if isinstance(result, Exception):
                    logger.error(f"Ollama batch error: {result}")
                    # Return empty response on error
                    results.append(
                        (
                            "",
                            {
                                "model": model,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "total_tokens": 0,
                                "cost_usd": 0.0,
                                "time_seconds": 0.0,
                                "error": str(result),
                            },
                        )
                    )
                else:
                    results.append(result)

        return results

    async def close(self):
        """Close aiohttp session for Ollama."""
        if self._ollama_session and not self._ollama_session.closed:
            await self._ollama_session.close()

    def _extract_usage(self, response, model: str, start_time: float) -> dict:
        """
        Extract token usage and calculate cost from API response.

        Args:
            response: The API response object
            model: The model name used
            start_time: Request start time

        Returns:
            Dict with usage info: model, prompt_tokens, completion_tokens, total_tokens, cost_usd, time_seconds
        """
        # Get usage from response
        if hasattr(response, "usage"):
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
        else:
            # Fallback if usage not available
            prompt_tokens = completion_tokens = total_tokens = 0

        # Pricing (per 1M tokens) - default to free for unknown models
        PRICING = {
            # Minimax
            "minimax/minimax-m2.1": {"input": 0.0, "output": 0.0},
            # NVIDIA
            "nvidia/nemotron-3-nano-30b-a3b:free": {"input": 0.0, "output": 0.0},
            # Google
            "google/gemini-2.5-flash-lite": {"input": 0.0, "output": 0.0},
            # Legacy (for backward compatibility)
            "z-ai/glm-4.5-air:free": {"input": 0.0, "output": 0.0},
            "qwen/qwen-2.5-7b-instruct": {"input": 0.0, "output": 0.0},
        }

        pricing = PRICING.get(model, {"input": 0.0, "output": 0.0})

        prompt_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        completion_cost = (completion_tokens / 1_000_000) * pricing["output"]

        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": prompt_cost + completion_cost,
            "time_seconds": time.time() - start_time,
        }

    async def complete_json(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Tuple[dict, dict]:
        """
        Generate a completion and parse as JSON.

        Handles JSON extraction from markdown code blocks.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Tuple of (parsed_json, usage_info)

        Raises:
            ValueError: If response cannot be parsed as JSON
        """
        response_text, usage_info = await self.complete(prompt, max_tokens, temperature)
        parsed_json = self._extract_json(response_text)
        return parsed_json, usage_info

    @staticmethod
    def _extract_json(text: str) -> dict:
        """
        Extract JSON from text, handling markdown code blocks.

        Args:
            text: Raw LLM response

        Returns:
            Parsed JSON as dict

        Raises:
            ValueError: If JSON cannot be extracted
        """
        import re

        # Try to extract from markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse JSON from response: {e}\n\nResponse was:\n{text[:500]}"
            )

    async def batch_complete(
        self,
        prompts: List[str],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        batch_size: int = 8,
    ) -> List[Tuple[str, dict]]:
        """
        Process multiple prompts in batches.

        For Ollama, uses concurrent processing. For other providers,
        processes sequentially (to respect rate limits).

        Args:
            prompts: List of prompts to process
            max_tokens: Maximum tokens per response
            temperature: Sampling temperature
            batch_size: Number of concurrent requests (Ollama only)

        Returns:
            List of (response_text, usage_info) tuples
        """
        max_tokens = max_tokens or self.config.llm_max_tokens
        temperature = temperature or self.config.llm_temperature

        if self.config.llm_provider == "ollama":
            # Use concurrent batch processing for Ollama
            return await self._ollama_batch_complete(
                model=self.config.model,
                prompts=prompts,
                max_tokens=max_tokens,
                temperature=temperature,
                batch_size=batch_size,
            )
        else:
            # Process sequentially for API-based providers
            results = []
            for prompt in prompts:
                try:
                    result = await self.complete(prompt, max_tokens, temperature)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Batch error: {e}")
                    results.append(("", {"error": str(e), "time_seconds": 0}))
            return results

    def estimate_cost(self, num_personas: int) -> dict:
        """
        Estimate LLM API cost for generating personas.

        Args:
            num_personas: Number of personas to generate

        Returns:
            Dict with cost estimates per provider
        """
        # Rough estimates per persona (in USD)
        cost_estimates = {
            "openrouter": 0.0,  # Qwen 2.5 7B is free tier
            "openai": 0.05,  # gpt-4o-mini
            "claude": 0.03,  # claude-3-5-haiku
            "ollama": 0.0,  # Local LLM is free
        }

        estimated_cost = (
            cost_estimates.get(self.config.llm_provider, 0.05) * num_personas
        )

        return {
            "provider": self.config.llm_provider,
            "model": self.config.model,
            "num_personas": num_personas,
            "estimated_cost_usd": estimated_cost,
        }
