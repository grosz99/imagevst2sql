"""
Anthropic Claude API wrapper for Vision capabilities.
"""

import base64
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, SecretStr

try:
    import anthropic
except ImportError:
    raise ImportError("anthropic package required: pip install anthropic")


class AnthropicConfig(BaseModel):
    """Anthropic API configuration."""

    api_key: SecretStr = Field(..., min_length=20)
    model: str = Field(default="claude-sonnet-4-20250514")
    max_tokens: int = Field(default=4096, ge=100, le=100000)

    model_config = {"extra": "forbid"}


class VisionResponse(BaseModel):
    """Response from Claude Vision API."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str

    model_config = {"extra": "forbid"}


class AnthropicService:
    """
    Service wrapper for Anthropic Claude API.
    Supports text and vision (image) queries.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Anthropic service.

        Args:
            api_key: Anthropic API key
            model: Model to use (default: claude-sonnet-4-20250514)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def ask_about_image(
        self,
        image_path: Path,
        question: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> VisionResponse:
        """
        Ask a question about an image using Claude Vision.

        Args:
            image_path: Path to image file (PNG, JPEG, GIF, WebP)
            question: Question to ask about the image
            system_prompt: Optional system prompt for context
            max_tokens: Maximum tokens in response

        Returns:
            VisionResponse with answer and usage stats

        Raises:
            FileNotFoundError: If image doesn't exist
            anthropic.APIError: If API call fails
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Read and encode image
        image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")

        # Determine media type
        suffix = image_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "image/png")

        # Build message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": question},
                ],
            }
        ]

        # Call API
        kwargs = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)

        return VisionResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )

    def ask_about_image_base64(
        self,
        image_base64: str,
        media_type: str,
        question: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> VisionResponse:
        """
        Ask a question about a base64-encoded image.

        Args:
            image_base64: Base64 encoded image data
            media_type: MIME type (e.g., "image/png")
            question: Question to ask about the image
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response

        Returns:
            VisionResponse with answer and usage stats
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        },
                    },
                    {"type": "text", "text": question},
                ],
            }
        ]

        kwargs = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)

        return VisionResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )

    def ask(
        self,
        question: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> VisionResponse:
        """
        Ask a text-only question.

        Args:
            question: Question to ask
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response

        Returns:
            VisionResponse with answer
        """
        messages = [{"role": "user", "content": question}]

        kwargs = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)

        return VisionResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )
