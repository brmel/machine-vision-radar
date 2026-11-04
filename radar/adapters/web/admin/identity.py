from __future__ import annotations

import base64
import json
import urllib.request
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_firebase_token

from radar.domain.ports.review.identity import Admin

TOOLKIT = "https://identitytoolkit.googleapis.com"

class FirebaseIdentity:
    def __init__(self, project: str, token: str, emulator: str | None = None, writable: bool = True) -> None:
        self._project, self._token, self._emulator, self._writable = project, token, emulator, writable

    def _claims(self, id_token: str) -> dict[str, Any] | None:
        if self._emulator:
            payload = id_token.split(".")[1] if id_token.count(".") == 2 else ""
            try:
                claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            except ValueError:
                return None
            return claims if isinstance(claims, dict) and claims.get("aud") == self._project else None
        try:
            return verify_firebase_token(id_token, Request(), audience=self._project)
        except ValueError:
            return None

    def admin(self, id_token: str) -> Admin | None:
        claims = self._claims(id_token)
        return (Admin(str(claims["sub"]), str(claims.get("email", ""))) if claims and claims.get("admin") is True
                else None)

    def _call(self, verb: str, body: dict[str, Any]) -> dict[str, Any]:
        root = f"http://{self._emulator}/identitytoolkit.googleapis.com" if self._emulator else TOOLKIT
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json",
                   "x-goog-user-project": self._project}
        req = urllib.request.Request(f"{root}/v1/projects/{self._project}/accounts:{verb}",
                                     data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as res:
            found = json.loads(res.read() or b"{}")
        return found if isinstance(found, dict) else {}

    def grant(self, email: str) -> str:
        if not self._writable:
            raise PermissionError(f"granting the admin claim on {self._project} needs --yes")
        users = self._call("lookup", {"email": [email]}).get("users") or []
        if not users:
            raise LookupError(f"no account signs in as {email}: sign in once at /admin first")
        uid = str(users[0]["localId"])
        self._call("update", {"localId": uid, "customAttributes": json.dumps({"admin": True})})
        return uid
