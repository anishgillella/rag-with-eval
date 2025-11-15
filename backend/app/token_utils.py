"""Token counting and cost calculation utilities."""

import logging
from typing import Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class TokenUtils:
    """Utilities for token counting and cost calculation."""
    
    # Pricing per 1M tokens (as of 2024)
    # GPT-4o mini pricing via OpenRouter
    MODEL_PRICING = {
        "openai/gpt-4o-mini": {
            "input": 0.15 / 1_000_000,  # $0.15 per 1M input tokens
            "output": 0.60 / 1_000_000,  # $0.60 per 1M output tokens
        },
        # Default fallback pricing
        "default": {
            "input": 0.15 / 1_000_000,
            "output": 0.60 / 1_000_000,
        }
    }
    
    @staticmethod
    def calculate_cost(
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "openai/gpt-4o-mini"
    ) -> float:
        """
        Calculate cost in USD for token usage.
        
        Args:
            prompt_tokens: Number of input/prompt tokens
            completion_tokens: Number of output/completion tokens
            model: Model name for pricing lookup
        
        Returns:
            Cost in USD
        """
        pricing = TokenUtils.MODEL_PRICING.get(model, TokenUtils.MODEL_PRICING["default"])
        
        input_cost = prompt_tokens * pricing["input"]
        output_cost = completion_tokens * pricing["output"]
        
        total_cost = input_cost + output_cost
        
        return round(total_cost, 6)  # Round to 6 decimal places
    
    @staticmethod
    def extract_usage_from_response(response) -> Optional[TokenUsage]:
        """
        Extract token usage from OpenAI/OpenRouter API response.
        
        Args:
            response: OpenAI API response object
        
        Returns:
            TokenUsage object or None if not available
        """
        try:
            if hasattr(response, 'usage'):
                usage = response.usage
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                total_tokens = getattr(usage, 'total_tokens', prompt_tokens + completion_tokens)
                
                return TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=0.0  # Will be calculated separately
                )
            return None
        except Exception as e:
            logger.warning(f"Failed to extract token usage from response: {e}")
            return None
    
    @staticmethod
    def create_usage(
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "openai/gpt-4o-mini"
    ) -> TokenUsage:
        """
        Create TokenUsage object with calculated cost.
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            model: Model name for cost calculation
        
        Returns:
            TokenUsage object
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = TokenUtils.calculate_cost(prompt_tokens, completion_tokens, model)
        
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost
        )
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for a text string.
        Rough approximation: ~4 characters per token for English text.
        
        Args:
            text: Text to estimate tokens for
        
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        # Rough approximation: 1 token ≈ 4 characters for English
        return len(text) // 4
    
    @staticmethod
    def format_cost(cost_usd: float) -> str:
        """
        Format cost for display.
        
        Args:
            cost_usd: Cost in USD
        
        Returns:
            Formatted cost string
        """
        if cost_usd < 0.0001:
            return f"${cost_usd * 1000:.4f} (millicents)"
        elif cost_usd < 0.01:
            return f"${cost_usd:.6f}"
        else:
            return f"${cost_usd:.4f}"

