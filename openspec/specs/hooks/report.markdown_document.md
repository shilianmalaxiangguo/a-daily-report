# report.markdown_document

## Purpose

Render the final markdown document from assembled report sections.

## Requires

- `sections.*`
- `derived.*`

## Provides

- `rendered.markdown_document`
- `diagnostics.rendering.markdown_document`

## Forbidden Reads

- `raw.*`
- `normalized.*`

## Failure Policy

- degradable

## Diagnostics Fields

- `status`
- `duration_ms`
- `confidence`
- `warnings`

