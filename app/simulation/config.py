"""
Configuration for the Agent Persona Generation System.

Uses environment variables for API keys and model selection.
Supports OpenRouter, OpenAI, and Claude API providers.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables from .env files
# Try .env.production first, then fall back to .env
load_dotenv(".env.production", override=True)
load_dotenv()  # Also load default .env for fallback


@dataclass
class SimulationConfig:
    """Configuration for persona generation system."""

    # LLM Provider Settings
    llm_provider: str = "openrouter"  # Options: openrouter, openai, claude
    llm_api_key: Optional[str] = None

    # Model Settings (per provider) - legacy, kept for compatibility
    openrouter_model: str = "z-ai/glm-4.5-air:free"
    openai_model: str = "gpt-4o-mini"
    claude_model: str = "claude-3-5-haiku-20241022"

    # Fallback models (OpenRouter) - used when provider is "openrouter"
    fallback_models: List[str] = field(default_factory=lambda: [
        "minimax/minimax-m2.1",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "google/gemini-2.5-flash-lite",
    ])
    current_model_index: int = 0  # Track which model is being used

    # LLM Generation Parameters
    llm_temperature: float = 0.8  # Balance creativity vs consistency
    llm_max_tokens: int = 2500

    # Generation Settings
    default_persona_count: int = 10
    max_concurrent_requests: int = 1  # Rate limiting (reduced for free tier)
    request_timeout: int = 60  # Seconds

    # Retry Settings
    max_retries: int = 5  # Increased for free tier rate limits
    retry_delay: float = 2.0  # Seconds (will use exponential backoff)

    # Output Settings
    output_dir: Path = Path("./data/personas")
    excel_enabled: bool = True
    save_preview_json: bool = True

    # Validation Settings
    validate_attributes: bool = True
    require_consistent_backstory: bool = True

    def __post_init__(self):
        """Load configuration from environment variables."""
        # LLM Provider
        if env_provider := os.getenv("LLM_PROVIDER"):
            self.llm_provider = env_provider.lower()

        # API Key - try provider-specific keys first, then generic
        if self.llm_provider == "openrouter":
            self.llm_api_key = os.getenv("OPENROUTER_API_KEY", "")
        elif self.llm_provider == "openai":
            self.llm_api_key = os.getenv("OPENAI_API_KEY", "")
        elif self.llm_provider == "claude":
            self.llm_api_key = os.getenv("ANTHROPIC_API_KEY", "")

        # Model overrides from environment
        if env_model := os.getenv("OPENROUTER_MODEL"):
            self.openrouter_model = env_model
        if env_model := os.getenv("OPENAI_MODEL"):
            self.openai_model = env_model
        if env_model := os.getenv("CLAUDE_MODEL"):
            self.claude_model = env_model

        # LLM parameters
        if temp := os.getenv("LLM_TEMPERATURE"):
            self.llm_temperature = float(temp)
        if tokens := os.getenv("LLM_MAX_TOKENS"):
            self.llm_max_tokens = int(tokens)

        # Ensure output directory exists
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def model(self) -> str:
        """Get the current model name based on provider."""
        if self.llm_provider == "openrouter":
            # Use fallback models if available
            if self.fallback_models and self.current_model_index < len(self.fallback_models):
                return self.fallback_models[self.current_model_index]
            return self.openrouter_model
        elif self.llm_provider == "openai":
            return self.openai_model
        elif self.llm_provider == "claude":
            return self.claude_model
        return "unknown"

    def advance_fallback_model(self) -> bool:
        """
        Move to next fallback model.

        Returns:
            True if moved to next model, False if no more models available
        """
        if self.current_model_index < len(self.fallback_models) - 1:
            self.current_model_index += 1
            return True
        return False

    def reset_fallback_index(self) -> None:
        """Reset the fallback model index to 0 (first model)."""
        self.current_model_index = 0

    def validate(self) -> bool:
        """Validate that required configuration is present."""
        if not self.llm_api_key:
            raise ValueError(
                f"API key not found for provider '{self.llm_provider}'. "
                f"Set {self.llm_provider.upper()}_API_KEY environment variable."
            )
        return True

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"SimulationConfig(provider={self.llm_provider}, model={self.model}, "
            f"temperature={self.llm_temperature}, max_tokens={self.llm_max_tokens})"
        )
