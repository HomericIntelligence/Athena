# Release `agent-contract-v1.0.0`

Use this runbook to publish the first immutable Athena agent contract. Do not create the tag from
the implementation pull request. Complete all validation before the first tag write.

## Preconditions

1. Confirm that Athena issue #162 and the issue #163 implementation pull request are merged.
2. Confirm that the issue #163 merge commit is the current `main` commit.
3. Confirm that GitHub verifies the signature on the exact `main` commit.
4. Confirm that successful `Required Checks` runs exist for these events:

   - the implementation pull request;
   - its merge group; and
   - the exact `main` commit.

5. Confirm that the aggregate evidence includes successful `agent-contract` and
   `required-checks-gate` checks.
6. Confirm that the local checkout has no changes.
7. Confirm that the operator can sign a Git tag and administer repository rulesets.
8. Confirm that the protected `release` environment contains
   `AGENT_CONTRACT_RULESET_PROOF_TOKEN`. Use a fine-grained token for this repository with
   Administration permission set to read-only. Give the token only to the live ruleset readback
   step.

Use one private temporary directory for the operation evidence:

```bash
release_run_dir="$(mktemp -d)"
git fetch origin main --tags
release_commit="$(git rev-parse origin/main)"
test "$(gh api repos/HomericIntelligence/Athena/commits/main --jq .sha)" = "$release_commit"
for provider_file in \
  .github/workflows/_agent-contract.yml \
  .github/actions/validate-agent-contract/action.yml \
  scripts/validate_agent_contract.py \
  scripts/policies/agent_contract.py \
  docs/principles/README.md \
  AGENTS.md; do
  test -f "$provider_file"
done
shasum -a 256 docs/principles/README.md \
  >"$release_run_dir/catalog-sha256.txt"
```

Run the pre-tag checks:

```bash
GITHUB_REPOSITORY=HomericIntelligence/Athena \
AGENT_CONTRACT_TAG=agent-contract-v1.0.0 \
AGENT_CONTRACT_COMMIT="$release_commit" \
uv run python scripts/ci_policy.py agent-contract-tracked-ruleset

GITHUB_REPOSITORY=HomericIntelligence/Athena \
AGENT_CONTRACT_TAG=agent-contract-v1.0.0 \
AGENT_CONTRACT_COMMIT="$release_commit" \
uv run python scripts/ci_policy.py agent-contract-release --pre-tag

uv run python scripts/ci_policy.py agent-contract-no-main-consumer
```

Stop when a command fails. Do not create the tag.

## Apply tag protection

Read the current ruleset list. Stop if more than one tag ruleset has the expected name. If one
ruleset exists, validate its complete live content and do not change it. If none exists, create it
from the tracked policy.

The live readback must use `AGENT_CONTRACT_RULESET_PROOF_TOKEN`. A response without
`bypass_actors` is an authority failure. It is not proof of policy drift or proof of a no-bypass
policy. Stop if the response does not contain this field.

```bash
gh api repos/HomericIntelligence/Athena/rulesets \
  >"$release_run_dir/rulesets-before.json"
tag_ruleset_id="$(jq -r '.[] | select(.name == "homeric-agent-contract-tags" and .target == "tag") | .id' "$release_run_dir/rulesets-before.json")"
test "$(printf '%s\n' "$tag_ruleset_id" | sed '/^$/d' | wc -l | tr -d ' ')" -le 1
```

Create the ruleset only when it is absent:

```bash
if test -n "$tag_ruleset_id"; then
  GITHUB_REPOSITORY=HomericIntelligence/Athena \
  uv run python scripts/ci_policy.py agent-contract-live-ruleset \
    >"$release_run_dir/tag-ruleset-readback.txt"
else
  gh api --method POST repos/HomericIntelligence/Athena/rulesets \
    --input .github/rulesets/homeric-agent-contract-tags.json \
    >"$release_run_dir/tag-ruleset-write.json"
  created_ruleset_id="$(jq -r .id "$release_run_dir/tag-ruleset-write.json")"
  test "$created_ruleset_id" != null
  if ! GITHUB_REPOSITORY=HomericIntelligence/Athena \
    uv run python scripts/ci_policy.py agent-contract-live-ruleset \
      >"$release_run_dir/tag-ruleset-readback.txt"; then
    gh api --method DELETE \
      "repos/HomericIntelligence/Athena/rulesets/$created_ruleset_id"
    test -z "$(gh api repos/HomericIntelligence/Athena/rulesets --jq \
      '.[] | select(.id == '"$created_ruleset_id"') | .id')"
    exit 1
  fi
fi
```

If an existing ruleset fails validation, stop without changing it. If creation or readback fails,
confirm that the exact new ruleset is absent before you continue. Do not create the tag after a
failed or incomplete ruleset operation.

## Create and validate the signed tag

Create one signed annotated tag at the exact green commit:

```bash
test "$(gh api "repos/HomericIntelligence/Athena/git/commits/$release_commit" --jq .verification.verified)" = true
git tag -s agent-contract-v1.0.0 "$release_commit" \
  -m "release: agent contract v1.0.0"
git verify-tag --raw agent-contract-v1.0.0
git push origin refs/tags/agent-contract-v1.0.0
```

