# Change Request

## Original Request

p1-provider-routing: make model_router.py read the routing table from config/providers.yml instead of the hardcoded dict, and route each target language in a multi-language batch independently (not just targets[0]).

Affected surface: services/model_router.py routing table + config/providers.yml routing section
Desired behavior: (1) config-driven routing — adding/changing routing rules requires only editing providers.yml, no code change; (2) per-target-language routing — resolve_route_groups() resolves each target_lang independently so mixed-language batches dispatch to the correct model per language.
Success criterion: a mixed-language batch (e.g. [vi, de, ko, ja]) dispatches each language to its correct model as defined in providers.yml; routing rule changes require no code edit; all existing tests pass and new routing tests pass.

## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
