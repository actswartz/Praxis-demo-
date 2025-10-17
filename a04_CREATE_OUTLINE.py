#!/usr/bin/env python3
"""
Course Outline Generator

This script takes a course description as input and generates a comprehensive 
course outline using an LLM with a specialized system prompt.
"""

# Import necessary modules
import os
import importlib.util
import sys
from typing import Optional

# Load the LLM module with the numeric name using full path (with 'a' prefix)
module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "a02_LLM_Access.py")
spec = importlib.util.spec_from_file_location("llm_access", module_path)
llm_module = importlib.util.module_from_spec(spec)
sys.modules["llm_access"] = llm_module
spec.loader.exec_module(llm_module)

# Get the call_llm function from the module
call_llm = llm_module.call_llm

# Define the static system prompt for course outline generation
SYSTEM_PROMPT = """
You are an expert curriculum designer with years of experience in creating 
comprehensive course outlines. Your task is to analyze the provided course 
description and generate a detailed, well-structured course outline.

The useer will provide information that may include:
1. Course title
2. Course overview (1-2 paragraphs)
3. Learning objectives (5-8 items)
4. Target audience
5. Prerequisites (if any)
6. Course duration recommendation
7. Detailed module breakdown with:
   - Modules
   - Topics
   - Recommended activities or assignments
8. Assessment methods
9. Recommended resources
---
Example of course outline with Module and topics submitted by the user:
Course Outline: 
Understanding SASE 
• Cloud Computing = Network and Security Disruption • SASE Business Outcomes 
• Challenges solved by Cisco SASE 
• Cisco SASE: Connect – Control – Converge • Cisco SASE components 
• Cisco SD-WAN 
• Cisco DUO 
SASE Use Cases 
• Secure Remote Worker 
• Provisioning 
• Administration and Monitoring 
---



Your Outline should include the Modules and Topics from the user.

For each every topic include 3-6 Subtopics.
For each and every subtopic include 3-6 points - these will be used on powerpoint slides and should be short sentences.
do not put the words "module, topic, subtopic, or point in the outline"
The output format should looke like
Title: Course Title
1.Module 1
1.1 Topic 1
1.1.1 Subtopic 1
1.1.1.1 Point 1
1.1.1.2 Point 2
1.1.1.3 Point 3
1.1.1.4 Point 4
1.1.1.5 Point 5
1.1.1.6 Point 6
1.1.2 Subtopic 2
1.1.2.1 Point 1
1.1.2.2 Point 2
1.1.2.3 Point 3
1.1.2.4 Point 4
1.1.2.5 Point 5
1.1.2.6 Point 6
1.1.3 Subtopic 3
1.1.3.1 Point 1
1.1.3.2 Point 2
1.1.3.3 Point 3
1.1.3.4 Point 4
1.1.3.5 Point 5
1.1.3.6 Point 6
1.1.4 Subtopic 4
1.1.4.1 Point 1
1.1.4.2 Point 2
1.1.4.3 Point 3
1.1.4.4 Point 4
1.1.4.5 Point 5
1.1.4.6 Point 6

The outline should go four levels deep.

The course outline that you create should the 
Only output the outline, do not include any additional text.
Do not use markdown, only plain text.

"""

def main():
    print("=" * 70)
    print("COURSE OUTLINE GENERATOR".center(70))
    print("=" * 70)
    print("\nThis tool generates a comprehensive course outline from a Cisco course description file.")
    
    # Define path to course requirements directory
    course_req_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_Cisco_Course_Requirements")
    
    # Get list of course description files
    course_files = [f for f in os.listdir(course_req_dir) if os.path.isfile(os.path.join(course_req_dir, f)) and f.endswith(".txt")]
    
    if not course_files:
        print("No course description files found in _Cisco_Course_Requirements directory.")
        return
    
    # Display available files with numbers
    print("Available course description files:")
    for i, file_name in enumerate(course_files, 1):
        print(f"{i}. {file_name}")
    
    # Get user selection
    while True:
        try:
            selection = int(input("\nEnter the number of the file to use: "))
            if 1 <= selection <= len(course_files):
                selected_file = course_files[selection - 1]
                # Extract directory name from filename (remove .txt extension)
                directory_name = os.path.splitext(selected_file)[0]
                
                # Create _output parent directory if it doesn't exist
                output_dir = "_output"
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
                # Full path will be _output/directory_name
                full_dir_path = os.path.join(output_dir, directory_name)
                print(f"Using directory path: {full_dir_path}")
                
                # Save the directory name to current_directory.txt
                with open("current_directory.txt", "w") as dir_file:
                    dir_file.write(full_dir_path)
                print(f"Directory path saved to 'current_directory.txt'")
                break
            else:
                print(f"Please enter a number between 1 and {len(course_files)}.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Read the selected file
    file_path = os.path.join(course_req_dir, selected_file)
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            course_description = file.read()
        print(f"\nUsing course description from: {selected_file}")
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        return
    
    if not course_description.strip():
        print("Selected file is empty. Exiting.")
        return
    
    print("\nGenerating course outline... This may take a moment.")
    
    try:
        # Create the prompt by combining the course description with additional context
        user_prompt = f"""
Please create a comprehensive course outline based on the following course description:

{course_description}

Please be thorough and follow the structure specified in the system prompt.
"""
        
        # Call the LLM with the system prompt and user prompt
        response = call_llm(user_prompt, SYSTEM_PROMPT)
        
        # Display the generated outline
        print("\n" + "=" * 70)
        print("GENERATED COURSE OUTLINE".center(70))
        print("=" * 70 + "\n")
        print(response)
        print("\n" + "=" * 70)
        
        # Create directory if it doesn't exist
        full_dir_path = os.path.join("_output", directory_name)
        if not os.path.exists(full_dir_path):
            os.makedirs(full_dir_path)
            print(f"Created directory: {full_dir_path}")
            
        # Save outline in both the current directory and the new directory
        filename = "course_outline.txt"
        with open(filename, 'w') as f:
            f.write(response)
            
        # Also save to the new directory
        dir_filename = os.path.join(full_dir_path, filename)
        with open(dir_filename, 'w') as f:
            f.write(response)
            
        print(f"Outline saved to {filename} and {dir_filename}")
        
    except Exception as e:
        print(f"\nError occurred: {str(e)}")

if __name__ == "__main__":
    main()
