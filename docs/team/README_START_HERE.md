# TerraGuard — Team Documentation Guide

Welcome to the TerraGuard team documentation.

This directory contains the instructions that guide our coding agents. Every team member must follow these instructions to help us maintain a consistent architecture, avoid conflicts, and build a reliable, integrated system.

## 1. Before You Start

**Every team member must follow this order:**

1. Open and read `README_AGENT_RULES.md`.
2. Give the full contents of `README_AGENT_RULES.md` to your coding agent first.
3. Open the README corresponding to your assigned role and give its full contents to the same agent.
4. Give the agent your specific task and ask it to inspect the existing repository before making changes.
5. Review the agent's proposed changes and test results before committing or submitting them.

Do not skip the general rules or assume the agent already knows the project requirements.

## 2. Find Your Role

| Assigned role | Required role-specific README |
|---|---|
| Data Engineering & Geospatial Processing | `README_DATA_ENGINEERING.md` |
| Machine Learning & Evaluation | `README_MACHINE_LEARNING.md` |
| Backend Engineering | `README_BACKEND.md` |
| Frontend Engineering | `README_FRONTEND.md` |
| Team Lead & Scientific Integration | `README_SCIENTIFIC_COORDINATOR.md` |

**Important:** The general rules file must always be provided first, followed by the README for your assigned role.

## 3. Documentation Files

- `README_AGENT_RULES.md` — General rules for every coding agent.
- `README_DATA_ENGINEERING.md` — Data preparation, validation, and geospatial processing.
- `README_MACHINE_LEARNING.md` — Anomaly detection, baselines, and model evaluation.
- `README_BACKEND.md` — API development and backend integration.
- `README_FRONTEND.md` — User interface, visual design, and frontend integration.
- `README_SCIENTIFIC_COORDINATOR.md` — Architecture oversight, scientific methodology, and integration.

## 4. Rules Everyone Must Follow

- Inspect the existing repository before editing files.
- Do not change the architecture, frameworks, or directory structure without approval.
- Work only within your assigned component.
- Do not edit the root `README.md` unless explicitly authorised by the team lead.
- Do not change shared data schemas, API contracts, or model interfaces without agreement from the relevant team members.
- Do not introduce dependencies or modify root configuration files without approval.
- Test changes and report the actual results.
- Never present mock data or unverified model results as real.
- Use separate Git branches and submit changes for review before merging.

If your task requires changes outside your assigned role, discuss the proposed changes with the team lead and the relevant component owner first.

## 5. Working Together

TerraGuard is one integrated project, not a collection of independent components.

Before implementation depends on another component, coordinate with the relevant owner and agree on the required data formats, fields, API responses, and interfaces.

Report blockers early. Small, reviewed changes are preferred over large, uncoordinated changes.

## 6. Final Reminder

These files guide our work, but they do not replace communication, code review, or testing.

Our goal is to build TerraGuard as a scientifically responsible, professional, and reliable system while preserving the agreed architecture and respecting everyone's responsibilities.

**Understand the rules. Respect your role. Coordinate before changing shared interfaces. Test before submitting.**