# Review framework

**Why:** Athena reviews must catch architecture and behavior regressions before lower-level checks
create false confidence. The shared framework keeps that standard consistent while each skill uses
the delivery channel appropriate to its scope.

## System at a glance

```mermaid
flowchart LR
    Request["Review request"] --> Scope{"Scope"}
    Scope --> Change["change-review"]
    Scope --> Issue["plan-issue / issue-review"]
    Scope --> Pull["pr-review"]
    Scope --> Repository["repo-review"]

    Change --> Framework["Shared framework\narchitecture → applicable checks → evidence"]
    Issue --> Framework
    Pull --> Framework
    Repository --> Framework

    Framework --> Findings["Deduplicated findings"]
    Findings --> Delivery{"Authorized delivery"}
    Delivery --> Console["Console or local annotations"]
    Delivery --> IssueComment["Actor-owned issue comment"]
    Delivery --> PullReview["One atomic PR review"]
    Delivery --> Tracker["Tracker and child work items"]
```

## Components

| Component | Owns | Read when |
| --- | --- | --- |
| [Shared contract](common.md) | Architecture gate, evidence, principles, findings, and delivery boundaries. | Every review. |
| [Language routing](language-routing.md) | Applicable language and toolchain profile. | The changed or inventoried surface contains code or build tooling. |
| [Behavior-first testing](behavior-first-testing.md) | Functional-test quality and false-confidence rules. | Tests, validation, or a plan are in scope. |
| [Issue planning](issue-planning.md) | Canonical plan identity and plan/review artifacts. | Planning or reviewing an issue. |
| [Repository scorecard](repository-scorecard.md) | Full-inventory repository criteria and scoring. | Reviewing a repository. |
| [Design-document structure](design-docs.md) | A clear order for architecture and design decisions. | Writing a new mutable design document. |

## Read order

1. Read the shared contract and repository guidance; establish architecture alignment first.
2. Classify the surface, then read only the applicable language and testing guidance.
3. Add the issue-planning or repository-scorecard contract when that scope applies.
4. Follow the invoking skill for scope resolution and its authorized delivery channel.

The diagram appears only here. Component documents use tables or prose when those communicate their
own decision more clearly.
