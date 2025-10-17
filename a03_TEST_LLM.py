#!/usr/bin/env python3
"""
Test LLM Interaction Script

This script prompts the user to input a question and sends it to the LLM using 
the call_llm function from the 02_LLM_Access module.

Usage:
    To run as an interactive script:
        python a03_TEST_LLM.py
    
    To use as a module:
        from a03_TEST_LLM import main
        main()
"""

# Import the call_llm function - using importlib because the module name starts with a number
import importlib.util
import sys
import os
from typing import Optional

# Load the module with the numeric name using full path
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "02_LLM_Access.py")
spec = importlib.util.spec_from_file_location("llm_access", module_path)
llm_module = importlib.util.module_from_spec(spec)
sys.modules["llm_access"] = llm_module
spec.loader.exec_module(llm_module)

# Get the call_llm function from the module
call_llm = llm_module.call_llm

def main():
    print("=" * 50)
    print("LLM Question-Answering System")
    print("=" * 50)
    print("Options:")
    print("  - Type your question directly")
    print("  - Type '/system' to set a system prompt")
    print("  - Type '/clear' to clear the system prompt")
    print("  - Type '/show' to view the current system prompt")
    print("  - Type '/exit' or 'exit' to quit")
    print("=" * 50)
    
    # Initialize system prompt as None
    system_prompt = None
    
    while True:
        # Get user input
        user_input = input("\nYour question: ")
        
        # Check for commands
        if user_input.lower() in ['exit', 'quit', 'q', '/exit']:
            print("Exiting program. Goodbye!")
            break
        
        elif user_input.startswith('/system'):
            # Set system prompt
            if len(user_input) > 8:  # If there's text after /system command
                system_prompt = user_input[8:].strip()
                print(f"System prompt set to: {system_prompt}")
            else:
                # Ask for the system prompt on the next line
                system_prompt = input("Enter system prompt: ")
                if system_prompt.strip():
                    print(f"System prompt set to: {system_prompt}")
                else:
                    print("System prompt unchanged.")
            continue
        
        elif user_input == '/clear':
            # Clear system prompt
            system_prompt = None
            print("System prompt cleared.")
            continue
        
        elif user_input == '/show':
            # Show current system prompt
            if system_prompt:
                print(f"Current system prompt: {system_prompt}")
            else:
                print("No system prompt is set.")
            continue
            
        if not user_input.strip():
            print("Please enter a valid question.")
            continue
            
        # Show what's happening
        print("\nSending to LLM, please wait...")
        if system_prompt:
            print(f"Using system prompt: {system_prompt}")
        
        try:
            # Send the input to the LLM and get a response
            response = call_llm(user_input, system_prompt)
            
            # Display the response
            print("\n" + "=" * 50)
            print("LLM Response:")
            print("=" * 50)
            print(response)
            print("=" * 50)
            
        except Exception as e:
            print(f"\nError occurred: {str(e)}")

if __name__ == "__main__":
    main()
