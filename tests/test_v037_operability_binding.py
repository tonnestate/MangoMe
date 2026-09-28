from pathlib import Path
import tomllib

from mangome.operability import configure_codex


def test_codex_repair_replaces_legacy_eval_binding_with_canonical_database(tmp_path: Path):
    config = tmp_path / ".codex" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        '[mcp_servers.mangome_eval]\ncommand = "/old/launcher"\n\n'
        '[mcp_servers.mangome_eval.env]\nMANGOME_DATABASE = "mangome_uai_eval"\n',
        encoding="utf-8",
    )
    result = configure_codex(str(tmp_path), backend="mongo", database="mangome", home=str(tmp_path / "home"))
    parsed_project = tomllib.loads(config.read_text(encoding="utf-8"))
    assert "mangome_eval" not in parsed_project.get("mcp_servers", {})
    user_config = tmp_path / "home" / ".codex" / "config.toml"
    parsed = tomllib.loads(user_config.read_text(encoding="utf-8"))
    server = parsed["mcp_servers"]["mangome"]
    assert server["env"]["MANGOME_DATABASE"] == "mangome"
    assert server["env"]["MANGOME_EXPECTED_DATABASE"] == "mangome"
    assert server["env"]["MANGOME_ALLOW_EVAL_DATABASE"] == "0"
    assert server["startup_timeout_sec"] == 8
    assert any("mangome_eval" in item for item in result["removed_shadow_entries"])
