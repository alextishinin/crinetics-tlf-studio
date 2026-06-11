"""Registry ↔ dispatcher sync.

Every table/figure shell the registry exposes on the Select TFLs page must
have a generator wired in generation_service — otherwise users can select a
shell whose generation is guaranteed to fail with 'Unknown table id'.
"""

from __future__ import annotations


def test_every_registry_shell_is_dispatchable():
    import config

    config.get_settings()  # primes sys.path so the tlf library imports

    from services import shell_service
    from services.generation_service import _dispatchers

    shell_service.clear_cache()
    registry = shell_service.load_registry()
    dispatch = _dispatchers()

    missing = sorted(
        s["id"]
        for s in registry.get("shells", [])
        if s.get("type") in ("table", "figure") and s["id"] not in dispatch
    )
    assert not missing, f"Shells selectable in the UI but not generatable: {missing}"


def test_table_number_formatting():
    from services.shell_ids import table_number

    assert table_number("t_14_1_1_1") == "14.1.1.1"
    assert table_number("f_14_3_5_1") == "14.3.5.1"
    assert table_number("t_14_3_1_11_common") == "14.3.1.11 (common)"
    assert table_number("t_14_3_1_11_aesi") == "14.3.1.11 (aesi)"
