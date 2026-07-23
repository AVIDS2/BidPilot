"""Bounded prompt and output limits for the governed Operator planner.

The values are deliberately expressed as characters for untrusted text and
tokens for model output. Character limits are conservative for CJK input, where
one visible character can approach one token.
"""

OPERATOR_MAX_CAPABILITY_CALLS = 3
OPERATOR_PLANNER_MAX_OUTPUT_TOKENS = 2_048
# Harness/planner preflight hold. Keep conservative but small enough that a
# few consecutive turns do not exhaust the platform monthly ceiling.
OPERATOR_PLANNER_RESERVATION_TOKENS = 8_000
OPERATOR_PLANNER_MAX_USER_MESSAGE_CHARACTERS = 4_000
OPERATOR_PLANNER_MAX_MEMORY_CONTEXT_CHARACTERS = 4_000
OPERATOR_PLANNER_MAX_CONVERSATION_CONTEXT_CHARACTERS = 4_000
OPERATOR_PLANNER_MAX_CONVERSATION_MESSAGE_CHARACTERS = 800
OPERATOR_PLANNER_MAX_PREVIOUS_RESULT_CHARACTERS = 2_000
OPERATOR_PLANNER_MAX_ATTACHMENT_CONTEXT_CHARACTERS = 1_500
