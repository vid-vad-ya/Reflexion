"""Validation script for Phase 4: Shared LLM Service Abstraction.

Tests Gemini client initialization, plain text generation, structured JSON response
with Pydantic validation, and markdown response generation.
"""

import sys
import os

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydantic import BaseModel
from app.services.llm import llm, LLMError, LLMConfigurationError


class TestResponse(BaseModel):
    language: str
    framework: str


def main():
    print("==================================================")
    print("Phase 4: Shared LLM Service Validation")
    print("==================================================")

    # 1. Initialize & Check Configuration
    print(f"\n[1/4] Service Configured Model: {llm.default_model}")
    try:
        client_instance = llm.client
        print("  [PASS] Gemini Singleton Client initialized successfully.")
    except LLMConfigurationError as e:
        print(f"  [CONFIG ERROR] {e}")
        print("\nNote: GEMINI_API_KEY must be set in backend/.env to run live API calls.")
        sys.exit(1)

    # 2. Test generate_text()
    print("\n[2/4] Testing generate_text()...")
    text_prompt = "Say hello in exactly three words."
    print(f"  Prompt: '{text_prompt}'")
    try:
        text_response = llm.generate_text(prompt=text_prompt, temperature=0.0)
        print(f"  Response: {text_response}")
        print("  [PASS] Text generation successful.")
    except LLMError as e:
        print(f"  [FAIL] Text generation failed: {e}")
        sys.exit(1)

    # 3. Test generate_json() (Structured Output)
    print("\n[3/4] Testing generate_json() (Pydantic Structured Output)...")
    json_prompt = "The project uses Python with FastAPI."
    print(f"  Prompt: '{json_prompt}'")
    print(f"  Expected Schema: TestResponse(language: str, framework: str)")
    try:
        json_response = llm.generate_json(
            prompt=json_prompt,
            response_schema=TestResponse,
            temperature=0.0,
        )
        print(f"  Validated Pydantic Object: {json_response}")
        print(f"  - language:  '{json_response.language}'")
        print(f"  - framework: '{json_response.framework}'")
        assert isinstance(json_response, TestResponse), "Output must be instance of TestResponse"
        assert json_response.language.lower() == "python", f"Expected language Python, got {json_response.language}"
        assert json_response.framework.lower() == "fastapi", f"Expected framework FastAPI, got {json_response.framework}"
        print("  [PASS] Structured JSON generation and Pydantic validation successful.")
    except LLMError as e:
        print(f"  [FAIL] Structured output failed: {e}")
        sys.exit(1)

    # 4. Test generate_markdown()
    print("\n[4/4] Testing generate_markdown()...")
    md_prompt = "List 2 main benefits of type hints in Python."
    try:
        md_response = llm.generate_markdown(prompt=md_prompt, temperature=0.0)
        print(f"  Response:\n{md_response}")
        print("  [PASS] Markdown generation successful.")
    except LLMError as e:
        print(f"  [FAIL] Markdown generation failed: {e}")
        sys.exit(1)

    print("\n==================================================")
    print("ALL PHASE 4 VALIDATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    main()
