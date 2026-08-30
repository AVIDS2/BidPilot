"""Shared, explicit defaults for the platform Chat Completions provider."""

DEEPSEEK_CHAT_COMPLETIONS_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_V4_FLASH_MODEL = "deepseek-v4-flash"

# Xiaomi MiMo direct-balance API. Token Plan regional endpoints are separate
# Pi providers and must not be mixed with this profile.
MIMO_CHAT_COMPLETIONS_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_V2_5_PRO_MODEL = "mimo-v2.5-pro"

# OpenCode Go exposes the same model through a separately operated,
# OpenAI-compatible gateway. Keep this as a distinct provider profile rather
# than treating it as the official DeepSeek endpoint: model controls and
# availability semantics can differ by gateway.
OPENCODE_GO_CHAT_COMPLETIONS_BASE_URL = "https://opencode.ai/zen/go/v1"
OPENCODE_GO_DEEPSEEK_V4_FLASH_MODEL = "deepseek-v4-flash"
