from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI

from cv_agent.config import settings


def get_chat_model(temperature: float = 0.2) -> BaseChatModel:
    """Return a model-agnostic chat model (local Ollama or hosted OpenAI-compatible)."""
    if settings.llm_provider == "ollama":
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=temperature,
            num_ctx=settings.ollama_num_ctx,
        )

    return ChatOpenAI(
        model=settings.openai_model,
        base_url=settings.openai_api_base,
        api_key=settings.openai_api_key,
        temperature=temperature,
    )


def get_embeddings() -> OllamaEmbeddings:
    """Return local multilingual embeddings via Ollama (e.g. qwen3-embedding or bge-m3)."""
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )
