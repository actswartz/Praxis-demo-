#!/usr/bin/env python3
"""
Final Exam Generator for Course

This script reads the entire course outline and generates a comprehensive 50-question 
multiple-choice final exam, along with a separate answer key file.

Files are saved in the _output/<course_name>/exams/ directory.

Usage:
    To run as a script:
        python a08_Final_Exam.py

    To use as a module:
        from a08_Final_Exam import main
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
QUESTION_COUNT = 50  # Number of questions for the final exam

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
    Parse the course outline text file and extract all course content.
    
    Returns:
        - A nested dictionary structure containing all modules and content
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
    
    # Store all content for the entire course
    all_content = [course_title]  # Start with the course title
    
    # Process line by line
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Add each line to the full course content
        all_content.append(line)
            
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
    
    return outline, course_title, all_content


def generate_final_exam(course_content, course_title, module_count, outline=None):
    """
    Generate a final exam covering the entire course content using LLM.
    
    Args:
        course_content: List containing all course content
        course_title: The title of the course
        module_count: Number of modules in the course
    
    Returns:
        Tuple of (exam_content, answer_key)
    """
    # Check if LLM is available
    global LLM_AVAILABLE, call_llm
    if not LLM_AVAILABLE:
        print("LLM module not available. Cannot generate exam.")
        return None, None
    
    # Format the course content for the LLM prompt
    # Limit the amount of content to avoid overloading the LLM
    content_text = "\n".join(course_content)
    
    # If content is very long, provide a summary of each module instead
    if len(content_text) > 25000:  # Character limit to avoid token issues
        print("Course content is very long. Using module summaries instead.")
        summarized_content = []
        summarized_content.append(course_title)
        
        for module_key, module_data in outline.items():
            # Add module title
            module_title = f"{module_data['module_number']}.Module {module_data['title']}"
            summarized_content.append(module_title)
            
            # Add topic titles
            for topic_key, topic_data in module_data['topics'].items():
                topic_title = f"{topic_data['topic_number']} {topic_data['title']}"
                summarized_content.append(topic_title)
                
                # Add subtopic titles
                for subtopic_key, subtopic_data in topic_data['subtopics'].items():
                    subtopic_title = f"{subtopic_data['subtopic_number']} {subtopic_data['title']}"
                    summarized_content.append(subtopic_title)
        
        content_text = "\n".join(summarized_content)
    
    # Construct the system prompt for the LLM
    system_prompt = f"""
    You are an expert exam creator for technical courses. 
    
    I will provide you with the content of a technical course titled '{course_title}'.
    Create a comprehensive final exam with exactly {QUESTION_COUNT} multiple-choice questions based on this content.
    
    The exam should:
    1. Cover content from all {module_count} modules of the course proportionally
    2. Include questions of varying difficulty (easy, medium, and hard)
    3. Test both foundational knowledge and deeper understanding
    4. Have each question with exactly 4 possible answers (A, B, C, D)
    5. Have only one correct answer per question
    
    Provide your response in JSON format with this structure:
    {{
        "exam": [
            {{
                "question": "What is the primary purpose of X?",
                "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
                "correct_answer": "B"
            }},
            // more questions...
        ]
    }}
    
    Only include the JSON response with no additional text.
    """
    
    # Construct the user prompt
    user_prompt = f"Create a {QUESTION_COUNT}-question comprehensive final exam for the following course content:\n\n{content_text}"
    
    print(f"\nGenerating final exam with {QUESTION_COUNT} questions...")
    
    # Call the LLM to generate the exam
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
            
            exam_data = json.loads(json_str)
            
            # Format the exam content
            exam_content = []
            answer_key = []
            
            exam_content.append(f"# Final Exam: {course_title}\n")
            answer_key.append(f"# Final Exam Answer Key: {course_title}\n")
            
            for i, q in enumerate(exam_data["exam"]):
                # Format the question for the exam
                question_text = f"Question {i+1}: {q['question']}"
                exam_content.append(question_text)
                
                # Add the options
                for option in q["options"]:
                    exam_content.append(f"  {option}")
                
                exam_content.append("\n")
                
                # Format the answer for the answer key
                answer_key.append(f"Question {i+1}: {q['correct_answer']}")
            
            return "\n".join(exam_content), "\n".join(answer_key)
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {str(e)}")
            print(f"Raw response: {response[:200]}...")  # Show first 200 chars
            return None, None
    
    except Exception as e:
        print(f"Error generating exam with LLM: {str(e)}")
        traceback.print_exc()
        return None, None


def create_exam_files(exam_content, answer_key, course_title):
    """
    Create exam and answer key files.
    
    Args:
        exam_content: The formatted exam content
        answer_key: The formatted answer key content
        course_title: The title of the course
    """
    # Ensure exams directory exists
    exams_dir = "exams"
    if CURRENT_DIR:
        exams_dir = os.path.join(CURRENT_DIR, "exams")
    
    os.makedirs(exams_dir, exist_ok=True)
    
    # Clean the course title for use in filenames
    clean_title = re.sub(r'[^\w\s-]', '', course_title).strip().replace(' ', '_')
    
    # Save the exam file
    exam_filename = f"Final_Exam_{clean_title}.txt"
    exam_path = os.path.join(exams_dir, exam_filename)
    
    with open(exam_path, 'w') as f:
        f.write(exam_content)
    print(f"Final exam saved to: {exam_path}")
    
    # Save the answer key file
    key_filename = f"Final_Exam_{clean_title}_AnswerKey.txt"
    key_path = os.path.join(exams_dir, key_filename)
    
    with open(key_path, 'w') as f:
        f.write(answer_key)
    print(f"Answer key saved to: {key_path}")


def main():
    """
    Main function to run the final exam generation process.
    """
    print("=" * 70)
    print("Course Final Exam Generator".center(70))
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
    outline, course_title, all_content = parse_outline(outline_path)
    
    # Count the number of modules found
    module_count = len(outline)
    print(f"Found {module_count} modules.")
    
    # Generate the final exam
    if module_count > 0:
        exam_content, answer_key = generate_final_exam(all_content, course_title, module_count, outline)
        
        if exam_content and answer_key:
            create_exam_files(exam_content, answer_key, course_title)
            print("\nFinal exam generation complete!")
        else:
            print("Failed to generate final exam.")
    else:
        print("No modules found in the outline. Cannot generate final exam.")


if __name__ == "__main__":
    main()
