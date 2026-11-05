from __future__ import annotations

import json
import os
import urllib.request
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from radar import paths
from radar.adapters.console import log
from radar.adapters.firestore.docs import FirestoreDocs
from radar.adapters.firestore.layout import catalog_of, read_records
from radar.adapters.firestore.store import scan
from radar.adapters.firestore.repository import (StoreCatalogRepository, StoreChangeLog, StoreHeldRecords,
                                                 StoreProposalQueue, StoreRecords, StoreVersionStore)
from radar.adapters.firestore.writer import StoreWriter
from radar.adapters.files import json_parser, json_store
from radar.adapters.files.model_json import load_model
from radar.adapters.storage.blobs import StorageBlobStore, bucket, media_url
from radar.adapters.storage.memory_catalog import MemoryCatalog
from radar.adapters.firestore.ledgers.agents import FirestoreAgentTokens, FirestoreResearchRuns
from radar.adapters.web.admin.identity import FirebaseIdentity
from radar.domain.ports.catalog.catalog import Catalog
from radar.domain.model.entities import EvalQuery
from radar.domain.model.model import Model, ParseError
from radar.domain.ports.catalog.catalog_repository import CatalogRepository
from radar.domain.ports.catalog.held_records import HeldRecords
from radar.domain.ports.catalog.views import Check, MediaUrl
from radar.domain.ports.store.records import Records
from radar.domain.ports.history.version_store import VersionStore
from radar.domain.ports.review.agent_tokens import AgentTokens
from radar.domain.ports.review.research_runs import ResearchRunLog
from radar.domain.ports.store.docs import Docs
from radar.domain.ai.eval import DatasheetCase
from radar.domain.read_model.history import Histories
from radar.domain.read_model.products.values import Terms
from radar.domain.read_model.derived.identity import ProductIdentity
from radar.domain.review.agents.duplicates import HELD
from radar.domain.review.review import Review
from radar.domain.validation.context import Part, Scope, Whole

DEMO = "demo-"
METADATA_TOKEN = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
FIRESTORE = "https://firestore.googleapis.com/v1"
STORAGE = "https://firebasestorage.googleapis.com"
NO_STORE = ("no store: pass --project with MVR_ACCESS_TOKEN, or start the emulators (`npm run emulators` in app/) and "
            "set "
            "FIRESTORE_EMULATOR_HOST and FIREBASE_STORAGE_EMULATOR_HOST")
TEST_ONLY = ("FIRESTORE_EMULATOR_HOST", "FIREBASE_STORAGE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST",
             "MVR_MEDIA_BASE", "MVR_STORAGE_BUCKET", "MVR_WEB_BASE")

