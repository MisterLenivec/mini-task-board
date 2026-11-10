"""The server serves its page, schema and only the intended static directory."""

import httpx
import pytest


def test_page_and_openapi_are_available(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Mini Task Board" in response.text

    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert schema.json()["info"]["title"] == "Mini Task Board"
    assert client.get("/docs").status_code == 200


def test_static_files_are_served_without_project_file_access(client):
    assert client.get("/static/index.html").status_code == 200
    assert client.get("/static/does-not-exist.css").status_code == 404
    response = client.get("/static/%2e%2e/%2e%2e/AGENTS.md")
    assert response.status_code == 404
    assert "постоянные инструкции" not in response.text


@pytest.mark.integration
def test_real_server_answers_http_requests(live_server):
    with httpx.Client(base_url=live_server, trust_env=False) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Mini Task Board" in response.text
        assert client.get("/openapi.json").json()["info"]["title"] == "Mini Task Board"
