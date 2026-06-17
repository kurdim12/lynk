"""The brain: the brand-safety system prompt and the RAG grounding processor.

Together these enforce the core contract — the avatar answers *only* from the
brand's approved knowledge, in the visitor's language, and never invents specs,
prices, or promises.
"""

from server.brain.rag import Grounding, RAGGrounder
from server.brain.system_prompt import build_system_prompt, detect_language

__all__ = ["Grounding", "RAGGrounder", "build_system_prompt", "detect_language"]
