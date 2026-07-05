"""
Thin wrapper around LLM provider APIs.
Supports Anthropic Claude, OpenAI, and Google Gemini — switch via LLM_PROVIDER env var.
"""
import json
from typing import Optional
from config import LLM_PROVIDER, ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, LLM_MODEL


async def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    model: Optional[str] = None,
) -> str:
    """
    Call the configured LLM and return the text response.
    Always returns a plain string — callers are responsible for JSON parsing.
    """
    target_model = model or LLM_MODEL

    if LLM_PROVIDER == "anthropic":
        return await _call_anthropic(system_prompt, user_message, max_tokens, temperature, target_model)
    elif LLM_PROVIDER == "openai":
        return await _call_openai(system_prompt, user_message, max_tokens, temperature, target_model)
    elif LLM_PROVIDER == "gemini":
        return await _call_gemini(system_prompt, user_message, max_tokens, temperature, target_model)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}. Set to 'anthropic', 'openai', or 'gemini'.")


async def _call_anthropic(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    model: str,
) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment variables.")

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


async def _call_openai(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    model: str,
) -> str:
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content


async def _call_gemini(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
    model: str,
) -> str:
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError(
            "google-generativeai package not installed. Run: pip install google-generativeai"
        )

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in environment variables.")

    genai.configure(api_key=GEMINI_API_KEY)

    gemini_model = genai.GenerativeModel(
        model_name=model,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
        system_instruction=system_prompt,
    )

    response = await gemini_model.generate_content_async(user_message)
    return response.text


def safe_parse_json(text: str) -> dict:
    """
    Extract and parse the first JSON object or array found in an LLM response.
    Handles markdown code fences gracefully.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        inner = []
        for i, line in enumerate(lines):
            if i == 0:
                continue
            if line.strip() == "```" and i == len(lines) - 1:
                continue
            inner.append(line)
        cleaned = "\n".join(inner).strip()

    # Find first { or [
    start = -1
    for i, ch in enumerate(cleaned):
        if ch in ("{", "["):
            start = i
            break

    if start == -1:
        raise ValueError(f"No JSON found in LLM response:\n{text[:500]}")

    # Find matching closing bracket
    opener = cleaned[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    end = -1
    for i in range(start, len(cleaned)):
        if cleaned[i] == opener:
            depth += 1
        elif cleaned[i] == closer:
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        raise ValueError(f"Unmatched brackets in LLM response:\n{text[:500]}")

    return json.loads(cleaned[start:end])
