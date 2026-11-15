from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentContext:
    user_id: int
    permission_codes: frozenset[str]
