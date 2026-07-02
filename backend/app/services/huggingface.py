import requests
from fastapi import HTTPException

from app.config import settings

HF_CHAT_COMPLETIONS_URL = "https://router.huggingface.co/v1/chat/completions"


def _routed_model_id() -> str:
    model = settings.hf_model
    if ":" in model:
        return model
    provider = settings.hf_provider.strip()
    if provider:
        return f"{model}:{provider}"
    return f"{model}:fastest"


def _call_hf_chat(messages: list[dict[str, str]]) -> str:
    if not settings.hf_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. Set HF_API_KEY on the server.",
        )

    routed_model = _routed_model_id()
    headers = {
        "Authorization": f"Bearer {settings.hf_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": routed_model,
        "messages": messages,
        "max_tokens": 768,
        "temperature": 0.3,
    }

    try:
        response = requests.post(
            HF_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=120,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Hugging Face API is unreachable: {exc}",
        ) from exc

    if response.status_code == 503:
        raise HTTPException(
            status_code=503,
            detail="Hugging Face model is loading. Please retry shortly.",
        )

    if not response.ok:
        detail = response.text.strip() or response.reason
        if response.status_code == 400 and (
            "model_not_found" in detail or "model_not_supported" in detail
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Hugging Face model '{routed_model}' is unavailable. "
                    "Use a provider-backed model such as "
                    "mistralai/Mistral-7B-Instruct-v0.2 with HF_PROVIDER=featherless-ai."
                ),
            )
        raise HTTPException(
            status_code=502,
            detail=f"Hugging Face API request failed ({response.status_code}): {detail[:500]}",
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Hugging Face returned a non-JSON response",
        ) from exc

    if isinstance(data, dict) and data.get("error"):
        error = data["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise HTTPException(
            status_code=502,
            detail=f"Hugging Face API error: {message}",
        )

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Hugging Face returned an unexpected response format",
        ) from exc

    if not text or not str(text).strip():
        raise HTTPException(status_code=502, detail="Hugging Face returned an empty response")

    return str(text).strip()


def generate_hf_response(prompt: str) -> str:
    return _call_hf_chat([{"role": "user", "content": prompt}])


def generate_hf_chat(
    *,
    system_prompt: str,
    user_message: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history:
            role = item.get("role", "")
            content = item.get("content", "").strip()
            if not content or role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return _call_hf_chat(messages)
