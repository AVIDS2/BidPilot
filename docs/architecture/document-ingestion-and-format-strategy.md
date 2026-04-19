# Document Ingestion and Format Strategy

## Goal

Define the supported file formats, ingestion pipeline stages, and parser behavior for `DocPilot`.

This document is the implementation guide for document intake beyond high-level architecture notes.

## Core principle

The system should normalize diverse document inputs into one stable internal representation.

Product logic should operate on the normalized representation, not on raw file-format quirks.

## Supported file formats

### Tier 1: first-class formats for early production

These formats should be supported in the earliest useful product version:

- `pdf`
- `docx`
- `txt`
- `md`
- `png`
- `jpg` / `jpeg`

### Tier 2: important but may rely on conversion or reduced fidelity

- `doc`
- `xlsx`
- `csv`
- `pptx`

### Tier 3: later or conditional support

- `xls`
- `ppt`
- `html`
- `eml`
- archives such as `zip` only when import rules are explicitly designed

## Format policy

### PDF

- must support both digitally generated and scanned PDFs
- OCR path is required for scanned content
- page-level layout and locator fidelity are important

### DOCX

- should preserve headings, tables, lists, and inline structure where practical
- should produce better structural fidelity than OCR-heavy PDF paths

### DOC

- support only through a controlled conversion or extraction path
- mark reduced trust or reduced fidelity when conversion is lossy

### TXT and Markdown

- treat as text-first sources with minimal layout expectations
- good for notes, templates, and promptable background material

### PNG and JPEG

- treat as image documents that require OCR
- preserve bounding boxes and page/image locator references where possible

### XLSX and CSV

- treat as structured tabular inputs, not just plain text blobs
- useful for scoring matrices, compliance sheets, and schedules

### PPTX

- treat as presentation material with lower initial priority than PDF and DOCX
- preserve slide boundaries when possible

## Ingestion pipeline stages

### 1. Registration

Store:

- file metadata
- storage location
- checksum
- MIME type
- original filename

### 2. Classification

Infer:

- format family
- likely source role
- language
- OCR requirement
- parser route

### 3. Extraction

Produce:

- raw extracted text
- layout structure
- table structure where available
- image/page references

### 4. Normalization

Transform extraction results into the canonical parsed document schema.

### 5. Chunking and indexing

Produce retrieval units with stable locators and metadata.

### 6. Requirement and evidence derivation

Generate structured artifacts from normalized content.

## Parser strategy

The parser layer must be adapter-based.

Recommended initial parser posture:

- one primary parser path for text-rich PDFs and DOCX
- one OCR-capable path for scans and images
- a normalization layer that hides parser-specific output differences

The product should not depend on one parser vendor's native schema.

## Output artifacts per source document

Each source document should produce some or all of:

- normalized parsed document record
- chunk records
- parser metadata
- extraction quality metadata
- optional preview artifacts

## Export targets

Initial export targets:

- markdown
- HTML-like structured render
- downloadable bundle artifact

Later export targets:

- `docx`
- `pdf`
- richer office-format outputs with stronger fidelity guarantees

## Quality requirements

- ingestion failures must be durable and inspectable
- parser version must be recorded
- OCR-required files must be distinguishable from text-native files
- chunk locators must remain traceable back to page, section, row, or bounding region when possible

## Non-goal

The product is not trying to become a full office-format editing engine in early phases.
