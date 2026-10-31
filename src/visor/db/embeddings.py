"""Optional semantic retrieval support.

The default retrieval path is lexical and has no model download or inference
dependency. Semantic retrieval is deliberately opt-in so a headless CLI or
MCP server remains usable offline.
"""

from __future__ import annotations

import os
from importlib.util import find_spec


RETRIEVAL_MODES = {"lexical", "semantic"}


class EmbeddingUnavailableError(RuntimeError):
    """Raised when semantic retrieval was requested but is not installed."""


def retrieval_mode() -> str:
    """Return the configured retrieval mode, defaulting to lightweight lexical."""
    mode = os.environ.get("VISOR_RETRIEVAL_MODE", "lexical").strip().lower()
    if mode not in RETRIEVAL_MODES:
        raise ValueError(
            f"VISOR_RETRIEVAL_MODE must be 'lexical' or 'semantic', not {mode!r}."
        )
    return mode


def semantic_enabled() -> bool:
    return retrieval_mode() == "semantic"


def semantic_dependencies_available() -> bool:
    """Check availability without importing a model or contacting the network."""
    return find_spec("sentence_transformers") is not None


class SemanticEmbedder:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SemanticEmbedder, cls).__new__(cls, *args, **kwargs)
            cls._instance.model = None
        return cls._instance

    def _get_model(self):
        if self.model is None:
            if not semantic_dependencies_available():
                raise EmbeddingUnavailableError(
                    "Semantic retrieval requires the optional dependency. Install "
                    "V.I.S.O.R. with `pip install 'visor-mcp[semantic]'`, or use "
                    "the default lexical mode."
                )
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        return self.model

    def encode(self, text: str) -> list[float]:
        """Encodes text into a normalized embedding vector for cosine similarity."""
        if not text:
            return [0.0] * 384
        model = self._get_model()
        # Create normalized embeddings so dot product acts as cosine similarity
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()


embedder = SemanticEmbedder()
