"""
Embedding service using sentence-transformers.
Wraps the all-MiniLM-L6-v2 model for generating 384-dim embeddings.
Lazy-loads the model on first use to avoid slow startup.
"""

import numpy as np
from typing import Union, List
import os
import sys

# Windows DLL and OpenMP Fix
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
if os.name == 'nt' and hasattr(os, 'add_dll_directory'):
    torch_lib_path = os.path.join(sys.prefix, 'Lib', 'site-packages', 'torch', 'lib')
    if os.path.exists(torch_lib_path):
        try:
            os.add_dll_directory(torch_lib_path)
        except Exception:
            pass

try:
    import torch
    from sentence_transformers import SentenceTransformer
except ImportError:
    torch = None
    SentenceTransformer = None


class EmbeddingService:
    """Generates text embeddings using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self.dimension = 384

    def _ensure_model_loaded(self):
        """Lazy-load the model on first use."""
        if self._model is None:
            if SentenceTransformer is None:
                raise ImportError("sentence-transformers could not be loaded. Check DLL/torch installation.")
            
            print(f"Loading embedding model: {self.model_name}...")
            self._model = SentenceTransformer(self.model_name, device="cpu")
            print(f"Embedding model loaded ({self.dimension} dimensions)")

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """Encode text(s) into embedding vector(s).

        Args:
            texts: Single string or list of strings to encode

        Returns:
            numpy array of shape (384,) for single text or (n, 384) for batch
        """
        self._ensure_model_loaded()

        single = isinstance(texts, str)
        if single:
            texts = [texts]

        embeddings = self._model.encode(
            texts,
            show_progress_bar=len(texts) > 50,
            normalize_embeddings=True  # L2-normalize for cosine similarity
        )

        if single:
            return embeddings[0]

        return embeddings

    @property
    def vector_size(self) -> int:
        """Return the embedding dimension size."""
        return self.dimension
