"""Conversation decisions retain provenance without inventing forge authority."""

from __future__ import annotations

from typing import Any

import pytest

from tests.unit.test_review_exchange import load_module


def context() -> dict[str, Any]:
    return {
        "schema_id": "athena.review-exchange.authority",
        "schema_version": 1,
        "action": "reframe",
        "target": {
            "provider": "github",
            "repository": "owner/repo",
            "number": 7,
            "url": "https://github.com/owner/repo/pull/7",
        },
        "exchange_id": "exchange-7",
        "requirements_sha256": "a" * 64,
        "prior_state_sha256": None,
        "supersedes_state_sha256": "b" * 64,
        "decisions": [],
    }


def test_conversation_decision_preserves_context_and_log_reference() -> None:
    module = load_module()
    record = module.conversation_authority_record(
        context(),
        log_id="session-7",
        message_id="message-3",
        decision_text="Use the revised requirements.",
        forge_unavailable_reason="The decision maker cannot post to the forge.",
    )
    body = module.canonical_json(record)
    receipt = {"reference": "comment:7", "sha256": module.sha256_text(body)}
    verified = module.verify_authority_record(body, receipt, context())
    assert verified["conversation"]["log_id"] == "session-7"
    assert verified["conversation"]["message_id"] == "message-3"
    assert verified["conversation"]["decision_sha256"] == module.sha256_text(
        "Use the revised requirements."
    )
    assert "Use the revised requirements." not in body


@pytest.mark.parametrize(
    "field", ["log_id", "message_id", "decision_text", "forge_unavailable_reason"]
)
def test_conversation_decision_requires_real_reference_and_fallback_reason(
    field: str,
) -> None:
    module = load_module()
    args = {
        "log_id": "session-7",
        "message_id": "message-3",
        "decision_text": "Proceed.",
        "forge_unavailable_reason": "Forge posting is unavailable.",
    }
    args[field] = ""
    with pytest.raises(module.ProtocolError):
        module.conversation_authority_record(context(), **args)


def test_conversation_metadata_cannot_authorize_another_target() -> None:
    module = load_module()
    record = module.conversation_authority_record(
        context(),
        log_id="session-7",
        message_id="message-3",
        decision_text="Proceed.",
        forge_unavailable_reason="Forge posting is unavailable.",
    )
    body = module.canonical_json(record)
    expected = context()
    expected["target"] = {**expected["target"], "number": 8}
    with pytest.raises(module.ProtocolError, match="action context"):
        module.verify_authority_record(
            body,
            {"reference": "comment:7", "sha256": module.sha256_text(body)},
            expected,
        )
