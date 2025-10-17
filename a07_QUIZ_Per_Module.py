#!/usr/bin/env python3
"""
Quiz Generator for Course Modules

This script reads the course outline and generates a 10-question multiple-choice quiz for each module,
saving them as separate files named with the section number and name. It also creates a separate
answer key file for each quiz.

Files are saved in the _output/<course_name>/quizzes/ directory.

Usage:
    To run as a script:
        python a07_QUIZ_Per_Module.py
    
    To use as a module:
        from a07_QUIZ_Per_Module import main
        main()
"""

import os
import re
import json
import time
import importlib
import traceback
import random
import sys
import textwrap
from datetime import datetime

# Constants
CURRENT_DIRECTORY_FILE = "current_directory.txt"
OUTLINE_FILE = "course_outline.txt"
CURRENT_DIR = None

# Import LLM module dynamically
import importlib.util
llm_spec = importlib.util.spec_from_file_location("llm_module", "a02_LLM_Access.py")
llm_module = importlib.util.module_from_spec(llm_spec)
sys.modules["llm_module"] = llm_module
try:
    llm_spec.loader.exec_module(llm_module)
    call_llm = llm_module.call_llm
    LLM_AVAILABLE = True
    print("LLM module successfully loaded.")
except Exception as e:
    print(f"Error loading LLM module: {str(e)}")
    LLM_AVAILABLE = False


def get_current_directory():
    """
    Get the current working directory from current_directory.txt file.
    Returns the directory path or None if not found.
    """
    global CURRENT_DIR
    try:
        with open(CURRENT_DIRECTORY_FILE, 'r') as f:
            CURRENT_DIR = f.read().strip()
            print(f"Using directory from current_directory.txt: {CURRENT_DIR}")
            return CURRENT_DIR
    except FileNotFoundError:
        print("current_directory.txt not found. Using default paths.")
        return None


def parse_outline(file_path):
    """
    Parse the course outline text file and extract modules with their topics and subtopics.
    
    Returns:
        - A nested dictionary structure organized by modules
        - The course title
    """
    course_title = "Course Presentation"  # Default title
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # First line is the course title
    if lines and not lines[0].strip().startswith("1."):
        course_title = lines[0].strip()
        lines = lines[1:]  # Remove the title line
    
    # Initialize the structure
    outline = {}
    current_module = None
    current_topic = None
    current_subtopic = None
    
    # Process line by line
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Match module line (e.g., "1.Module 1: What is SONiC NOS")
        module_match = re.match(r'^(\d+)\.Module\s(.+)$', line)
        
        # Match topic line (e.g., "1.1 SONiC Overview")
        topic_match = re.match(r'^(\d+\.\d+)\s(.+)$', line)
        
        # Match subtopic line (e.g., "1.1.1 Defining SONiC")
        subtopic_match = re.match(r'^(\d+\.\d+\.\d+)\s(.+)$', line)
        
        # Match point line (e.g., "1.1.1.1 Software for Open Networking in the Cloud.")
        point_match = re.match(r'^(\d+\.\d+\.\d+\.\d+)\s(.+)$', line)
        
        if module_match:
            # It's a module
            module_number, module_title = module_match.groups()
            current_module = f"Module {module_number}"
            outline[current_module] = {
                "title": module_title.strip(),
                "module_number": module_number,
                "topics": {},
                "full_content": [line]
            }
            current_topic = None
            current_subtopic = None
        
        elif topic_match and current_module:
            # It's a topic
            topic_number, topic_title = topic_match.groups()
            current_topic = f"Topic {topic_number}"
            outline[current_module]["topics"][current_topic] = {
                "title": topic_title.strip(),
                "topic_number": topic_number,
                "subtopics": {}
            }
            outline[current_module]["full_content"].append(line)
            current_subtopic = None
        
        elif subtopic_match and current_module and current_topic:
            # It's a subtopic
            subtopic_number, subtopic_title = subtopic_match.groups()
            current_subtopic = f"Subtopic {subtopic_number}"
            outline[current_module]["topics"][current_topic]["subtopics"][current_subtopic] = {
                "title": subtopic_title.strip(),
                "subtopic_number": subtopic_number,
                "points": []
            }
            outline[current_module]["full_content"].append(line)
        
        elif point_match and current_module and current_topic and current_subtopic:
            # It's a point
            point_number, point_text = point_match.groups()
            point = point_text.strip()
            outline[current_module]["topics"][current_topic]["subtopics"][current_subtopic]["points"].append(point)
            outline[current_module]["full_content"].append(line)
        
        elif current_module:
            # It's some other text that belongs to the current module
            outline[current_module]["full_content"].append(line)
    
    return outline, course_title


