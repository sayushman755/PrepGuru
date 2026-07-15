"""
Local embeddings - no API cost, runs on your own machine.
Model downloads once (~80MB) on first use, then it's cached.
"""
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL_NAME


@lru_cache(maxsize=1)
def _model():
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    vector = _model().encode(text, normalize_embeddings=True)
    return vector.tolist()
