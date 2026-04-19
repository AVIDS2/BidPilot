# Normalized Document Schema

## Goal

Define the canonical internal schema for parsed documents so ingestion, retrieval, evidence, and downstream drafting operate on stable structures.

This schema is conceptual first. Implementation may map it to relational rows, JSON columns, or object payloads as appropriate.

## Core rule

Raw parser output is never the product contract.

Every parser route must normalize into one canonical structure.

## Canonical parsed document shape

Each normalized parsed document should conceptually include:

- document metadata
- structural blocks
- tables
- media references
- document-level quality metadata

## Document metadata

Suggested fields:

- `document_id`
- `project_id`
- `bundle_id`
- `source_document_id`
- `format`
- `language`
- `page_count`
- `parser_name`
- `parser_version`
- `ocr_used`
- `created_at`

## Structural blocks

Blocks are the main reading-order units for text and layout.

Suggested block fields:

- `block_id`
- `page_number`
- `block_type`
- `text`
- `heading_level`
- `parent_block_id`
- `order_index`
- `bbox`
- `style_hint`
- `source_locator`

Typical block types:

- `title`
- `heading`
- `paragraph`
- `list_item`
- `table_caption`
- `footer`
- `header`
- `note`

## Tables

Suggested table fields:

- `table_id`
- `page_number`
- `title`
- `columns`
- `rows`
- `bbox`
- `source_locator`

Suggested row shape:

- `row_index`
- `cells`

Suggested cell shape:

- `column_index`
- `text`
- `row_span`
- `col_span`
- `bbox`

## Media references

Suggested fields:

- `media_id`
- `page_number`
- `media_type`
- `bbox`
- `caption_text`
- `storage_key`

## Quality metadata

Suggested fields:

- `extraction_quality`
- `ocr_confidence`
- `warnings`
- `normalization_notes`

## Chunk schema

Chunks should be derived from normalized structure, not raw plain text slicing alone.

Suggested chunk fields:

- `chunk_id`
- `project_id`
- `source_document_id`
- `parsed_asset_id`
- `chunk_index`
- `chunk_type`
- `content`
- `content_markdown`
- `token_estimate`
- `metadata_json`
- `locator_json`
- `embedding`

Suggested chunk metadata:

- `page_numbers`
- `section_path`
- `table_id` when relevant
- `language`
- `source_role`
- `trust_level`

## Evidence schema guidance

Evidence should point back to stable chunk and source locators.

Suggested evidence fields:

- `evidence_id`
- `project_id`
- `source_document_id`
- `chunk_id`
- `quote_text`
- `summary_text`
- `locator_json`
- `confidence`
- `created_at`

Suggested locator contents:

- `page_number`
- `block_id`
- `table_id`
- `row_index`
- `bbox`

## Why this matters

This normalized schema is what keeps:

- retrieval stable
- evidence references durable
- review traceability consistent
- parser replacement possible later

## Change rule

If normalized document structure changes materially, update this document, the data model doc, and any contract docs touched by the change.
