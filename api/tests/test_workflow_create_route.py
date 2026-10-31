from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.workflow import router
from api.schemas.user_configuration import UserConfiguration
from api.services.auth.depends import get_user


def _make_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_user] = lambda: SimpleNamespace(
        id=1,
        provider_id="provider-1",
        selected_organization_id=11,
    )
    return app


def test_create_workflow_rejects_invalid_trigger_path_before_db_write():
    app = _make_test_app()
    client = TestClient(app)

    with patch("api.routes.workflow.db_client") as mock_db:
        response = client.post(
            "/workflow/create/definition",
            json={
                "name": "Support Agent",
                "workflow_definition": {
                    "nodes": [
                        {
                            "id": "trigger-1",
                            "type": "trigger",
                            "data": {"trigger_path": "support/west"},
                        }
                    ],
                    "edges": [],
                },
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["is_valid"] is False
    assert detail["errors"][0]["field"] == "data.trigger_path"
    assert "single URL path segment" in detail["errors"][0]["message"]
    assert mock_db.mock_calls == []


def _workflow_response(configurations):
    return SimpleNamespace(
        id=42,
        name="Tech4Help intake",
        status="active",
        created_at=datetime.now(UTC),
        current_definition_id=17,
        template_context_variables={},
        call_disposition_codes=None,
        workflow_configurations=configurations,
    )


def test_create_workflow_validates_and_saves_local_settings_before_returning():
    configurations = {
        "model_overrides": {
            "is_realtime": False,
            "llm": {"provider": "speaches", "base_url": "http://ollama:11434/v1"},
            "stt": {"provider": "speaches", "base_url": "http://speaches:8000/v1"},
            "tts": {"provider": "speaches", "base_url": "http://speaches:8000/v1"},
        }
    }
    client = TestClient(_make_test_app())
    with (
        patch("api.routes.workflow.db_client") as db,
        patch("api.routes.workflow.capture_event"),
    ):
        db.get_user_configurations = AsyncMock(return_value=UserConfiguration())
        db.create_workflow = AsyncMock(return_value=_workflow_response(configurations))
        response = client.post(
            "/workflow/create/definition",
            json={
                "name": "Tech4Help intake",
                "workflow_definition": {"nodes": [], "edges": []},
                "workflow_configurations": configurations,
            },
        )
    assert response.status_code == 200
    assert response.json()["workflow_configurations"] == configurations
    db.get_user_configurations.assert_awaited_once_with(1)
    db.create_workflow.assert_awaited_once_with(
        "Tech4Help intake",
        {"nodes": [], "edges": []},
        1,
        11,
        workflow_configurations=configurations,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm": {"provider": "speaches", "base_url": ""}},
        {"llm": "not a configuration"},
    ],
)
def test_create_workflow_rejects_invalid_model_settings_before_creation(overrides):
    client = TestClient(_make_test_app())
    with patch("api.routes.workflow.db_client") as db:
        db.get_user_configurations = AsyncMock(return_value=UserConfiguration())
        db.create_workflow = AsyncMock()
        response = client.post(
            "/workflow/create/definition",
            json={
                "name": "Invalid settings",
                "workflow_definition": {"nodes": [], "edges": []},
                "workflow_configurations": {"model_overrides": overrides},
            },
        )
    assert response.status_code == 422
    db.create_workflow.assert_not_awaited()


def test_create_workflow_without_settings_remains_compatible():
    client = TestClient(_make_test_app())
    with (
        patch("api.routes.workflow.db_client") as db,
        patch("api.routes.workflow.capture_event"),
    ):
        db.create_workflow = AsyncMock(return_value=_workflow_response({}))
        response = client.post(
            "/workflow/create/definition",
            json={
                "name": "Legacy client",
                "workflow_definition": {"nodes": [], "edges": []},
            },
        )
    assert response.status_code == 200
    db.get_user_configurations.assert_not_called()
    assert db.create_workflow.call_args.kwargs["workflow_configurations"] is None
