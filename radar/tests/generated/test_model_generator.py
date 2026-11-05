from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import jsonschema
import pytest

from radar import paths
from radar.build import codegen as generator
from radar.adapters.files.model_json import load_schema
from radar.domain.model.schema import SchemaError

@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    dest = tmp_path / "model"
    shutil.copytree(paths.MODEL, dest)
    return dest

def _edit_entities(model_dir: Path, edit) -> None:
    path = model_dir / "entities.json"
    entities = json.loads(path.read_text(encoding="utf-8"))
    edit(next(e for e in entities if e["id"] == "Product"))
    path.write_text(json.dumps(entities), encoding="utf-8")

def test_a_new_field_reaches_the_python_model_and_fails_the_check_until_generated(
        model_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _edit_entities(model_dir, lambda p: p["fields"].update(probe_flag={"type": "boolean", "optional": True}))
    py, *_ = generator.render(model_dir).values()
    assert "probe_flag: bool | None = None" in py
    assert generator.check(model_dir) == 1
    assert "python -m radar model generate" in capsys.readouterr().err

def test_a_contract_file_off_the_layout_fails_the_check_and_passes_in_it(
        model_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    values = model_dir / "value_types.json"
    laid = values.read_text(encoding="utf-8")
    values.write_text(json.dumps(json.loads(laid), indent=4), encoding="utf-8")
    assert generator.check(model_dir) == 1
    assert "value_types.json is not what `model generate` writes" in capsys.readouterr().err
    values.write_text(laid, encoding="utf-8")
    assert generator.check(model_dir) == 0

def test_unknown_type_is_refused(model_dir: Path) -> None:
    _edit_entities(model_dir, lambda p: p["fields"].update(probe={"type": "Nope"}))
    with pytest.raises(SchemaError, match="Nope"):
        load_schema(model_dir)

def test_an_enum_type_without_values_is_refused(model_dir: Path) -> None:
    path = model_dir / "value_types.json"
    path.write_text(json.dumps([{**t, "values": []} if t.get("kind") == "enum" else t
                                for t in json.loads(path.read_text(encoding="utf-8"))]), encoding="utf-8")
    with pytest.raises(SchemaError, match="enum without values"):
        load_schema(model_dir)

def test_a_view_reaches_the_app_domain_and_its_zod_schema(model_dir: Path) -> None:
    views = json.loads((model_dir / "views.json").read_text(encoding="utf-8"))
    views.append({"id": "ProbeView", "kind": "record", "description": "probe",
                  "fields": {"when": {"type": "PartialDate"}}})
    (model_dir / "views.json").write_text(json.dumps(views), encoding="utf-8")
    *_, view_ts, view_zod = generator.render(model_dir).values()
    assert "export interface ProbeView {" in view_ts and "export interface PartialDate {" in view_ts
    assert "export const ProbeViewSchema: z.ZodType<M.ProbeView> =" in view_zod

def test_a_tool_s_arguments_and_answer_are_json_schemas_of_the_model(model_dir: Path) -> None:
    path = model_dir / "tools.json"
    tools = json.loads(path.read_text(encoding="utf-8"))
    tools[0]["input"]["probe"] = {"type": "TermId", "optional": True, "default": "probe", "description": "a probe"}
    path.write_text(json.dumps(tools), encoding="utf-8")
    listed = json.loads(generator.render(model_dir)[paths.GENERATED_MCP_TOOLS])["tools"]
    assert [t["name"] for t in listed] == [t["id"] for t in tools]
    arguments = listed[0]["inputSchema"]
    assert arguments["properties"]["probe"] == {"$ref": "#/$defs/TermId", "description": "a probe", "default": "probe"}
    assert ("probe" not in arguments["required"] and arguments["$defs"]["TermId"]["pattern"]
            and arguments["additionalProperties"] is False)
    for tool in listed:
        jsonschema.Draft202012Validator.check_schema(tool["inputSchema"])
        jsonschema.Draft202012Validator.check_schema(tool["outputSchema"])
        refs = {r.split("/")[-1] for r in re.findall(r'"\$ref": "([^"]+)"', json.dumps(tool["outputSchema"]))}
        assert refs == set(tool["outputSchema"].get("$defs", {}))
    tools[0]["output"] = "Nope"
    path.write_text(json.dumps(tools), encoding="utf-8")
    with pytest.raises(SchemaError, match="Nope"):
        load_schema(model_dir)
