class SemanticEmbedder:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SemanticEmbedder, cls).__new__(cls, *args, **kwargs)
            cls._instance.model = None
        return cls._instance

    def _get_model(self):
        if self.model is None:
            # Lazy import to speed up initial load if embeddings aren't immediately needed
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
