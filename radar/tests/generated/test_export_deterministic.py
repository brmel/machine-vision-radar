from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from radar import paths
from radar.tests.fixtures.fixture_category import built

FAKE_CLOCK = '''
import datetime as _dt, os, time as _time
_NOW = _dt.datetime.fromisoformat(os.environ["FAKE_NOW"]).replace(tzinfo=_dt.timezone.utc)
class _FakeDateTime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return _NOW if tz else _NOW.replace(tzinfo=None)
    @classmethod
    def utcnow(cls):
        return _NOW.replace(tzinfo=None)
class _FakeDate(_dt.date):
    @classmethod
    def today(cls):
        return _NOW.date()
_dt.datetime = _FakeDateTime
_dt.date = _FakeDate
_time.time = lambda: _NOW.timestamp()
'''

def _export_at(fake_now: str, out: Path, site: Path) -> dict[str, bytes]:
    env = {**os.environ, "FAKE_NOW": fake_now, "PYTHONPATH": os.pathsep.join([str(site), str(paths.DEV)])}
    code = ("import datetime, time; from pathlib import Path; from radar.tests.fixtures.fixture_category import "
            "export_bundle; "
            f"export_bundle(Path({str(built() / 'data')!r}), Path({str(out)!r}), Path({str(built() / 'registry')!r})); "
            "print(datetime.datetime.now().isoformat(), int(time.time()))")
    clock = subprocess.run([sys.executable, "-c", code], env=env, check=True, cwd=paths.DEV, capture_output=True,
                           text=True).stdout.split()
    assert clock == [fake_now, str(int(datetime.fromisoformat(fake_now).replace(tzinfo=timezone.utc).timestamp()))], (
        "the fake clock is applied")
    return {str(f.relative_to(out)): f.read_bytes() for f in sorted(out.rglob("*")) if f.is_file()}

def test_export_bytes_do_not_depend_on_the_clock(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(FAKE_CLOCK, encoding="utf-8")
    a = _export_at("2001-02-03T04:05:06", tmp_path / "early", site)
    b = _export_at("2033-11-12T13:14:15", tmp_path / "late", site)
    assert a and a.keys() == b.keys()
    assert [name for name in a if a[name] != b[name]] == [], (
        "these files differ between two fake dates: they carry a clock value")
