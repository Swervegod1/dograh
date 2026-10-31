"""Validate the actual shipped starter graphs against Dograh's runtime contract."""

import json
from pathlib import Path

import pytest

from api.services.workflow.dto import ReactFlowDTO
from api.services.workflow.workflow_graph import WorkflowGraph

CATALOG = json.loads(
    (
        Path(__file__).resolve().parents[2] / "ui/src/lib/tech4help/catalog.json"
    ).read_text()
)


@pytest.mark.parametrize("starter", CATALOG["starters"], ids=lambda item: item["id"])
def test_tech4help_starter_is_valid_and_extracts_on_exit(starter):
    dto = ReactFlowDTO.model_validate(starter["workflow"]["workflow_definition"])
    WorkflowGraph(dto)
    start = next(node for node in dto.nodes if node.type == "startCall")
    assert start.data.extraction_enabled
    variables = {
        variable.name: variable.type for variable in start.data.extraction_variables
    }
    assert variables["follow_up_consent"] == "boolean"
    assert variables["intake_outcome"] == "string"
    assert variables["intake_summary"] == "string"
    assert len(variables) == len(start.data.extraction_variables)
    assert any(edge.source == start.id for edge in dto.edges)
    # No external actions, phone triggers or paid analysis integrations are shipped.
    assert {node.type for node in dto.nodes} == {"startCall", "endCall", "globalNode"}
