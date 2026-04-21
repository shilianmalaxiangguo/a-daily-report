# Persist Module

## Purpose

Store report outputs and execution artifacts.

## Responsibilities

- Save markdown documents, snapshots, and replay artifacts.
- Preserve output state without changing decisions.

## Boundaries

- May read `rendered` and `artifacts`.
- Must not alter inference or report content.