def generate_module_quiz(module_data, module_number):
    """
    Generate a quiz for a specific module using LLM.
    
    Args:
        module_data: Dictionary containing module information and content
        module_number: The module number
    
    Returns:
        Tuple of (quiz_content, answer_key)
    """
    # Check if LLM is available
    global LLM_AVAILABLE, call_llm
    if not LLM_AVAILABLE:
        print("LLM module not available. Cannot generate quiz.")
        return None, None
    
    # Format the module content for the LLM prompt
    module_content = "\n".join(module_data["full_content"])
    
    # Construct the system prompt for the LLM
    system_prompt = """
    You are an expert quiz creator for technical courses. 
    
    I will provide you with the content of a technical course module.
    Create a 10-question multiple-choice quiz based on this content.
    
    Each question should:
    1. Be clearly related to the module content
    2. Have exactly 4 possible answers (A, B, C, D)
    3. Have only one correct answer
    4. Test understanding, not just memorization
    
    Provide your response in JSON format with this structure:
    {
        "quiz": [
            {
                "question": "What is the primary purpose of X?",
                "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
                "correct_answer": "B"
            },
            // more questions...
        ]
    }
    
    Only include the JSON response with no additional text.
    """
    
    # Construct the user prompt
    user_prompt = f"Create a 10-question quiz for the following module content:\n\n{module_content}"
    
    print(f"\nGenerating quiz for Module {module_number}...")
    
    # Call the LLM to generate the quiz
    try:
        response = call_llm(system_prompt=system_prompt, prompt=user_prompt)
        
        # Extract and parse the JSON response
        try:
            # Check if the response is wrapped in markdown code block
            json_match = re.search(r'```json\n(.+?)\n```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to extract just the JSON part
                json_match = re.search(r'\{.+\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response
            
            quiz_data = json.loads(json_str)
            
            # Format the quiz content
            quiz_content = []
            answer_key = []
            
            quiz_content.append(f"# Quiz for {module_data['title']}\n")
            answer_key.append(f"# Answer Key for {module_data['title']}\n")
            
            for i, q in enumerate(quiz_data["quiz"]):
                # Format the question for the quiz
                question_text = f"Question {i+1}: {q['question']}"
                quiz_content.append(question_text)
                
                # Add the options
                for option in q["options"]:
                    quiz_content.append(f"  {option}")
                
                quiz_content.append("\n")
                
                # Format the answer for the answer key
                answer_key.append(f"Question {i+1}: {q['correct_answer']}")
            
            return "\n".join(quiz_content), "\n".join(answer_key)
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {str(e)}")
            print(f"Raw response: {response[:200]}...")  # Show first 200 chars
            return None, None
    
    except Exception as e:
        print(f"Error generating quiz with LLM: {str(e)}")
        traceback.print_exc()
        return None, None


def create_quiz_files(outline, course_title):
    """
    Create quiz and answer key files for each module.
    
    Args:
        outline: The parsed course outline
        course_title: The title of the course
    """
    # Ensure quiz directory exists
    quiz_dir = "quizzes"
    if CURRENT_DIR:
        quiz_dir = os.path.join(CURRENT_DIR, "quizzes")
    
    os.makedirs(quiz_dir, exist_ok=True)
    
    # Generate quizzes for each module
    for module_key, module_data in outline.items():
        module_number = module_data["module_number"]
        module_title = module_data["title"]
        
        # Clean the module title for use in filenames
        clean_title = re.sub(r'[^\w\s-]', '', module_title).strip().replace(' ', '_')
        
        # Generate the quiz content
        print(f"\nProcessing module {module_number}: {module_title}")
        quiz_content, answer_key = generate_module_quiz(module_data, module_number)
        
        if quiz_content and answer_key:
            # Save the quiz file
            quiz_filename = f"{module_number}_{clean_title}_Quiz.txt"
            quiz_path = os.path.join(quiz_dir, quiz_filename)
            
            with open(quiz_path, 'w') as f:
                f.write(quiz_content)
            print(f"Quiz saved to: {quiz_path}")
            
            # Save the answer key file
            key_filename = f"{module_number}_{clean_title}_AnswerKey.txt"
            key_path = os.path.join(quiz_dir, key_filename)
            
            with open(key_path, 'w') as f:
                f.write(answer_key)
            print(f"Answer key saved to: {key_path}")
        else:
            print(f"Failed to generate quiz for module {module_number}")


def main():
    """
    Main function to run the quiz generation process.
    """
    print("=" * 70)
    print("Course Quiz Generator".center(70))
    print("=" * 70)
    
    # Get the current directory from file
    current_dir = get_current_directory()
    
    # Determine paths based on current directory
    outline_path = OUTLINE_FILE
    
    if current_dir:
        # Use directory-specific path if available
        outline_path = os.path.join(current_dir, OUTLINE_FILE)
    
    # Check if outline file exists
    if not os.path.exists(outline_path):
        print(f"Error: Outline file not found at {outline_path}")
        return
    
    # Parse the outline
    print(f"\nReading course outline from '{outline_path}'...")
    outline, course_title = parse_outline(outline_path)
    
    # Count the number of modules found
    module_count = len(outline)
    print(f"Found {module_count} modules.")
    
    # Generate quizzes for each module
    if module_count > 0:
        create_quiz_files(outline, course_title)
        print("\nQuiz generation complete!")
    else:
        print("No modules found in the outline. Cannot generate quizzes.")


if __name__ == "__main__":
    main()
