"""Shared LLM Service Abstraction for Reflexion.

Provider-agnostic wrapper supporting:
- Google Gemini
- Groq

All AI components interact only through this service.
"""

import json
import logging
import time
import re
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings

from google import genai
from google.genai import types
from google.genai.errors import APIError

from groq import Groq


logger = logging.getLogger("reflexion.llm")

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


class LLMConfigurationError(LLMError):
    pass


class LLMAPIError(LLMError):
    pass


class LLMValidationError(LLMError):
    pass


class LLMService:

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
    ):

        self.provider = settings.LLM_PROVIDER.lower()

        if self.provider == "groq":
            self._api_key = api_key or settings.GROQ_API_KEY
            self._default_model = (
                default_model
                or settings.GROQ_MODEL
            )

        elif self.provider == "gemini":
            self._api_key = api_key or settings.GEMINI_API_KEY
            self._default_model = (
                default_model
                or settings.GEMINI_MODEL
            )

        else:
            raise LLMConfigurationError(
                f"Unsupported LLM provider: {self.provider}"
            )

        self._client = None


    @property
    def client(self):

        if self._client is None:

            if not self._api_key:
                raise LLMConfigurationError(
                    f"{self.provider.upper()} API key missing"
                )

            try:

                if self.provider == "groq":

                    self._client = Groq(
                        api_key=self._api_key
                    )

                    logger.info(
                        "Initialized Groq client"
                    )


                elif self.provider == "gemini":

                    self._client = genai.Client(
                        api_key=self._api_key
                    )

                    logger.info(
                        "Initialized Gemini client"
                    )


            except Exception as e:

                raise LLMConfigurationError(
                    f"Client initialization failed: {e}"
                )


        return self._client



    @property
    def default_model(self):
        return self._default_model



    def _execute_with_retry(
        self,
        model: str,
        contents: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_attempts: int = 3,
    ):

        last_exception = None


        for attempt in range(1, max_attempts + 1):

            try:

                logger.info(
                    f"LLM request {attempt}/{max_attempts} "
                    f"[{self.provider}:{model}]"
                )


                # -----------------------------
                # GROQ
                # -----------------------------

                if self.provider == "groq":

                    response = self.client.chat.completions.create(

                        model=model,

                        messages=[

                            {
                                "role": "system",
                                "content": system_instruction
                                or ""
                            },

                            {
                                "role": "user",
                                "content": contents
                            }

                        ],

                        temperature=temperature,

                        response_format=(
                            {"type": "json_object"}
                            if json_mode
                            else None
                        )
                    )


                    return response.choices[0].message.content



                # -----------------------------
                # GEMINI
                # -----------------------------

                elif self.provider == "gemini":

                    config = types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=temperature,

                        response_mime_type=(
                            "application/json"
                            if json_mode
                            else None
                        )
                    )


                    response = self.client.models.generate_content(

                        model=model,

                        contents=contents,

                        config=config
                    )


                    return response.text


            except Exception as e:

                last_exception = e

                msg = str(e)

                logger.warning(
                    f"LLM failure attempt {attempt}: {msg}"
                )


                if attempt < max_attempts:

                    delay = 2 ** (attempt - 1)

                    if "429" in msg:
                        delay = 10

                    time.sleep(delay)



        raise LLMAPIError(
            f"LLM request failed: {last_exception}"
        )



    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> str:


        return self._execute_with_retry(

            model=model or self.default_model,

            contents=prompt,

            system_instruction=system_instruction,

            temperature=temperature

        ).strip()



    def generate_json(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> T:

        schema_text = json.dumps(
            response_schema.model_json_schema(),
            indent=2
        )

        enhanced_prompt = f"""
    You must return ONLY valid JSON.

    The JSON MUST exactly match this schema:

    {schema_text}

    Do not rename fields.
    Do not add wrapper objects.
    Do not create nested objects for fields that expect lists.
    Do not use camelCase. Use snake_case exactly.

    User request:

    {prompt}
    """


        raw_response = self._execute_with_retry(
            model=model or self.default_model,
            contents=enhanced_prompt,
            system_instruction=system_instruction,
            temperature=0.1,
            json_mode=True,
        )


        try:

            data = json.loads(raw_response)

            # Remove accidental wrapper objects
            if len(data) == 1:
                value = next(iter(data.values()))

                if isinstance(value, dict):
                    data = value


            return response_schema.model_validate(data)


        except ValidationError as e:

            logger.error(
                f"Schema validation failed: {e}"
            )

            logger.error(
                f"Raw response: {raw_response}"
            )

            raise LLMValidationError(
                str(e)
            )



    def generate_markdown(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> str:


        instruction = (
            "Format response using clean Markdown."
        )


        if system_instruction:
            instruction += "\n" + system_instruction


        return self.generate_text(
            prompt,
            instruction,
            temperature,
            model
        )



llm_service = LLMService()

llm = llm_service