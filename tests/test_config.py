"""Unit tests for configuration manager, YAML read/write, and models."""

import pytest
from pathlib import Path
from news_agent_core.config import ConfigManager, TopicConfig, AppConfig


def test_load_default_config():
    mgr = ConfigManager()
    assert mgr.config is not None
    assert len(mgr.config.topics) >= 1
    assert mgr.config.llm.provider in ("deepseek", "local")


def test_topic_upsert_and_delete(tmp_path):
    config_file = tmp_path / "mock_config.yaml"
    mgr = ConfigManager(config_path=config_file)

    test_topic = TopicConfig(
        id="quantum_test",
        title="Quantum Computing",
        strategy_prompt="Focus on topological qubits and fault-tolerant architectures.",
        search_queries=["quantum computing topological qubits"]
    )

    mgr.upsert_topic(test_topic)
    assert mgr.get_topic("quantum_test") is not None
    assert mgr.get_topic("quantum_test").title == "Quantum Computing"

    deleted = mgr.delete_topic("quantum_test")
    assert deleted is True
    assert mgr.get_topic("quantum_test") is None


def test_raw_yaml_read_and_save(tmp_path):
    config_file = tmp_path / "mock_user_config.yaml"
    mgr = ConfigManager(config_path=config_file)

    yaml_text, path = mgr.get_raw_yaml()
    assert "topics:" in yaml_text
    assert "llm:" in yaml_text

    custom_yaml = """
llm:
  provider: "deepseek"
  model: "deepseek-reasoner"
  api_key: "sk-test1234"
topics:
  - id: "space_tech"
    title: "Space & Aerospace"
    icon: "🚀"
    enabled: true
    strategy_prompt: "Focus on commercial launch cadence and lunar landers."
    search_queries:
      - "space launch lunar mission propulsion"
"""
    updated_cfg = mgr.save_raw_yaml(custom_yaml)
    assert updated_cfg.llm.model == "deepseek-reasoner"
    assert len(updated_cfg.topics) == 1
    assert updated_cfg.topics[0].id == "space_tech"


def test_keyword_persistence_to_yaml(tmp_path):
    config_file = tmp_path / "test_keywords_config.yaml"
    mgr = ConfigManager(config_path=config_file)

    topic = TopicConfig(
        id="ai_chips",
        title="AI Hardware",
        strategy_prompt="Focus on GPUs and TPUs",
        search_queries=["Nvidia Blackwell", "Google TPU v6"]
    )
    mgr.upsert_topic(topic)

    # 1. Add new keywords to topic
    updated = mgr.add_keywords_to_topic("ai_chips", ["AMD MI325X", "Nvidia Blackwell", "Cerebras CS-3"])
    assert updated is not None
    # Verify deduplication (Nvidia Blackwell was already present)
    assert len(updated.search_queries) == 4
    assert "AMD MI325X" in updated.search_queries
    assert "Cerebras CS-3" in updated.search_queries

    # Verify YAML content on disk
    yaml_str, _ = mgr.get_raw_yaml()
    assert "AMD MI325X" in yaml_str
    assert "Cerebras CS-3" in yaml_str

    # 2. Remove a keyword
    removed = mgr.remove_keyword_from_topic("ai_chips", "Google TPU v6")
    assert removed is True
    assert "Google TPU v6" not in mgr.get_topic("ai_chips").search_queries

    # 3. Quick feed keyword to new topic
    new_t, is_new = mgr.quick_feed_keyword("Photonics Interconnect", topic_identifier="Optical Computing")
    assert is_new is True
    assert new_t.title == "Optical Computing"
    assert "Photonics Interconnect" in new_t.search_queries

