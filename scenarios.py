import random
import string
from abc import ABC, abstractmethod
from typing import Dict, Tuple


class Scenario(ABC):
    """Abstract base class for benchmark scenarios."""

    @abstractmethod
    def generate_prompt(self, context_len: int) -> Tuple[str, Dict]:
        """
        Generates a prompt of target context length.
        Returns:
            prompt (str): The constructed prompt string (or messages).
            metadata (Dict): Any data needed for validation (e.g. the needle).
        """
        pass

    @abstractmethod
    def validate(self, response: str, metadata: Dict) -> bool:
        """
        Validates the LLM response against the metadata.
        Returns:
            passed (bool): True if correct, False otherwise.
        """
        pass


class SyntheticScenario(Scenario):
    """
    Standard synthetic load generation (current baseline).
    Fills context with random noise but doesn't strictly validate logic.
    """

    def generate_prompt(self, context_len: int) -> Tuple[str, Dict]:
        # Reserve space for system/template (~200 chars)
        # Rough char approx for tokens
        noise_len = max(100, (context_len * 4) - 200)
        noise = ''.join(random.choices(
            string.ascii_letters + " ", k=noise_len))

        prompt = f"System: You are a helpful assistant.\nContext: {noise}\nUser: Please summarize the context."
        return prompt, {}

    def validate(self, response: str, metadata: Dict) -> bool:
        # For synthetic load, as long as we get a response, it's a pass.
        # Real validation logic comes with NeedleInHaystack.
        return len(response.strip()) > 0


class NeedleInHaystackScenario(Scenario):
    """
    Injects a specific fact (needle) into a large context (haystack)
    and asks a question that requires retrieving that fact.
    """

    def __init__(self):
        self.facts = [
            ("The secret code is:", "BLUE-OMEGA-99"),
            ("The project manager's favorite color is:", "Octarine"),
            ("The meeting is scheduled continuously for:", "256 years")
        ]

    def generate_prompt(self, context_len: int) -> Tuple[str, Dict]:
        fact_intro, fact_answer = random.choice(self.facts)
        needle = f"{fact_intro} {fact_answer}."

        # Haystack
        target_chars = context_len * 4
        # We place needle at random depth (0% to 100%)
        # For simplicity in V1, let's place it at 50% depth

        noise_part_len = (target_chars - len(needle)) // 2
        noise_prefix = ''.join(random.choices(
            string.ascii_letters + " ", k=noise_part_len))
        noise_suffix = ''.join(random.choices(
            string.ascii_letters + " ", k=noise_part_len))

        prompt = f"Context:\n{noise_prefix}\n{needle}\n{noise_suffix}\n\nUser: {fact_intro}\nAnswer:"

        return prompt, {"expected": fact_answer}

    def validate(self, response: str, metadata: Dict) -> bool:
        expected = metadata.get("expected", "").lower()
        actual = response.lower()
        return expected in actual
