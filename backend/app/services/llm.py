"""Shared LLM Service Abstraction for Reflexion.

Provides a centralized, singleton wrapper around the Google GenAI SDK.
All AI components in Reflexion interact with LLMs exclusively via this service.
"""

import logging
import re
import time
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.core.config import settings

logger = logging.getLogger("reflexion.llm")

T = TypeVar("T", bound=BaseModel)

NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, "400", "401", "403", "404"}


class LLMError(Exception):
    """Base exception for all LLM service errors."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM configuration (API key, model settings) is invalid or missing."""
    pass


class LLMAPIError(LLMError):
    """Raised when an API or network operation fails."""
    pass


class LLMValidationError(LLMError):
    """Raised when response content fails schema validation."""
    pass


class LLMService:
    """Centralized singleton service for interacting with Gemini models.
    
    Provides clean methods for text generation, structured JSON generation with
    Pydantic schema validation, and markdown response generation.
    """

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None) -> None:
        """Initialize the LLM service instance.
        
        Args:
            api_key: Optional API key override. If None, uses settings.GEMINI_API_KEY.
            default_model: Optional model override. If None, uses settings.GEMINI_MODEL.
        """
        self._api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self._default_model = default_model or getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Get or initialize the singleton Gemini Client instance.
        
        Raises:
            LLMConfigurationError: If GEMINI_API_KEY is not configured.
        """
        if self._client is None:
            if not self._api_key:
                logger.error("LLM initialization failed: GEMINI_API_KEY is not set.")
                raise LLMConfigurationError(
                    "GEMINI_API_KEY is missing. Please configure it in your environment or .env file."
                )
            try:
                self._client = genai.Client(api_key=self._api_key)
                logger.info("Initialized singleton Gemini client successfully.")
            except Exception as e:
                logger.error(f"Failed to instantiate Gemini client: {e}")
                raise LLMConfigurationError(f"Failed to initialize Gemini client: {str(e)}") from e
        return self._client

    @property
    def default_model(self) -> str:
        """Get the default model configured for the service."""
        return self._default_model

    def _is_non_retryable(self, error: Exception) -> bool:
        """Determine if an exception is non-retryable (400, 401, 403, 404, configuration, validation)."""
        if isinstance(error, (LLMConfigurationError, LLMValidationError)):
            return True
        if isinstance(error, APIError):
            code = getattr(error, "code", None)
            if code in NON_RETRYABLE_STATUS_CODES:
                return True
            msg = str(error).upper()
            if any(term in msg for term in ("NOT_FOUND", "404", "INVALID_ARGUMENT", "UNAUTHORIZED", "PERMISSION_DENIED")):
                if "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
                    return True
        return False

    def _execute_with_retry(
        self,
        model: str,
        contents: str,
        config: types.GenerateContentConfig,
        max_attempts: int = 3,
        initial_backoff: float = 2.0,
    ) -> types.GenerateContentResponse:
        """Internal helper to execute generate_content with exponential backoff retries.
        
        Args:
            model: Target Gemini model identifier.
            contents: Prompt contents string.
            config: GenerateContentConfig object.
            max_attempts: Maximum total attempts (default 3).
            initial_backoff: Base delay in seconds for exponential backoff.
            
        Returns:
            GenerateContentResponse object.
            
        Raises:
            LLMAPIError: If execution fails after maximum attempts or encounters non-retryable error.
        """
        client = self.client
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Executing LLM request [Model: {model}] (Attempt {attempt}/{max_attempts})")
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                logger.info(f"LLM request completed successfully [Model: {model}]")
                return response
            except Exception as e:
                last_exception = e
                if self._is_non_retryable(e):
                    logger.error(f"Non-retryable error encountered on attempt {attempt}: {str(e)}")
                    raise LLMAPIError(f"Gemini API Non-retryable Error: {str(e)}") from e

                msg = str(e)
                logger.warning(f"Transient error on attempt {attempt}/{max_attempts}: {msg}")

                if attempt < max_attempts:
                    sleep_time = initial_backoff * (2 ** (attempt - 1))
                    
                    # Parse dynamic retry delay if provided by Gemini API for rate limits
                    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                        match = re.search(r"retryDelay': '(\d+)s", msg) or re.search(r"retry in (\d+\.?\d*)s", msg)
                        if match:
                            sleep_time = max(sleep_time, float(match.group(1)) + 0.5)
                        else:
                            sleep_time = max(sleep_time, 5.0)

                    logger.info(f"Retrying LLM call in {sleep_time:.1f} seconds...")
                    time.sleep(sleep_time)

        logger.error(f"LLM request failed after {max_attempts} attempts [Model: {model}]")
        raise LLMAPIError(f"LLM API request failed after {max_attempts} attempts: {str(last_exception)}") from last_exception

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> str:
        """Generate plain text from prompt."""
        target_model = model or self._default_model
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )

        response = self._execute_with_retry(
            model=target_model,
            contents=prompt,
            config=config,
        )

        if not response.text:
            logger.error("LLM returned empty or null text response.")
            raise LLMAPIError("Gemini API returned an empty response.")

        return response.text.strip()

    def generate_json(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> T:
        """Generate structured response validated against a Pydantic schema."""
        target_model = model or self._default_model
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        response = self._execute_with_retry(
            model=target_model,
            contents=prompt,
            config=config,
        )

        if hasattr(response, "parsed") and isinstance(response.parsed, response_schema):
            return response.parsed

        raw_text = response.text
        if not raw_text:
            logger.error("Structured output generation returned empty response text.")
            raise LLMValidationError("Gemini API returned an empty text response for structured JSON.")

        try:
            validated_object = response_schema.model_validate_json(raw_text)
            return validated_object
        except ValidationError as ve:
            logger.error(f"Pydantic schema validation failed for model {response_schema.__name__}: {ve}")
            raise LLMValidationError(
                f"Failed to validate response against schema {response_schema.__name__}: {str(ve)}"
            ) from ve
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise LLMValidationError(f"Invalid JSON returned by LLM: {str(e)}") from e

    def generate_markdown(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> str:
        """Generate markdown-formatted text response."""
        markdown_instruction = (
            "Format your response cleanly in valid Markdown using headings, lists, code blocks, or tables where appropriate."
        )
        combined_instruction = (
            f"{system_instruction}\n\n{markdown_instruction}" if system_instruction else markdown_instruction
        )

        return self.generate_text(
            prompt=prompt,
            system_instruction=combined_instruction,
            temperature=temperature,
            model=model,
        )


# Global singleton instance and shortcut alias
llm_service = LLMService()
llm = llm_service
