from __future__ import annotations

from nova_runtime_support.export_copy_parts import _serialize_item


def test_serialize_item_converts_values_to_attribute_value_maps() -> None:
    item: dict[str, object] = {
        "export_id": "export-1",
        "part_number": 1,
        "attempts": 2,
        "error": None,
    }

    assert _serialize_item(item) == {
        "export_id": {"S": "export-1"},
        "part_number": {"N": "1"},
        "attempts": {"N": "2"},
        "error": {"NULL": True},
    }