Wait for the tag-triggered `Release` workflow. Its `agent-contract-release` job must pass. The
package and npm publication jobs must be skipped.

```bash
release_run_id="$(gh run list --repo HomericIntelligence/Athena --workflow Release --limit 20 --json databaseId,headSha,event --jq '.[] | select(.event == "push" and .headSha == "'"$release_commit"'") | .databaseId' | head -1)"
test -n "$release_run_id"
gh run watch "$release_run_id" --repo HomericIntelligence/Athena
```

Read the exact remote tag object and signature:

```bash
gh api repos/HomericIntelligence/Athena/git/ref/tags/agent-contract-v1.0.0 \
  >"$release_run_dir/tag-ref.json"
tag_object_sha="$(jq -r .object.sha "$release_run_dir/tag-ref.json")"
gh api "repos/HomericIntelligence/Athena/git/tags/$tag_object_sha" \
  >"$release_run_dir/tag-object.json"
test "$(jq -r .object.sha "$release_run_dir/tag-object.json")" = "$release_commit"
test "$(jq -r .verification.verified "$release_run_dir/tag-object.json")" = true

GITHUB_REPOSITORY=HomericIntelligence/Athena \
AGENT_CONTRACT_TAG=agent-contract-v1.0.0 \
AGENT_CONTRACT_COMMIT="$release_commit" \
uv run python scripts/ci_policy.py agent-contract-release

GITHUB_REPOSITORY=HomericIntelligence/Athena \
AGENT_CONTRACT_TAG=agent-contract-v1.0.0 \
uv run python scripts/ci_policy.py agent-contract-url-resolution
```

The URL check must resolve all 91 principle detail files through the GitHub contents API at the
release tag.

## Verify update and deletion rejection

These commands must fail. Each command uses the exact remote tag object as its lease. Stop if either
command succeeds.

```bash
if git push --force-with-lease="refs/tags/agent-contract-v1.0.0:$tag_object_sha" \
  origin "${release_commit}^:refs/tags/agent-contract-v1.0.0" \
  >"$release_run_dir/retarget-command.log" 2>&1; then
  git push --force origin "$tag_object_sha:refs/tags/agent-contract-v1.0.0"
  exit 1
fi
{
  printf '%s\n' "Retarget rejected as expected."
  cat "$release_run_dir/retarget-command.log"
} >"$release_run_dir/retarget-rejection.txt"

if git push --force-with-lease="refs/tags/agent-contract-v1.0.0:$tag_object_sha" \
  origin :refs/tags/agent-contract-v1.0.0 \
  >"$release_run_dir/deletion-command.log" 2>&1; then
  gh api --method POST repos/HomericIntelligence/Athena/git/refs \
    -f ref=refs/tags/agent-contract-v1.0.0 -f sha="$tag_object_sha"
  exit 1
fi
{
  printf '%s\n' "Deletion rejected as expected."
  cat "$release_run_dir/deletion-command.log"
} >"$release_run_dir/deletion-rejection.txt"
```

After a successful rejection test, read the tag again. Confirm that the object SHA did not change.

## Publish the release record

Generate the release body only from the verified live evidence:

```bash
GITHUB_REPOSITORY=HomericIntelligence/Athena \
AGENT_CONTRACT_TAG=agent-contract-v1.0.0 \
AGENT_CONTRACT_COMMIT="$release_commit" \
uv run python scripts/ci_policy.py agent-contract-release-record \
  --retarget-rejection-file "$release_run_dir/retarget-rejection.txt" \
  --deletion-rejection-file "$release_run_dir/deletion-rejection.txt" \
  --output "$release_run_dir/release-record.md"

gh release create agent-contract-v1.0.0 \
  --repo HomericIntelligence/Athena \
  --title "Athena agent contract v1.0.0" \
  --notes-file "$release_run_dir/release-record.md" \
  --verify-tag
```

If release creation fails, read the release before you retry. Create it only when it is absent. Use
`gh release edit --notes-file` when the release exists with incomplete notes.

Verify the published record:

```bash
GITHUB_REPOSITORY=HomericIntelligence/Athena \
AGENT_CONTRACT_TAG=agent-contract-v1.0.0 \
AGENT_CONTRACT_COMMIT="$release_commit" \
uv run python scripts/ci_policy.py agent-contract-release-record \
  --retarget-rejection-file "$release_run_dir/retarget-rejection.txt" \
  --deletion-rejection-file "$release_run_dir/deletion-rejection.txt" \
  --verify-release
```

The release record is complete only when it contains the tag object SHA, commit SHA, catalog
SHA-256, three required workflow run URLs, live ruleset digest, URL-resolution count, and both
rejection records. Each rejection record must contain GitHub error `GH013` and the exact protected
tag ref. A network, authentication, or local Git failure is not ruleset-rejection evidence.

## Recover the immutable `agent-contract-v1.0.0` release

Do not delete or retarget `agent-contract-v1.0.0`. Keep failed workflow run `34090390986` as
historical evidence. Use the fixed tooling on `main` to verify and publish the release record for
that tag. Use the next immutable tag, `agent-contract-v1.0.1`, to prove the repaired tag-triggered
workflow path.
