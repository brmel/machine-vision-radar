from __future__ import annotations

import json
import urllib.error
import urllib.request

from radar.adapters.console import log
from radar.domain.ports.web.attestation import Verdict

APP_CHECK = "https://firebaseappcheck.googleapis.com/v1beta"

class AppCheck:
    def __init__(self, project: str, token: str, root: str = APP_CHECK) -> None:
        self._project, self._token, self._root = project, token, root

    def check(self, token: str) -> Verdict:
        if not token:
            return Verdict.REFUSED
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json",
                   "x-goog-user-project": self._project}
        req = urllib.request.Request(f"{self._root}/projects/{self._project}:verifyAppCheckToken",
                                     data=json.dumps({"appCheckToken": token}).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                verified = json.loads(res.read() or b"{}")
        except urllib.error.HTTPError as exc:
            verdict = Verdict.REFUSED if 400 <= exc.code < 500 and exc.code != 429 else Verdict.UNAVAILABLE
            log.warn(f"app check: {verdict.value}", status=exc.code)
            return verdict
        except OSError as exc:
            log.warn(f"app check: unavailable: {exc}")
            return Verdict.UNAVAILABLE
        return (Verdict.ATTESTS if isinstance(verified, dict) and verified.get("alreadyConsumed") is not True
                else Verdict.REFUSED)

class Unchecked:
    def check(self, token: str) -> Verdict:
        return Verdict.ATTESTS
