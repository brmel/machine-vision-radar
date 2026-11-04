from __future__ import annotations

from radar.adapters.files.model_json import LANGUAGES, load_registry, load_schema
from radar.domain.ports.store.records import LISTED
from radar.domain.review.views import OWNED, admin_model

def test_the_admin_edits_every_entity_another_screen_does_not_own_labelled_and_reached_from_a_catalog_list() -> None:
    codes = [l.code for l in LANGUAGES]
    schema = load_schema()
    model = admin_model(schema, load_registry())
    edited = model.entities
    assert set(OWNED) <= {t.name for t in schema.entities}
    labels = [(e.id, e.label) for e in (*edited, *model.owned)] + [
        (f"{e.id}.{f.name}", f.label) for e in edited for f in e.fields]
    unlabelled = [f"{name} ({code})" for name, label in labels for code in codes if not label.get(code)]
    assert not unlabelled, f"admin entities and fields without a label: {unlabelled}"
    reached = set(LISTED)
    while grown := {e.id for e in edited for f in e.fields if f.name != "source_refs"
                    and reached & set(f.refs)} - reached:
        reached |= grown
    assert {e.id for e in edited} - reached == set(), "edited kinds no Catalog list reaches"
