---
contract: ci
summary: CI gate inventory, artifact retention, and rollback requirements.
owner: platform-team
surface: delivery-pipeline
schema-version: 0.1.0
last-changed: 2026-04-27
breaking-change-policy: deprecate-2-minors
---

# CI/CD Gate Contract

## Gate Inventory
| gate | tier | trigger | required | command/workflow | owner | artifact |
|---|---:|---|---:|---|---|---|
| contract-validate | 2+ | pre-commit / PR | yes | cdd-kit validate --contracts | platform-team | exit code 0 |
| change-gate | 2+ | pre-commit / PR | yes | cdd-kit gate <change-id> | platform-team | exit code 0 |
| unit-tests | 2+ | PR | yes | pytest tests/ | application-team | junit XML |

## Required Check Policy

## Informational Gate Promotion Policy

## Artifact Retention Policy

## Rollback Policy
