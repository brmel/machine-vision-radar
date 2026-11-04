from __future__ import annotations

from typing import Callable

from firebase_functions import https_fn, options

from radar import paths
from radar.adapters.console import log
from radar.adapters.web.api import Served, wire
from radar.domain.ports.web.endpoint import Request
from radar.adapters.wiring.root import Wiring

def entry(served: Served) -> Callable[[https_fn.Request], https_fn.Response]:
    @https_fn.on_request(region="us-central1", min_instances=0, max_instances=2, concurrency=4,
                         memory=options.MemoryOption.GB_2, timeout_sec=60,
                         secrets=["MODEL_API_KEY"])
    def api(req: https_fn.Request) -> https_fn.Response:
        res = served(Request(req.method, req.path, req.get_data(), {k.lower(): v for k, v in req.headers.items()},
                             req.remote_addr or "", {k: req.args[k] for k in req.args}))
        return https_fn.Response(wire(res), status=res.status, headers=dict(res.headers),
                                 content_type="application/json")
    return api

log.configure(json_mode=True)
api = entry(Served(lambda: Wiring(paths.firebase_project(), yes=True).api()))
