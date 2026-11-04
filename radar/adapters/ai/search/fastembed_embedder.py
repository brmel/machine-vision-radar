from __future__ import annotations

import contextlib
import io
import math
import os
from functools import cached_property
from typing import Any, Sequence

from radar.domain.model.entities import EmbedderModel

def _unit(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(x) * float(x) for x in vector)) or 1.0
    return [float(x) / norm for x in vector]

class FastembedEmbedder:
    def __init__(self, model_id: str) -> None:
        self._model_id = model_id

    @cached_property
    def _fastembed(self) -> Any:
        os.environ["ORT_DISABLE_TELEMETRY"] = "1"
        try:
            import fastembed
        except ImportError as exc:
            raise RuntimeError("fastembed is not installed: python3 -m pip install -r radar/requirements.txt") from exc
        return fastembed

    @cached_property
    def _text_embedding(self) -> Any:
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                return self._fastembed.TextEmbedding(self._model_id)
        except ValueError as exc:
            cache = os.environ.get("FASTEMBED_CACHE_PATH")
            into = f"FASTEMBED_CACHE_PATH={cache} " if cache else ""
            raise RuntimeError(f"fastembed could not load {self._model_id} ({exc}). With the network off "
                               f"(HF_HUB_OFFLINE, as in the gate), it loads only from its cache: fetch it once, with "
                               f"the network on: {into}python3 -c "
                               f"'import fastembed; fastembed.TextEmbedding(\"{self._model_id}\")'") from exc

    @cached_property
    def model(self) -> EmbedderModel:
        known = {m["model"]: m for m in self._fastembed.TextEmbedding.list_supported_models()}
        if self._model_id not in known:
            raise ValueError(f"fastembed has no model '{self._model_id}'")
        return EmbedderModel(model_id=self._model_id, dimension=int(known[self._model_id]["dim"]),
                             version=f"fastembed {self._fastembed.__version__}")

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [_unit(v) for v in self._text_embedding.embed(list(texts))] if texts else []
