"""Tests for Admin Role Configuration and Learner Session Inheritance.

Validates:
1. GET /api/admin/configurations returns all published role configurations.
2. GET /api/admin/configurations/{role} returns configuration or defaults.
3. POST /api/admin/configurations saves and returns configuration.
4. Storage persistence across calls.
5. Learner session creation without persona configuration automatically inherits published admin configuration.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.storage_service import storage

client = TestClient(app)


def test_get_admin_configurations_endpoint():
    response = client.get("/api/admin/configurations")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_get_admin_configuration_for_role_endpoint():
    response = client.get("/api/admin/configurations/CTO")
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "CTO"
    assert "traits" in data
    assert "preset" in data
    assert "voice" in data


def test_save_and_retrieve_admin_configuration():
    payload = {
        "role": "CTO",
        "preset": "STRICT",
        "traits": {
            "skepticism": 0.88,
            "strictness": 0.92,
            "kindness": 0.25,
            "directness": 0.85,
            "patience": 0.30,
            "domain_depth": 0.95
        },
        "experience": "Advanced",
        "style": "Stress Interview",
        "voice": "am_michael",
        "conversation_overview": "Candidate must pitch and defend a distributed Kafka architecture against tough CTO scrutiny.",
        "custom_scenario": "Admin test custom scenario for high-throughput scaling.",
        "scenario_title": "Q4 Scale Pitch",
        "challenge_tags": ["20k TPS", "mTLS"]
    }

    # Save via POST
    post_res = client.post("/api/admin/configurations", json=payload)
    assert post_res.status_code == 200
    saved = post_res.json()
    assert saved["role"] == "CTO"
    assert saved["preset"] == "STRICT"
    assert saved["traits"]["skepticism"] == 0.88
    assert saved["voice"] == "am_michael"
    assert saved["conversation_overview"] == "Candidate must pitch and defend a distributed Kafka architecture against tough CTO scrutiny."
    assert saved["experience"] == "Advanced"
    assert saved["style"] == "Stress Interview"

    # Retrieve via GET
    get_res = client.get("/api/admin/configurations/CTO")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["role"] == "CTO"
    assert retrieved["preset"] == "STRICT"
    assert retrieved["traits"]["skepticism"] == 0.88
    assert retrieved["voice"] == "am_michael"
    assert retrieved["conversation_overview"] == "Candidate must pitch and defend a distributed Kafka architecture against tough CTO scrutiny."


def test_learner_session_inherits_admin_configuration():
    # Configure CEO as admin
    ceo_payload = {
        "role": "CEO",
        "preset": "EXECUTIVE",
        "traits": {
            "skepticism": 0.80,
            "strictness": 0.85,
            "kindness": 0.40,
            "directness": 0.90,
            "patience": 0.35,
            "domain_depth": 0.75
        },
        "experience": "Expert",
        "style": "Executive",
        "voice": "am_onyx",
        "custom_scenario": "",
        "scenario_title": "Enterprise AI ROI",
        "challenge_tags": ["Valuation", "EBITDA"]
    }
    client.post("/api/admin/configurations", json=ceo_payload)

    # Now create learner session without persona configuration
    session_res = client.post("/api/session", json={
        "topic": "Strategic Value Pitch",
        "role": "CEO",
        "scenario": "Meeting to align on business ROI",
        "experience": "Intermediate",
        "style": "Professional"
    })
    assert session_res.status_code == 200
    data = session_res.json()
    session_id = data["session_id"]
    assert session_id is not None

    # Verify that the session stored in SQLite has the admin-configured traits
    stored_cfg = storage.get_persona_configuration(session_id)
    assert stored_cfg is not None
    assert stored_cfg["traits"]["skepticism"] == 0.80
    assert stored_cfg["traits"]["strictness"] == 0.85


def test_delete_admin_configuration():
    # Save HR configuration
    hr_payload = {
        "role": "HR",
        "preset": "FRIENDLY",
        "traits": {
            "skepticism": 0.30,
            "strictness": 0.40,
            "kindness": 0.85,
            "directness": 0.50,
            "patience": 0.80,
            "domain_depth": 0.70
        },
        "experience": "Intermediate",
        "style": "Friendly",
        "voice": "bf_emma",
        "conversation_overview": "Talent retention and leveling calibration meeting.",
    }
    client.post("/api/admin/configurations", json=hr_payload)
    assert storage.get_admin_role_configuration("HR") is not None

    # Delete via DELETE endpoint
    del_res = client.delete("/api/admin/configurations/HR")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["success"] is True
    assert del_data["role"] == "HR"

    # Verify deleted in SQLite
    assert storage.get_admin_role_configuration("HR") is None


def test_multiple_personas_per_role():
    # 1. Fetch all personas - should have seeded defaults
    all_res = client.get("/api/admin/personas")
    assert all_res.status_code == 200
    all_personas = all_res.json()
    assert isinstance(all_personas, list)
    assert len(all_personas) >= 12

    # 2. Fetch personas for CTO specifically
    cto_res = client.get("/api/admin/personas/by-role/CTO")
    assert cto_res.status_code == 200
    cto_personas = cto_res.json()
    assert isinstance(cto_personas, list)
    assert len(cto_personas) >= 3
    # Check that titles and overviews are distinct
    titles = [p["title"] for p in cto_personas]
    assert len(set(titles)) == len(titles)

    # 3. Create a brand new custom CTO persona
    new_cto_id = "cto-cost-optimizer-test"
    new_cto_payload = {
        "id": new_cto_id,
        "role": "CTO",
        "title": "CTO - Cloud Cost & Efficiency Architect",
        "preset": "STRICT",
        "traits": {
            "skepticism": 0.95,
            "strictness": 0.90,
            "kindness": 0.20,
            "directness": 0.90,
            "patience": 0.20,
            "domain_depth": 0.99
        },
        "experience": "Advanced",
        "style": "Stress Interview",
        "voice": "am_michael",
        "conversation_overview": "Defending annual AWS spend against strict 40% reduction target.",
        "custom_scenario": "You are the Chief Technology Officer (CTO). The candidate is presenting an aggressive cloud cost containment plan to you. Scrutinize technical tradeoffs and platform stability.",
        "scenario_title": "FinOps Cloud Cost Negotiation",
        "challenge_tags": ["FinOps", "Unit Economics"]
    }
    create_res = client.post("/api/admin/personas", json=new_cto_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"] == new_cto_id
    assert created["title"] == "CTO - Cloud Cost & Efficiency Architect"

    # 4. Verify it appears in by-role query
    cto_after = client.get("/api/admin/personas/by-role/CTO").json()
    found = any(p["id"] == new_cto_id for p in cto_after)
    assert found is True

    # 5. Clean up by deleting the test persona
    del_res = client.delete(f"/api/admin/personas/{new_cto_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True


def test_seeded_personas_agent_perspective():
    """Verify all 12 seeded persona scenarios are written from the agent's perspective, NOT the candidate's."""
    seeded_ids = [
        "cto-kafka", "cto-tech-debt", "cto-security",
        "ceo-ai-platform", "ceo-cloud-spend", "ceo-security-risk",
        "hr-culture-friction", "hr-talent-scaling", "hr-performance-reset",
        "sales-competitive-displacement", "sales-procurement-negotiation", "sales-stakeholder-consensus"
    ]

    res = client.get("/api/admin/personas")
    assert res.status_code == 200
    personas = res.json()
    persona_map = {p["id"]: p for p in personas}

    for sid in seeded_ids:
        assert sid in persona_map, f"Seeded persona {sid} missing"
        p = persona_map[sid]
        custom_scenario = p.get("custom_scenario", "")
        # Must NOT be from candidate perspective
        assert not custom_scenario.startswith("You are meeting with"), (
            f"Persona {sid} has wrong candidate perspective: {custom_scenario[:50]}"
        )
        # Must prime the agent in their executive role ("You are the...")
        assert custom_scenario.startswith("You are the "), (
            f"Persona {sid} does not prime agent persona: {custom_scenario[:50]}"
        )


def test_session_uses_admin_custom_scenario():
    """Verify that when a learner selects an admin persona, the session overrides effective_scenario with custom_scenario."""
    res = client.post("/api/session", json={
        "topic": "Healthcare Cloud Pitch",
        "role": "CTO",
        "scenario": "Learner briefing text that should not override agent context",
        "admin_configuration_id": "cto-security",
        "experience": "Advanced",
        "style": "Stress Interview"
    })
    assert res.status_code == 200
    data = res.json()
    session_id = data["session_id"]

    # Verify stored session scenario in DB is the agent's custom_scenario
    session = storage.get_session(session_id)
    assert session is not None
    assert "You are the Chief Technology Officer (CTO) of a healthcare technology company" in session["scenario"]


def test_session_derives_topic_when_omitted():
    """Verify Option A: POST /api/session without Stage 1 topic derives topic from the admin scenario."""
    res = client.post("/api/session", json={
        "role": "CTO",
        "scenario": "Learner briefing text",
        "admin_configuration_id": "cto-kafka",
        "experience": "Advanced",
        "style": "Stress Interview"
    })
    assert res.status_code == 200
    session_id = res.json()["session_id"]

    session = storage.get_session(session_id)
    assert session is not None
    assert session["topic"] == "High-Throughput Architecture Migration"




