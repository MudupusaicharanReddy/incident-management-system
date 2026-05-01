from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ComponentType, Severity, Signal


class AlertStrategy(ABC):
    @abstractmethod
    def severity(self, signal: Signal) -> Severity:
        raise NotImplementedError

    @abstractmethod
    def channel(self, signal: Signal) -> str:
        raise NotImplementedError


class DatabaseAlertStrategy(AlertStrategy):
    def severity(self, signal: Signal) -> Severity:
        return Severity.P0

    def channel(self, signal: Signal) -> str:
        return "pagerduty:database-oncall"


class QueueAlertStrategy(AlertStrategy):
    def severity(self, signal: Signal) -> Severity:
        return Severity.P1

    def channel(self, signal: Signal) -> str:
        return "pagerduty:platform-oncall"


class CacheAlertStrategy(AlertStrategy):
    def severity(self, signal: Signal) -> Severity:
        return Severity.P2

    def channel(self, signal: Signal) -> str:
        return "slack:#cache-incidents"


class DefaultAlertStrategy(AlertStrategy):
    def severity(self, signal: Signal) -> Severity:
        return Severity.P3

    def channel(self, signal: Signal) -> str:
        return "slack:#ops-triage"


def strategy_for(component_type: ComponentType) -> AlertStrategy:
    if component_type in {ComponentType.RDBMS, ComponentType.NOSQL}:
        return DatabaseAlertStrategy()
    if component_type == ComponentType.QUEUE:
        return QueueAlertStrategy()
    if component_type == ComponentType.CACHE:
        return CacheAlertStrategy()
    return DefaultAlertStrategy()
