"""
Persona generator using LLM for creating unique agent personas.

Handles batch generation with concurrency control, validation, and error handling.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from app.simulation.config import SimulationConfig
from app.simulation.generators.llm_client import LLMClient, CostTracker
from app.simulation.generators.prompts import get_persona_prompt, CVS_DIVERSITY_NOTES
from app.simulation.models.persona import AgentPersona

logger = logging.getLogger(__name__)


class PersonaGenerator:
    """
    Generate agent personas using LLM.

    Usage:
        config = SimulationConfig()
        generator = PersonaGenerator(config)
        personas, cost_summary = await generator.generate_batch(count=10)
    """

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.llm_client = LLMClient(config)
        self.cost_tracker = CostTracker()

    async def generate_batch(
        self,
        count: int = 10,
        show_progress: bool = True,
    ) -> Tuple[List[AgentPersona], dict]:
        """
        Generate multiple personas concurrently.

        Args:
            count: Number of personas to generate
            show_progress: Whether to log progress messages

        Returns:
            Tuple of (list of generated AgentPersona objects, cost_summary dict)
        """
        if show_progress:
            logger.info(f"Generating {count} personas using {self.config.llm_provider}")
            logger.info(f"Fallback models: {' -> '.join(self.config.fallback_models)}")

        personas = []
        errors = []

        # Generate in batches to respect rate limits
        batch_size = self.config.max_concurrent_requests

        for i in range(0, count, batch_size):
            batch_count = min(batch_size, count - i)
            batch_start = i

            # Create tasks for this batch
            batch_tasks = [
                self._generate_single_with_tracking(
                    agent_id=f"agent_{j+1:03d}",
                    diversity_index=j % len(CVS_DIVERSITY_NOTES),
                )
                for j in range(batch_start, batch_start + batch_count)
            ]

            # Execute batch concurrently
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Process results
            for j, result in enumerate(batch_results):
                agent_num = batch_start + j + 1
                if isinstance(result, Exception):
                    error_msg = f"Failed to generate agent_{agent_num:03d}: {result}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                elif self._validate_persona(result):
                    personas.append(result)
                    if show_progress:
                        logger.info(f"Generated {agent_num}/{count}: {result.agent_id} - "
                                   f"{result.demographics.age}yo {result.demographics.gender}, "
                                   f"{result.demographics.income_bracket} income")
                else:
                    error_msg = f"agent_{agent_num:03d} failed validation"
                    logger.warning(error_msg)
                    errors.append(error_msg)

        if show_progress:
            logger.info(f"Generated {len(personas)}/{count} personas successfully")
            if errors:
                logger.warning(f"Encountered {len(errors)} errors")

        cost_summary = self.cost_tracker.get_summary()
        return personas, cost_summary

    async def generate_batch_streaming(
        self,
        count: int = 10,
        show_progress: bool = True,
        batch_callback: Optional[Callable[[List[AgentPersona]], None]] = None,
    ) -> Tuple[List[AgentPersona], dict]:
        """
        Generate personas with streaming callback for incremental export.

        This method is similar to generate_batch() but calls a callback function
        after each batch completes, enabling incremental saving to disk.

        Args:
            count: Number of personas to generate
            show_progress: Whether to log progress messages
            batch_callback: Optional function called after each batch with new personas

        Returns:
            Tuple of (list of generated AgentPersona objects, cost_summary dict)
        """
        if show_progress:
            logger.info(f"Generating {count} personas using {self.config.llm_provider}")
            logger.info(f"Fallback models: {' -> '.join(self.config.fallback_models)}")

        personas = []
        errors = []

        # Generate in batches to respect rate limits
        batch_size = self.config.max_concurrent_requests

        for i in range(0, count, batch_size):
            batch_count = min(batch_size, count - i)
            batch_start = i

            # Create tasks for this batch
            batch_tasks = [
                self._generate_single_with_tracking(
                    agent_id=f"agent_{j+1:03d}",
                    diversity_index=j % len(CVS_DIVERSITY_NOTES),
                )
                for j in range(batch_start, batch_start + batch_count)
            ]

            # Execute batch concurrently
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Process results - collect batch personas separately
            batch_personas = []
            for j, result in enumerate(batch_results):
                agent_num = batch_start + j + 1
                if isinstance(result, Exception):
                    error_msg = f"Failed to generate agent_{agent_num:03d}: {result}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                elif self._validate_persona(result):
                    batch_personas.append(result)
                    personas.append(result)
                    if show_progress:
                        logger.info(f"Generated {agent_num}/{count}: {result.agent_id} - "
                                   f"{result.demographics.age}yo {result.demographics.gender}, "
                                   f"{result.demographics.income_bracket} income")
                else:
                    error_msg = f"agent_{agent_num:03d} failed validation"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Call callback with this batch for incremental export
            if batch_callback and batch_personas:
                batch_callback(batch_personas)

        if show_progress:
            logger.info(f"Generated {len(personas)}/{count} personas successfully")
            if errors:
                logger.warning(f"Encountered {len(errors)} errors")

        cost_summary = self.cost_tracker.get_summary()
        return personas, cost_summary

    async def _generate_single_with_tracking(
        self,
        agent_id: str,
        diversity_index: Optional[int] = None,
    ) -> AgentPersona:
        """
        Generate a single persona via LLM with cost tracking.

        Args:
            agent_id: Unique identifier for the agent
            diversity_index: Index for diversity notes (0-9)

        Returns:
            Generated AgentPersona object

        Raises:
            Exception: If LLM generation fails
        """
        # Build prompt with CVS Health context (default)
        prompt = get_persona_prompt(agent_id, diversity_index, use_cvs_context=True)

        # Get LLM response as JSON with usage tracking
        persona_data, usage_info = await self.llm_client.complete_json(
            prompt=prompt,
            max_tokens=self.config.llm_max_tokens,
            temperature=self.config.llm_temperature,
        )

        # Track cost
        self.cost_tracker.add(agent_id, usage_info)

        # Add metadata
        persona_data["agent_id"] = agent_id
        persona_data["generated_at"] = datetime.utcnow().isoformat()
        persona_data["generation_model"] = usage_info["model"]

        # Create AgentPersona object (validates structure)
        return AgentPersona(**persona_data)

    def _validate_persona(self, persona: AgentPersona) -> bool:
        """
        Validate a generated persona for internal consistency.

        Args:
            persona: The persona to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.config.validate_attributes:
            return True

        try:
            # Pydantic already validates structure and ranges
            # Additional consistency checks:

            # 1. Age group should match age
            age = persona.demographics.age
            age_group = persona.demographics.age_group
            expected_group = self._get_age_group(age)
            if age_group != expected_group:
                logger.warning(
                    f"{persona.agent_id}: age_group '{age_group}' doesn't match age {age} (expected '{expected_group}')"
                )

            # 2. Budget should align with income
            budget = persona.shopping_preferences.weekly_budget
            income = persona.demographics.income_bracket
            reasonable_budgets = {
                "low": (10, 40),
                "medium": (25, 70),
                "high": (50, 100),
                "affluent": (75, 150),
            }
            min_budget, max_budget = reasonable_budgets.get(income, (0, 1000))
            if not (min_budget <= budget <= max_budget):
                logger.warning(
                    f"{persona.agent_id}: weekly_budget ${budget} outside reasonable range for {income} income (${min_budget}-${max_budget})"
                )

            # 3. Temporal patterns should have reasonable values
            total_day_prob = sum(persona.temporal_patterns.preferred_days.values())
            total_time_prob = sum(persona.temporal_patterns.preferred_times.values())

            if not (0.5 <= total_day_prob <= 2.0):
                logger.warning(
                    f"{persona.agent_id}: preferred_days sum to {total_day_prob:.2f}, expected ~1.0"
                )
            if not (0.5 <= total_time_prob <= 2.0):
                logger.warning(
                    f"{persona.agent_id}: preferred_times sum to {total_time_prob:.2f}, expected ~1.0"
                )

            return True

        except Exception as e:
            logger.error(f"Validation error for {persona.agent_id}: {e}")
            return False

    @staticmethod
    def _get_age_group(age: int) -> str:
        """Get expected age group for a given age."""
        if age <= 24:
            return "18-24"
        elif age <= 34:
            return "25-34"
        elif age <= 44:
            return "35-44"
        elif age <= 54:
            return "45-54"
        elif age <= 64:
            return "55-64"
        else:
            return "65+"

    async def generate_with_checkpoint(
        self,
        count: int,
        checkpoint_interval: int = 5,
        checkpoint_path: Optional[str] = None,
    ) -> List[AgentPersona]:
        """
        Generate personas with periodic checkpointing for large batches.

        Args:
            count: Total number of personas to generate
            checkpoint_interval: Save progress every N personas
            checkpoint_path: Path to save checkpoint JSON

        Returns:
            List of generated personas
        """
        import json
        from pathlib import Path

        if checkpoint_path is None:
            checkpoint_path = self.config.output_dir / f"checkpoint_{count}.json"

        personas = []
        checkpoint_path = Path(checkpoint_path)

        # Check for existing checkpoint
        if checkpoint_path.exists():
            logger.info(f"Resuming from checkpoint: {checkpoint_path}")
            with open(checkpoint_path) as f:
                data = json.load(f)
                personas = [AgentPersona(**p) for p in data]
                logger.info(f"Loaded {len(personas)} personas from checkpoint")

        # Generate remaining
        remaining = count - len(personas)
        if remaining > 0:
            new_personas = await self.generate_batch(remaining)
            personas.extend(new_personas)

            # Save checkpoint
            if len(personas) % checkpoint_interval == 0 or len(personas) == count:
                with open(checkpoint_path, "w") as f:
                    json.dump([p.model_dump() for p in personas], f, indent=2)
                logger.info(f"Checkpoint saved: {len(personas)}/{count} personas")

        return personas
