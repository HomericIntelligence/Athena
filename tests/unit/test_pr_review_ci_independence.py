"""CI metadata cannot change source evidence or review delivery."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.unit import test_pr_review_contract_hardening as evidence_fixtures
from tests.unit import test_pr_review_go_delivery as delivery_fixtures

CI_STATES = ("PENDING", "FAILURE", "SKIPPED", "SUCCESS", None)


def ci_metadata(state: str | None) -> list[dict[str, str]]:
    """Create provider metadata for one CI state."""
    if state is None:
        return []
    return [
        {
            "__typename": "CheckRun",
            "name": "required",
            "status": "IN_PROGRESS" if state == "PENDING" else "COMPLETED",
            "conclusion": "" if state == "PENDING" else state,
        }
    ]


@pytest.fixture
def source_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Reject CI requests at the controlled provider boundary."""
    guard = """
if arguments[:2] == ["pr", "checks"] or (
    arguments[:1] == ["api"]
    and any(token in " ".join(arguments) for token in (
        "check-runs", "check-suites", "/status", "actions/", "deployments"
    ))
) or any("statusCheckRollup" in argument for argument in arguments):
    raise AssertionError("Source review requested CI evidence")
"""
    monkeypatch.setattr(
        evidence_fixtures,
        "FAKE_GH",
        evidence_fixtures.FAKE_GH.replace(
            "arguments = sys.argv[1:]",
            "arguments = sys.argv[1:]\n" + guard,
        ).replace(
            "print(json.dumps(sequence[min(count, len(sequence) - 1)]))",
            """metadata = sequence[min(count, len(sequence) - 1)]
    with open(os.environ["ATHENA_TEST_CI_READS"], "a") as receipt:
        receipt.write(json.dumps(metadata["statusCheckRollup"]) + chr(10))
    fields = arguments[arguments.index("--json") + 1].split(",")
    print(json.dumps({key: value for key, value in metadata.items() if key in fields}))""",
            1,
        ),
    )
    receipt = tmp_path / "ci-reads.jsonl"
    monkeypatch.setenv("ATHENA_TEST_CI_READS", str(receipt))
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-01-01T00:00:00Z")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-01-01T00:00:00Z")
    return receipt


@pytest.mark.parametrize("ci_state", CI_STATES)
def test_source_evidence_is_independent_of_ci_state(
    ci_state: str | None, source_provider: Path
) -> None:
    """CI changes between provider reads preserve all source evidence."""
    collector = evidence_fixtures.ImmutableEvidenceTests()
    before = evidence_fixtures.pull_request()
    after = copy.deepcopy(before)
    after["statusCheckRollup"] = ci_metadata(ci_state)
    assert after["statusCheckRollup"] == ci_metadata(ci_state)
    baseline, _, base_oid, head_oid = collector.run_collector([before, before])
    result, reads, actual_base, actual_head = collector.run_collector([before, after])

    assert baseline.returncode == 0, baseline.stderr
    assert result.returncode == 0, result.stderr
    observed = [json.loads(line) for line in source_provider.read_text().splitlines()]
    assert observed == [[], [], [], ci_metadata(ci_state)]
    assert reads == 2
    assert (actual_base, actual_head) == (base_oid, head_oid)
    assert json.loads(result.stdout) == json.loads(baseline.stdout)
    assert "check_evidence" not in json.loads(result.stdout)


@pytest.fixture
def review_case() -> delivery_fixtures.PrReviewGoDeliveryTests:
    """Reuse the controlled delivery history and proof fixtures."""
    fixture = delivery_fixtures.PrReviewGoDeliveryTests()
    fixture.delivery = delivery_fixtures.load_module()
    fixture.setUp()
    return fixture


class CiForge(delivery_fixtures.FakeForge):
    """Keep provider CI metadata separate from the source snapshot."""

    def __init__(
        self, module: ModuleType, *, threads: tuple[Any, ...], ci_state: str | None
    ) -> None:
        super().__init__(module, threads=threads)
        self.ci_metadata = ci_metadata(ci_state)
        self.observed_ci_metadata: list[list[dict[str, str]]] = []

    def snapshot(self) -> Any:
        self.observed_ci_metadata.append(copy.deepcopy(self.ci_metadata))
        return super().snapshot()


def prepare_delivery(
    fixture: delivery_fixtures.PrReviewGoDeliveryTests,
    verdict: str,
    ci_state: str | None,
) -> tuple[CiForge, Callable[[], Any]]:
    """Keep CI metadata outside the source snapshot and review proof."""
    module = fixture.delivery
    if verdict == "GO":
        thread = fixture.owned_thread()
        forge = CiForge(module, threads=(thread,), ci_state=ci_state)
        proof = fixture.v1_manifest(thread)
        fixture.add_history(forge, proof)

        def deliver() -> Any:
            return module.deliver_go_v1(forge, fixture.binding(), proof)

    else:
        proof, record = fixture.no_go_proof(
            finding_evidence=("The bound source omits the required input check.",)
        )
        forge = CiForge(
            module,
            threads=fixture.carrier_threads(proof.state_envelope, proof.review_id),
            ci_state=ci_state,
        )
        forge.labels = {"state:implementation-go", "enhancement"}
        forge.reviews.append(record)

        def deliver() -> Any:
            return module.deliver_no_go(forge, fixture.binding(), proof)

    return forge, deliver


@pytest.mark.parametrize("verdict", ("GO", "NO-GO"))
@pytest.mark.parametrize("ci_state", CI_STATES)
def test_ci_state_does_not_change_verdict_or_delivery(
    review_case: delivery_fixtures.PrReviewGoDeliveryTests,
    verdict: str,
    ci_state: str | None,
) -> None:
    """Valid proofs retain their verdict and exclusive label in every CI state."""
    forge, deliver = prepare_delivery(review_case, verdict, ci_state)
    assert forge.ci_metadata == ci_metadata(ci_state)
    binding = review_case.binding()
    result = deliver()

    label = "state:implementation-" + verdict.lower()
    assert forge.observed_ci_metadata
    assert all(item == ci_metadata(ci_state) for item in forge.observed_ci_metadata)
    assert result.status == "delivered"
    assert result.label == label
    assert result.observed_head_oid == binding.head_oid
    assert forge.labels == {label, "enhancement"}
    carrier = review_case.delivery.review_exchange.extract_carrier(
        forge.reviews[-1].body
    )
    assert carrier["state"]["verdict"] == verdict


@pytest.mark.parametrize("verdict", ("GO", "NO-GO"))
def test_review_delivery_does_not_query_ci(
    review_case: delivery_fixtures.PrReviewGoDeliveryTests,
    verdict: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delivery completes when external command execution is forbidden."""
    forge, deliver = prepare_delivery(review_case, verdict, "PENDING")

    def reject_command(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Delivery attempted an external command")

    monkeypatch.setattr("subprocess.run", reject_command)
    assert deliver().status == "delivered"
    assert forge.observed_ci_metadata


@pytest.mark.parametrize("verdict", ("GO", "NO-GO"))
def test_stale_source_still_prevents_delivery(
    review_case: delivery_fixtures.PrReviewGoDeliveryTests, verdict: str
) -> None:
    """Successful CI cannot authorize a stale source binding."""
    forge, deliver = prepare_delivery(review_case, verdict, "SUCCESS")
    labels = set(forge.labels)
    forge.head_oid = "c" * 40

    with pytest.raises(review_case.delivery.DeliveryError):
        deliver()

    assert forge.labels == labels
    assert forge.events == ["read"]
