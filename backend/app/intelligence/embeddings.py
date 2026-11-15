"""One lazy, bounded CPU encoder per process. Runtime never downloads models."""

import hashlib
import json
import math
import threading
from functools import lru_cache

from app.core.config import Settings


class EmbeddingUnavailable(RuntimeError):
    pass


def profile(settings: Settings) -> str:
    return hashlib.sha256(
        json.dumps(
            [
                settings.embedding_model,
                settings.embedding_revision,
                settings.embedding_dimension,
                "token-windows-mean-normalized-v1",
            ]
        ).encode()
    ).hexdigest()


class Encoder:
    def __init__(self, model, dimension, batch_size):
        if model.get_sentence_embedding_dimension() != dimension:
            raise EmbeddingUnavailable("Embedding dimension does not match the configured model")
        self.model, self.dimension, self.batch_size = model, dimension, batch_size
        self.lock = threading.Lock()

    def encode(self, texts: list[str]) -> list[list[float]]:
        # Existing character chunks can exceed a model's token limit. Pool all
        # token windows rather than silently discarding their final passages.
        with self.lock:
            tokenizer = self.model.tokenizer
            width = self.model.max_seq_length - tokenizer.num_special_tokens_to_add(pair=False)
            results = []
            for text in texts:
                tokens = tokenizer.encode(text, add_special_tokens=False)
                windows = [tokens[i : i + width] for i in range(0, len(tokens), width)] or [[]]
                total = [0.0] * self.dimension
                weight = 0
                for start in range(0, len(windows), self.batch_size):
                    group = windows[start : start + self.batch_size]
                    vectors = self.model.encode(
                        [tokenizer.decode(w) for w in group],
                        batch_size=self.batch_size,
                        normalize_embeddings=True,
                        show_progress_bar=False,
                    )
                    for window, vector in zip(group, vectors, strict=True):
                        count = max(1, len(window))
                        total = [a + float(b) * count for a, b in zip(total, vector, strict=True)]
                        weight += count
                vector = [v / weight for v in total]
                norm = math.sqrt(sum(v * v for v in vector))
                if not math.isfinite(norm) or norm == 0:
                    raise EmbeddingUnavailable("Embedding model returned an invalid vector")
                results.append([v / norm for v in vector])
            return results


_load_lock = threading.Lock()


@lru_cache(maxsize=1)
def _load(model, revision, dimension, cache, batch, threads):
    try:
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(threads)
        instance = SentenceTransformer(
            model,
            revision=revision,
            device="cpu",
            cache_folder=cache,
            local_files_only=True,
            trust_remote_code=False,
        )
        return Encoder(instance, dimension, batch)
    except EmbeddingUnavailable:
        raise
    except Exception:
        raise EmbeddingUnavailable(
            "Local embedding model unavailable. Run python -m app.intelligence.cli prepare "
            "and verify the configured model, revision, and dimension."
        ) from None


def get_encoder(settings: Settings):
    if not settings.embeddings_enabled:
        raise EmbeddingUnavailable(
            "Embeddings are disabled; enable EMBEDDINGS_ENABLED and index documents"
        )
    with _load_lock:
        return _load(
            settings.embedding_model,
            settings.embedding_revision,
            settings.embedding_dimension,
            str(settings.embedding_cache_path),
            settings.embedding_batch_size,
            settings.embedding_threads,
        )
