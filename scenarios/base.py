from abc import ABC, abstractmethod
from typing import Dict, Any
import time


class BenchmarkScenario(ABC):
    def __init__(self, config: Any):
        self.config = config
        self.results = {}

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """
        Executes the scenario logic.
        Returns a dictionary of summary metrics.
        """
        pass

    def log(self, message: str):
        print(f"[{self.config.scenario.id}] {message}")
