# Required repository resolution

Athena has two hard repository dependencies. Skills fail closed when a required dependency cannot
be resolved, authenticated, checked out, or updated.

## Owner precedence

For dependency `<Repository>` with environment override `<OWNER_VARIABLE>`:

1. If `<OWNER_VARIABLE>` is non-empty, use `<value>/<Repository>`. An invalid explicit override is
   an error and does not fall back.
2. Otherwise determine the current repository owner with:

   ```bash
   gh repo view --json owner --jq .owner.login
   ```

   Prefer `<current-owner>/<Repository>` only when GitHub confirms it is a fork whose
   `parent.full_name` is `HomericIntelligence/<Repository>`.
3. Otherwise use `HomericIntelligence/<Repository>`.

Do not select a same-named repository that is not a verified fork.

The fork decision must inspect repository metadata, not naming alone:

```bash
current_owner=$(gh repo view --json owner --jq '.owner.login')
gh api "repos/${current_owner}/<Repository>" \
  --jq '.fork == true and .parent.full_name == "HomericIntelligence/<Repository>"'
```

Only the literal result `true` qualifies. A missing same-owner candidate is normal and falls back
to the default; an API/authentication error that prevents a trustworthy decision is fatal.

## Dependencies

| Purpose | Repository | Override | Checkout |
| --- | --- | --- | --- |
| Knowledge | `Mnemosyne` | `HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER` | `$HOME/.agent_brain/knowledge` |
| Automation | `Hephaestus` | `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER` | `$HOME/.agent_brain/automation` |

## Checkout contract

Requirements are authenticated `gh`, `git`, and network access. Create `$HOME/.agent_brain` when
needed. Clone the resolved repository when its checkout is absent. For an existing checkout:

- Require `origin` to identify the resolved `owner/repository`.
- Refuse to overwrite local changes or silently rewrite the remote.
- Fetch `origin`, resolve its default branch, and fast-forward it.
- Report the resolved repository and commit SHA.

An authentication failure, missing repository, invalid fork relationship, unexpected origin,
conflicting local state, clone failure, fetch failure, or fast-forward failure is fatal.

Mnemosyne writes use isolated worktrees and always end in a pull request. Hephaestus is read or
executed from its canonical checkout; Athena skills never edit it unless the user explicitly asks
for a Hephaestus change.
