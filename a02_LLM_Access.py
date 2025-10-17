#!/usr/bin/env python3
"""
LLM Access Module - Enhanced version using new architecture.

This module provides backward compatibility while using the new LLM client.
"""

# Import the new LLM client for backward compatibility
from llm_client import call_llm

# Example usage
if __name__ == "__main__":
    response = call_llm("Explain how vector databases work in RAG applications in 3 paragraphs")
    print("\nLLM Response:\n")
    print(response)
