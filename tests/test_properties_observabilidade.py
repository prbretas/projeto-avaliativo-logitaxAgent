"""Property tests para observabilidade.

Property 18: Structured logs contain all required fields.

Validates: Requirements 11.1
"""

import json
import logging

from hypothesis import given, settings
from hypothesis import strategies as st

from src.observability.logger import StructuredLogFormatter

# --- Property 18: Structured logs contain all required fields ---


@given(
    thread_id=st.text(
        min_size=1, max_size=36, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    node_name=st.sampled_from(
        ["parse_operacao", "sanitize_input", "route_regime", "simular_ano", "human_review"]
    ),
)
@settings(max_examples=50)
def test_structured_logs_contain_required_fields(thread_id, node_name):
    """Property 18: Each log contains thread_id, node name, ISO 8601 timestamp, duration_ms >= 0, status."""
    formatter = StructuredLogFormatter()

    # Create a log record with extra fields
    record = logging.LogRecord(
        name=f"node.{node_name}",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test log",
        args=None,
        exc_info=None,
    )
    record.thread_id = thread_id
    record.node_name = node_name
    record.duration_ms = 42.5
    record.status = "success"

    # Format and parse
    output = formatter.format(record)
    log_data = json.loads(output)

    # Verify required fields
    assert "timestamp" in log_data, "Missing timestamp"
    assert "T" in log_data["timestamp"], "Timestamp not ISO 8601"
    assert log_data["thread_id"] == thread_id, f"Wrong thread_id: {log_data['thread_id']}"
    assert log_data["node_name"] == node_name, f"Wrong node_name: {log_data['node_name']}"
    assert log_data["duration_ms"] >= 0, f"duration_ms negative: {log_data['duration_ms']}"
    assert log_data["status"] == "success", f"Wrong status: {log_data['status']}"
