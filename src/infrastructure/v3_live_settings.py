"""Opt-in output allowance for verbose multi-issue records; P2 limits unchanged."""
from dataclasses import dataclass, replace
from src.infrastructure.deepseek import LiveSettings, LiveError


@dataclass(frozen=True)
class V3PilotSettings(LiveSettings):
    def validate(self):
        if not 1 <= self.max_tokens <= 6000:
            raise LiveError('configuration_error')
        LiveSettings.validate(replace(LiveSettings(**self.__dict__), max_tokens=1800))
