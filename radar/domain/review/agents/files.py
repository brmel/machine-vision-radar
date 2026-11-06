from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from radar.domain.ai.meter import Meter
from radar.domain.model.entities import Claim, Document, Source, Term
from radar.domain.model.history.ids import keyed
from radar.domain.ports.ai.datasheet_extractor import Datasheet, DatasheetExtractor
from radar.domain.ports.store.blob_store import BlobStore
from radar.domain.ports.web.reader import File

@dataclass(frozen=True, slots=True)
class Staged:
    file: File
    document: Document

@dataclass(frozen=True, slots=True)
class Stated:
    source: Source
    claims: tuple[Claim, ...]
    cad: float

class Files:
    def __init__(self, blobs: BlobStore, meter: Meter[DatasheetExtractor],
                 vocabularies: Mapping[str, Mapping[str, Term]]) -> None:
        self._blobs, self._meter, self._kinds = blobs, meter, vocabularies["document_kinds"]
        self._rights = next(k for k, t in vocabularies["media_rights"].items() if t.research)

    def staged(self, file: File, product: str) -> Staged:
        ref = self._blobs.put(file.content, file.mime, False)
        kind = next(k for k, t in self._kinds.items() if t.mime_types and file.mime.startswith(tuple(t.mime_types)))
        return Staged(file,
                      Document(id=keyed("doc", ref.sha256), version=1, kind=kind, mime=file.mime,
                               bytes=len(file.content), sha256=ref.sha256, subjects=(product,), rights=self._rights,
                               source_url=file.link.address, fetched_at=file.retrieved_at))

    def stated(self, staged: Staged, source_type: str, day: str) -> Stated | None:
        kind, file = staged.document.kind, staged.file
        if not self._kinds[kind].research:
            return None
        source = Source(id=keyed("src", file.link.address), version=1, type=source_type, url=file.link.address,
                        retrieved_at=file.retrieved_at)
        product = staged.document.subjects[0]
        extraction, cad = self._meter.call(day,
                                           lambda extractor: extractor.extract(
                                               Datasheet(product, file.content, file.mime, source)))
        claims = tuple(Claim(id=keyed("clm", f"{product} {v.spec_key} {source.id}"), version=1, subject=product,
                             spec_key=v.spec_key, value=v.value, method=kind, recorded_at=source.retrieved_at, rank=1,
                             source_refs=(source.id,))
                       for v in extraction.values)
        return Stated(source, claims, cad)
