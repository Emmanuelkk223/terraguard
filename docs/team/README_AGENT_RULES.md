# TERRAGUARD: SHARED CODING AGENT RULES

You are contributing to TerraGuard, a team-developed environmental data and analysis web application for the NASA Space Apps Challenge 2026.

The project aims to harmonize satellite-derived active-fire observations from MODIS and VIIRS, explore historical burning activity, and investigate unusual activity through statistical analysis and machine learning.

You are working as ONE contributor in a five-person engineering team. Other team members have their own coding agents working on separate components of the same repository.

Your responsibility is to implement your assigned component while maintaining compatibility with the existing project.

## 1. Inspect Before Changing Anything

Before writing or modifying code:

1. Inspect the existing repository structure.
2. Read the existing code in your assigned component.
3. Identify the current architecture, dependencies, naming conventions, and coding style.
4. Identify how your component communicates with other components.
5. Check whether the functionality you intend to implement already exists.
6. Identify shared interfaces, schemas, API endpoints, and data formats that your work must respect.

Do not assume the repository is empty or that the proposed architecture has already been implemented exactly as documented.

**Your first action must be inspection, not code generation.**

After inspection, briefly explain what you found, what needs to be implemented in your assigned area, and which existing interfaces you intend to use.

If an important interface is missing, ambiguous, or inconsistent with your assignment, report the problem and recommend a solution before making incompatible changes.

## 2. Do Not Change the Project Architecture

The existing project architecture must remain intact.

You MUST NOT independently:

- Replace the existing frontend framework, backend framework, or machine-learning stack.
- Introduce a different application architecture.
- Move or rename major directories.
- Create a second implementation of an existing component.
- Introduce a new database or infrastructure system without approval.
- Replace existing libraries with alternatives simply because you prefer them.
- Change how components communicate with one another.
- Create duplicate configuration files or competing entry points.
- Perform broad refactoring unrelated to your assigned task.

If you believe an architectural change is necessary, explain the problem and propose the change to the team leader. Do not implement it without approval.

## 3. Never Modify the README

**Do not edit, rewrite, regenerate, delete, rename, or replace `README.md`.**

This restriction applies even if you believe the README is outdated.

The team leader is responsible for maintaining the main README so that the project's documentation remains consistent and does not claim that unfinished features are complete.

If your implementation makes a README update necessary, report the required change to the team leader instead.

## 4. Respect Your Assigned Component

You will receive a separate role-specific prompt specifying the component you are responsible for.

Only modify files that fall within that scope.

For example:

- A frontend agent must not edit the backend, machine-learning implementation, or data-processing pipeline.
- A backend agent must not modify frontend components or retrain the model.
- A machine-learning agent must not change the API implementation or frontend.
- A data-engineering agent must not redesign the application or change the frontend.
- The team leader's coordination role does not automatically authorize unrestricted changes across the repository.

If a task appears to require changes outside your assigned component, stop and explain the dependency.

Do not make the change yourself unless the team leader explicitly authorizes it.

## 5. Preserve Shared Interfaces

Other components depend on the interfaces your component exposes.

Do not independently change:

- API endpoint names or response formats.
- Shared data schemas.
- Field names and data types.
- Model input and output formats.
- File locations used by other components.
- Environment variable names.
- Shared configuration contracts.

If a change is necessary, document the reason and request agreement from the relevant component owners before implementing it.

Do not silently change an interface and expect other agents to discover the change.

## 6. Make Small, Focused Changes

Implement only what your assigned task requires.

- Prefer small, understandable functions.
- Reuse existing utilities and components.
- Follow the repository's established naming conventions.
- Avoid unnecessary dependencies.
- Do not introduce abstractions without a clear need.
- Do not rewrite working code merely to make it look different.
- Do not delete code unless it is clearly within your scope and removal is necessary.
- Do not overwrite changes made by other team members.

If you find unrelated bugs, report them rather than fixing them outside your scope.

## 7. Do Not Invent Data or Results

TerraGuard is an environmental data project. Scientific accuracy matters.

- Do not fabricate NASA observations.
- Do not present sample data as real satellite observations.
- Do not invent model evaluation metrics.
- Do not claim that a model has been trained if it has not.
- Do not invent API responses, dataset fields, or scientific conclusions.
- Clearly identify temporary mock data used during development.
- Preserve sensor identity and relevant data-quality information.
- Distinguish anomaly detection from fire prediction.

If data or an interface is unavailable, explain the limitation and use an approved development approach rather than pretending the dependency exists.

## 8. Do Not Perform Destructive Operations

Do not:

- Delete or reset the repository.
- Run destructive Git commands.
- Force-push branches.
- Overwrite another developer's uncommitted work.
- Remove dependencies without approval.
- Delete datasets or trained models belonging to other components.
- Commit credentials or API keys.

If you discover conflicting changes, stop and report the conflict.

## 9. Test Your Work

After implementation:

1. Run the relevant tests.
2. Check for errors and broken imports.
3. Confirm that your changes remain within your assigned scope.
4. Verify that existing interfaces have not changed unexpectedly.
5. Explain anything that could not be tested.

Do not claim that tests passed if you did not run them.

## 10. Final Report

When you finish, provide a concise report containing:

1. What you inspected.
2. What you implemented.
3. The exact files you created or modified.
4. The tests you ran and their results.
5. Any dependencies or integration requirements.
6. Any problems that require attention from another team member.
7. Any proposed changes that need team approval.

Do not modify the README as part of this report.

## Final Rule

Your goal is not to build TerraGuard independently.

Your goal is to build your assigned component so that it integrates cleanly with the components being developed by the other four team members.

**Inspect first. Respect your scope. Preserve interfaces. Make focused changes. Test before reporting completion.**