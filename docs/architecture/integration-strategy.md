# Integration Strategy

## Goal

Keep all fast-moving AI dependencies replaceable while preserving one stable product core.

## Adapter categories

### Model provider adapter

Responsibilities:

- chat completion
- structured generation
- embeddings
- optional reasoning metadata

Contract requirements:

- provider name
- model name
- request options
- normalized response
- cost metadata
- raw provider payload

### Parser adapter

Responsibilities:

- file ingestion
- OCR
- layout extraction
- table extraction
- normalized parse output

### Retriever adapter

Responsibilities:

- dense retrieval
- lexical retrieval
- hybrid merge
- reranking

### Tool adapter

Responsibilities:

- internal tool invocation
- external API invocation
- normalized tool result payloads
- timeout and retry policy

### MCP adapter

Responsibilities:

- connect to external MCP servers
- expose internal tools as MCP servers where useful
- translate MCP resources, prompts, and tools into internal tool contracts

Rule:

MCP is an external interoperability layer. Internal workflows must not depend on MCP semantics as the source of truth.

## Provider policy

The system must support:

- OpenAI-compatible providers
- domestic providers behind the same normalized interface
- local or private models later without changing domain services

## Versioning policy

Every execution run stores:

- provider identifier
- model identifier
- adapter version
- parser version
- prompt template version when applicable

This preserves reproducibility even when providers change behavior.

## Failure policy

Adapters must return normalized error types:

- configuration error
- transient provider error
- auth error
- validation error
- quota/rate limit error

Domain services should not branch on raw provider-specific messages.
