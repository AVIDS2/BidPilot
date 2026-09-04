# AI Provider Integrations

This document records the provider presets exposed in the BidPilot provider
settings page. Provider API keys are never stored in frontend state beyond the
active form submission. Saved keys are encrypted by the backend secret layer.

## Endpoint Rules

- `openai` protocol means an OpenAI-compatible chat-completions API.
- `anthropic` protocol means the Anthropic Messages API shape.
- Versioned provider paths are authoritative. If a provider base URL ends in a
  version segment such as `/v1`, `/api/v3`, `/api/paas/v4`, or
  `/compatible-mode/v1`, the backend must not append another `/v1`.
- DeepSeek's official OpenAI-compatible base is kept as
  `https://api.deepseek.com`; the backend appends `/chat/completions` or
  `/models` directly.
- For unknown bare OpenAI-compatible hosts, the backend still appends `/v1`
  because that is the most common OpenAI-compatible gateway convention.

## Presets

| Provider | Protocol | Base URL | Default model | Documentation | Notes |
| --- | --- | --- | --- | --- | --- |
| Custom OpenAI | OpenAI-compatible | User supplied | `gpt-4o` | User gateway docs | For enterprise proxy, local gateway, or provider not listed here. |
| OpenAI Official | OpenAI-compatible | `https://api.openai.com/v1` | `gpt-4o` | [OpenAI API reference](https://platform.openai.com/docs/api-reference/chat/create) | Local unauthenticated probe hit an SSL/proxy issue on this machine; verify from VPS when needed. |
| DeepSeek | OpenAI-compatible | `https://api.deepseek.com` | `deepseek-v4-flash` | [DeepSeek API docs](https://api-docs.deepseek.com/) | Official docs expose `api.deepseek.com/chat/completions` and `/models`. |
| DeepSeek Claude Protocol | Anthropic Messages-compatible | `https://api.deepseek.com/anthropic` | `deepseek-v4-flash` | [DeepSeek Anthropic API guide](https://api-docs.deepseek.com/guides/anthropic_api) | Use this preset for Claude-protocol clients backed by DeepSeek. |
| Alibaba Bailian / DashScope | OpenAI-compatible | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | [DashScope OpenAI compatibility](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope) | Keep the full `/compatible-mode/v1` path. |
| Volcengine Ark / Doubao | OpenAI-compatible | `https://ark.cn-beijing.volces.com/api/v3` | `ep-xxxxxxxx` | [Volcengine Ark docs](https://www.volcengine.com/docs/82379) | Model field is usually the Ark Endpoint ID. Keep `/api/v3`. |
| Anthropic Claude Official | Anthropic Messages | `https://api.anthropic.com` | `claude-sonnet-4-20250514` | [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) | Backend appends `/v1/messages`; model list uses `/v1/models`. |
| Zhipu GLM | OpenAI-compatible | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | [BigModel docs](https://docs.bigmodel.cn/) | Keep `/api/paas/v4`; do not append `/v1`. |
| MiniMax | OpenAI-compatible | `https://api.minimax.io/v1` | `MiniMax-M3` | [MiniMax platform docs](https://platform.minimaxi.com/document/) | Local unauthenticated probe hit an SSL/proxy issue on this machine; verify from VPS when needed. |
| SiliconFlow | OpenAI-compatible | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` | [SiliconFlow chat completions](https://docs.siliconflow.cn/api-reference/chat-completions/chat-completions) | Official docs expose `/v1/chat/completions`. |
| OpenRouter | OpenAI-compatible | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` | [OpenRouter API reference](https://openrouter.ai/docs/api-reference/overview) | `/api/v1/models` returned `200` in the no-key probe. |
| Xiaomi MiMo direct balance | OpenAI-compatible | `https://api.xiaomimimo.com/v1` | `mimo-v2.5-pro` | [MiMo OpenAI Chat Completions docs](https://mimo.mi.com/docs/en-US/api/chat/openai-api) | Uses the documented `api-key` or Bearer header. No-key chat endpoint probe returned `405`, confirming the host/path is reachable but requires the proper method and auth. |
| Custom Claude Protocol | Anthropic Messages-compatible | User supplied | `claude-sonnet-4-20250514` | User gateway docs | For Claude proxies, enterprise gateways, and protocol adapters. |

### MiMo Workflow Call Policy

MiMo V2.5 models enable thinking by default. The official Chat Completions
contract exposes `thinking.type` with `enabled`/`disabled`, returns visible
text in `choices[].message.content`, and uses `max_completion_tokens` for the
completion budget. BidPilot therefore disables thinking for Worker-owned
structured requirement extraction, quality review, and section drafting. These
steps already have deterministic retrieval, evidence binding and human review
around the model; leaving hidden reasoning enabled made a structured request
consume its budget before returning JSON and caused a 160-second degraded
workflow in the 2026-09-04 public rehearsal. The interactive Pi Assistant keeps
its own native streaming/reasoning policy and is not changed by this rule.

This policy is based on the [MiMo OpenAI Chat Completions
documentation](https://mimo.mi.com/docs/en-US/api/chat/openai-api) and its
[API integration FAQ](https://mimo.mi.com/docs/en-US/quick-start/faq/api-integration).

## Logo Policy

- Known provider marks should render through the local `ProviderBrandMark`
  component instead of provider favicons wrapped in random colored squares.
- SVG paths sourced from public brand icon registries are used only as
  identification marks in the provider picker. Trademarks belong to their
  respective owners.
- Where a reliable SVG mark is not available, the UI uses the provider's
  official website asset URL with a neutral fallback. Do not draw fake marks
  that could be mistaken for official assets.

## No-Key Probe, 2026-07-07

These probes intentionally sent no API key and did not call any billable model
generation. Expected healthy responses are `200`, `400`, `401`, or `405`
depending on endpoint and HTTP method.

| Endpoint | Result |
| --- | --- |
| `https://api.anthropic.com/v1/models` | `401` |
| `https://api.deepseek.com/models` | `401` |
| `https://api.deepseek.com/chat/completions` | `401` |
| `https://api.deepseek.com/anthropic/v1/messages` | `401` |
| `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` | `400` |
| `https://dashscope.aliyuncs.com/compatible-mode/v1/models` | `401` |
| `https://ark.cn-beijing.volces.com/api/v3/chat/completions` | `401` |
| `https://open.bigmodel.cn/api/paas/v4/chat/completions` | `401` |
| `https://api.siliconflow.cn/v1/models` | `401` |
| `https://openrouter.ai/api/v1/models` | `200` |
| `https://api.xiaomimimo.com/v1/chat/completions` | `405` |
| `https://api.openai.com/v1/models` | Local SSL/proxy failure |
| `https://api.minimax.io/v1/models` | Local SSL/proxy failure |