def _service_account_token() -> str:
    req = urllib.request.Request(METADATA_TOKEN, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return str(json.loads(res.read())["access_token"])

class NoStore(Exception):
    ...

class Stores:
    def __init__(self, project: str | None = None, yes: bool = False) -> None:
        self._real, self._yes = project, yes
        self._model: Model | None = None

    def now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def today(self) -> date:
        return date.fromisoformat(self.now()[:10])

    def instant(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def correlate(self, job: str) -> str:
        cid = f"{job}-{uuid.uuid4().hex[:16]}"
        log.bind(correlation_id=cid)
        return cid

    def _host(self, variable: str) -> str:
        host = os.environ.get(variable)
        if not host:
            raise NoStore(NO_STORE)
        return host

    def _demo(self) -> str:
        name = os.environ.get("MVR_FIREBASE_PROJECT", "demo-mvradar")
        if not name.startswith(DEMO):
            raise NoStore(f"the emulators run on a {DEMO} project, not '{name}'")
        return name

    def _token(self) -> str:
        if self._real != paths.firebase_project():
            raise NoStore(f"--project names .firebaserc's project ({paths.firebase_project()}), not '{self._real}'")
        leftover = [v for v in TEST_ONLY if os.environ.get(v)]
        if leftover:
            raise NoStore("--project talks to the project, not the emulators or a fixture: unset "
                          f"{', '.join(leftover)}")
        token = os.environ.get("MVR_ACCESS_TOKEN") or (_service_account_token() if os.environ.get("K_SERVICE")
                                                       else None)
        if not token:
            raise NoStore("--project needs MVR_ACCESS_TOKEN=$(gcloud auth application-default print-access-token)")
        return token

    def store(self, database: str | None = None) -> Docs:
        name = database or os.environ.get("MVR_FIRESTORE_DATABASE", "(default)")
        if self._real:
            return FirestoreDocs(FIRESTORE, self._real, name, self._token(), writable=self._yes)
        return FirestoreDocs(f"http://{self._host('FIRESTORE_EMULATOR_HOST')}/v1", self._demo(), name)

    def blobs(self) -> StorageBlobStore:
        if self._real:
            return StorageBlobStore(STORAGE, bucket(), self._token(), writable=self._yes)
        self._demo()
        return StorageBlobStore(f"http://{self._host('FIREBASE_STORAGE_EMULATOR_HOST')}", bucket())

    def repository(self) -> CatalogRepository:
        return StoreCatalogRepository(self.store(), self.model())

    def model(self) -> Model:
        self._model = self._model or load_model()
        return self._model

    def writer(self) -> StoreWriter:
        return StoreWriter(self.store(), self.model(), self.now, self.blobs())

    def review(self) -> Review:
        model = self.model()
        return Review(StoreProposalQueue(self.store(), model.registry.proposal_kinds()), self.writer(), self.versions(),
                      lambda: self.catalog(tuple(HELD)), ProductIdentity.of(model.registry), model.schema,
                      self.instant)

    def identity(self) -> FirebaseIdentity:
        if self._real:
            return FirebaseIdentity(self._real, self._token(), writable=self._yes)
        return FirebaseIdentity(self._demo(), "owner", self._host("FIREBASE_AUTH_EMULATOR_HOST"))

    def agent_tokens(self) -> AgentTokens:
        return FirestoreAgentTokens(self.store())

    def research_runs(self) -> ResearchRunLog:
        return FirestoreResearchRuns(self.store())

    def held(self) -> HeldRecords:
        return StoreHeldRecords(self.store(), self.model())

    def records(self) -> Records:
        return StoreRecords(self.store(), self.model(), self.blobs())

    def histories(self) -> Histories:
        model, docs = self.model(), self.store()
        return Histories(self.versions(), self.repository(),
                         lambda ids: catalog_of(model, read_records(docs, model.schema, ids).values()),
                         Terms(model.registry).source_view)

    def catalog(self, kinds: tuple[str, ...] = ()) -> Catalog:
        return catalog_of(self.model(), scan(self.store(), self.model().schema, kinds))

    def catalog_at(self, path: str | None) -> tuple[Catalog, Scope]:
        if not path:
            return MemoryCatalog(), Part()
        p, model = Path(path), self.model()
        if not p.exists():
            raise ParseError(f"model file not found: {p}")
        if p.is_dir() or p.name.endswith(".jsonl"):
            return json_store.load_catalog(p if p.is_dir() else p.parent, model), Whole()
        return json_parser.load_catalog_file(p, model), Part()

    def datasheet_cases(self, path: Path) -> tuple[DatasheetCase, ...]:
        return json_parser.parse_datasheet_set(json_parser.read_json(path), self.model())

    def problems(self, path: Path) -> tuple[EvalQuery, ...]:
        return tuple(json_parser.load_catalog_file(path, self.model()).all(EvalQuery))

    def views(self) -> tuple[Check, MediaUrl]:
        return json_parser.Checker(self.model()), media_url

    def versions(self) -> VersionStore:
        docs = self.store()
        return StoreVersionStore(docs, StoreChangeLog(docs, self.model()))
