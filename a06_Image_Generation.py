#!/usr/bin/env python3
"""
Image Generation Module for Course Presentations

This module handles image prompt generation and image creation for presentation slides,
keeping the image generation functionality separate from the presentation creation.

Functionality:
1. Generates enhanced image prompts via AI for all slides in a presentation
2. Creates images based on these prompts using the image generation API
3. Manages file paths and storage locations for generated images
"""

import os
import sys
import json
import importlib.util
import re
from typing import Dict, List, Optional, Tuple

# Constants
IMAGE_WIDTH = 512      # Portrait orientation
IMAGE_HEIGHT = 1024    # Taller than wide for portrait images
DEFAULT_IMAGE_DIR = "slide_images"

# Configuration
config = {
    "image_dir": DEFAULT_IMAGE_DIR,
    "prompt_style": "professional business",
    "focus": "people and technology concepts with an exciting and modern design",
    "color_scheme": "modern corporate looke"
}

# For backward compatibility with existing code
IMAGE_DIR = DEFAULT_IMAGE_DIR  # This will be updated in setup_environment()


def setup_environment() -> None:
    """Initialize environment, directories, and dependencies"""
    # Import LLM module dynamically
    global call_llm, IMAGE_DIR
    llm_spec = importlib.util.spec_from_file_location("llm_module", "a02_LLM_Access.py")
    llm_module = importlib.util.module_from_spec(llm_spec)
    sys.modules["llm_module"] = llm_module
    llm_spec.loader.exec_module(llm_module)
    call_llm = llm_module.call_llm
    
    # Setup output directory
    output_dir = get_current_directory() or DEFAULT_IMAGE_DIR
    config["image_dir"] = os.path.join(output_dir, "slide_images")
    
    # Update global IMAGE_DIR for backward compatibility
    IMAGE_DIR = config["image_dir"]
    
    os.makedirs(config["image_dir"], exist_ok=True)
    print(f"Using image directory: {config['image_dir']}")


def get_current_directory() -> Optional[str]:
    """Get current working directory from configuration file
    
    Returns:
        Directory path if found in config file, None otherwise
    """
    try:
        if os.path.exists("current_directory.txt"):
            with open("current_directory.txt", "r") as dir_file:
                directory = dir_file.read().strip()
                if directory:
                    print(f"Using directory from current_directory.txt: {directory}")
                    os.makedirs(directory, exist_ok=True)
                    return directory
    except Exception as e:
        print(f"Error reading current_directory.txt: {str(e)}")
    return None

# Store all generated prompts
prompt_cache = {}


def extract_slide_info(outline_data: dict, max_slides: int = 0) -> List[dict]:
    """Extract all slide titles and content from the outline
    
    Args:
        outline_data: The parsed outline data structure
        max_slides: Maximum number of slides to return (0 = no limit)
        
    Returns:
        List of dictionaries with slide title and content
    """
    slides_info = []
    
    # Check if we have the new format (from PowerPoint script)
    # which has a title and modules list
    if "title" in outline_data and "modules" in outline_data:
        print("Processing simplified outline format...")
        # Process each module in the list
        for module in outline_data["modules"]:
            # Process topics in this module
            for topic in module.get("topics", []):
                # Get title and content
                title = topic.get("title", "")
                content = ""
                
                # Extract content from subtopics if available
                subtopics = topic.get("subtopics", [])
                if subtopics:
                    # Join all subtopic content
                    all_content = []
                    for subtopic in subtopics:
                        if isinstance(subtopic.get("content"), list):
                            all_content.extend(subtopic.get("content", []))
                        else:
                            all_content.append(str(subtopic.get("content", "")))
                    content = "\n".join(all_content)
                
                # Add to slides
                slides_info.append({"title": title, "content": content})
    
    # Handle original outline format (legacy)
    else:
        print("Processing original outline format...")
        # Process modules, topics, and subtopics to collect slide content
        for module, module_data in outline_data.items():
            if not isinstance(module_data, dict) or "topics" not in module_data:
                continue
                
            # Extract module number without the word "Module"
            try:
                module_number = module.split()[1]  # Gets the number after "Module"
                module_title = f"{module_number}: {module_data['title']}"
                
                # Module slide content
                topic_bullets = [f"{topic_data['title']}" for topic, topic_data in module_data["topics"].items()]
                module_content = "\n".join(topic_bullets)
                slides_info.append({"title": module_title, "content": module_content})
                
                # Process topics
                for topic, topic_data in module_data["topics"].items():
                    # Extract topic number 
                    topic_parts = topic.split()
                    topic_number = topic_parts[1]  # Gets the number like "1.1"
                    topic_title = f"{topic_number}: {topic_data['title']}"
                    
                    # Topic slide content
                    subtopic_bullets = [f"{subtopic_data['title']}" for subtopic, subtopic_data in topic_data["subtopics"].items()]
                    topic_content = "\n".join(subtopic_bullets)
                    slides_info.append({"title": topic_title, "content": topic_content})
                    
                    # Process subtopics
                    for subtopic, subtopic_data in topic_data["subtopics"].items():
                        subtopic_title = subtopic_data['title']
                        subtopic_content = "\n".join(subtopic_data["points"])
                        slides_info.append({"title": subtopic_title, "content": subtopic_content})
            except (KeyError, IndexError) as e:
                print(f"Warning: Skipping malformed module: {e}")
    
    # Limit slides if requested
    if max_slides > 0 and max_slides < len(slides_info):
        slides_info = slides_info[:max_slides]
    
    print(f"Extracted {len(slides_info)} slides for image prompt generation")
    return slides_info


def clean_json_response(response: str) -> str:
    """Clean and extract JSON from LLM response
    
    Args:
        response: Raw response from LLM
        
    Returns:
        Cleaned JSON string
    """
    # Extract JSON from markdown code blocks if present
    if "```json" in response:
        json_start = response.find("```json") + 7
        json_end = response.find("```", json_start)
        if json_end > json_start:
            response = response[json_start:json_end].strip()
    
    # Remove any leading content before JSON
    response = response.strip()
    if not response.startswith("{"):
        start_idx = response.find('{')
        if start_idx >= 0:
            response = response[start_idx:]
    
    return response


def save_prompts_to_file(prompts_json: str, output_filename: str = "06_Enhanced_Prompts.txt") -> str:
    """Save raw prompt response to file
    
    Args:
        prompts_json: Raw JSON response to save
        output_filename: Filename to save to
        
    Returns:
        Path to saved file
    """
    # Determine output directory
    current_dir = get_current_directory()
    if current_dir:
        output_path = os.path.join(current_dir, output_filename)
    else:
        output_path = output_filename
    
    # Save the raw response
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(prompts_json)
        
    return output_path


def create_fallback_prompt(slide_title: str) -> str:
    """Create a fallback prompt for a slide if AI generation fails
    
    Args:
        slide_title: Title of the slide
        
    Returns:
        Fallback prompt for image generation
    """
    return (f"Create a professional image representing {slide_title}. "
           f"Style: {config['prompt_style']}. "
           f"Focus on {config['focus']} with {config['color_scheme']}.")


def generate_all_image_prompts(outline_data: dict, max_slides: int = 0) -> Dict[str, str]:
    """Generate image prompts for all slides in the presentation in a single batch
    
    Args:
        outline_data: The parsed outline data structure
        max_slides: Maximum number of slides to generate prompts for (0 = no limit)
        
    Returns:
        Dictionary of slide titles to enhanced prompts
    """
    global prompt_cache
    
    print("\nPreparing slide content for batch prompt generation...")
    slides_info = extract_slide_info(outline_data, max_slides)
    print(f"Found {len(slides_info)} slides for prompt generation")
    print("****************************************************")
    # Build system prompt for AI model
    system_prompt = f"""
You are an expert AI image prompt engineer for presentations.

I will provide you with a list of slide titles and content.
For EACH slide, create an AI image generation concise prompt that would produce a visually appealing 
image representing that slide's idea or concept.

The image prompts should:
- Be visually appealing and suitable for a {config['prompt_style']}
- NOT generate any text
- Focus on {config['focus']}
- Use {config['color_scheme']}

Provide your response as a JSON object with the following structure:
{{"slide_title": "prompt"}}

Only include the JSON response with no additional explanations or text.
"""
    
    # Build the user prompt with all slides
    slides_json = json.dumps(slides_info, indent=2)
    user_prompt = f"Generate unique image prompts for each of these presentation slides:\n{slides_json}"
    
    # Call LLM through the module
    try:
        print(f"Sending batch request to generate {len(slides_info)} slide prompts...")
        enhanced_prompts_json = call_llm(user_prompt, system_prompt)
        
        # Save the raw enhanced prompts to a file
        output_path = save_prompts_to_file(enhanced_prompts_json)
        print(f"Enhanced prompts saved to: {output_path}")
        
        # Parse the JSON response
        try:
            # Clean and parse JSON
            cleaned_json = clean_json_response(enhanced_prompts_json)
            prompt_cache = json.loads(cleaned_json)
            print(f"Successfully received {len(prompt_cache)} enhanced prompts")
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {str(e)}")
            # Use fallback prompts if JSON parsing fails
            prompt_cache = {}
            for slide_info in slides_info:
                slide_title = slide_info["title"]
                prompt_cache[slide_title] = create_fallback_prompt(slide_title)
    
    except Exception as e:
        print(f"Error generating enhanced prompts: {str(e)}")
        # Use fallback prompts if API call fails
        prompt_cache = {}
        for slide_info in slides_info:
            slide_title = slide_info["title"]
            prompt_cache[slide_title] = create_fallback_prompt(slide_title)
    
    return prompt_cache

def get_enhanced_prompt(slide_title: str, slide_content: str = "") -> str:
    """Get an enhanced prompt for a specific slide
    
    Args:
        slide_title: The title of the slide
        slide_content: Optional content/bullet points of the slide
        
    Returns:
        Enhanced image generation prompt for this slide
    """
    # Check if we have a pre-generated prompt for this slide
    if slide_title in prompt_cache:
        print(f"Using pre-generated prompt for: {slide_title}")
        return prompt_cache[slide_title]
    else:
        # Fallback to a basic prompt if no pre-generated prompt is available
        print(f"No pre-generated prompt found for: {slide_title}. Using fallback.")
        return create_fallback_prompt(slide_title)


def sanitize_filename(name: str, max_length: int = 30) -> str:
    """Create a safe filename from a slide title
    
    Args:
        name: Original string to sanitize
        max_length: Maximum filename length
        
    Returns:
        Sanitized filename
    """
    # Remove invalid filename characters
    safe_name = re.sub(r'[^\w\-_.]+', '_', name)
    
    # Truncate if needed
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]
        
    return safe_name


def generate_image_for_slide(slide_title: str, slide_content: str = "") -> Optional[str]:
    """Generate an image for a slide based on its title and content
    
    Args:
        slide_title: The title of the slide
        slide_content: Optional content/bullet points of the slide
        
    Returns:
        Path to the generated image file, or None if generation failed
    """
    # Import here to avoid circular imports
    from arunware_image_generator import generate_image
    
    # Get enhanced prompt for this slide
    prompt = get_enhanced_prompt(slide_title, slide_content)
    
    # Create a safe filename from the slide title
    safe_title = sanitize_filename(slide_title)
    image_filename = f"slide_{safe_title}.png"
    image_path = os.path.join(config["image_dir"], image_filename)
    
    # Generate the image
    print(f"Generating image for slide: {slide_title}")
    print(f"Prompt: {prompt}")
    
    try:
        # Call the image generation API
        image_files = generate_image(
            prompt=prompt,
            output_path=image_path,
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            num_images=1
        )
        
        # Return the first image path if successful
        if image_files and len(image_files) > 0:
            return image_files[0]
        else:
            print(f"Warning: No images were generated for slide '{slide_title}'")
            return None
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return None


def generate_slide_images_parallel(slides_data, batch_size: int = 25) -> Dict[str, str]:
    """Generate images for all slides in parallel batches
    
    Args:
        slides_data: List of slide dictionaries with title and content
        batch_size: Maximum number of slides to process in each batch
        
    Returns:
        Dictionary mapping slide titles to image paths
    """
    # First, ensure all prompts are pre-generated
    all_titles = [slide["title"] for slide in slides_data]
    print(f"Preparing to generate images for {len(all_titles)} slides")
    
    # Track image paths by title
    image_paths_by_title = {}
    
    # Get all existing images in the output directory
    slide_images_dir = config["image_dir"]
    existing_files = []
    if os.path.exists(slide_images_dir):
        existing_files = os.listdir(slide_images_dir)
    
    # Process slides sequentially (in real implementation, this would be parallel)
    for j, slide in enumerate(slides_data):
        # Create numeric filename for output consistency
        slide_num = j + 1  # 1-based indexing
        image_filename = f"{slide_num:02d}_slide.png"
        output_path = os.path.join(slide_images_dir, image_filename)
        
        # Check if image already exists
        if image_filename in existing_files and os.path.exists(output_path):
            print(f"Image already exists for slide {j+1}: {output_path}")
        else:
            # Generate the image for this slide
            prompt = get_enhanced_prompt(slide["title"], slide["content"])
            print(f"Generating image {j+1}/{len(slides_data)}: {slide['title']}")
            
            # In a real parallel implementation, this would be added to a task queue
            # For now, we'll just generate sequentially
            try:
                # Import here to avoid circular imports
                from arunware_image_generator import generate_image
                
                image_files = generate_image(
                    prompt=prompt,
                    output_path=output_path,
                    width=IMAGE_WIDTH,
                    height=IMAGE_HEIGHT,
                    num_images=1
                )
                
                if not image_files or len(image_files) == 0:
                    print(f"Warning: Failed to generate image for slide {j+1}")
            except Exception as e:
                print(f"Error generating image for slide {j+1}: {str(e)}")
        
        # Add to our mapping regardless of whether we just generated it or it existed
        if os.path.exists(output_path):
            image_paths_by_title[slide["title"]] = output_path
        else:
            print(f"Warning: No image file found for slide {j+1}")
    
    print(f"Completed image generation. Generated {len(image_paths_by_title)} images.")
    return image_paths_by_title


def main():
    """Main function for testing the module independently"""
    print("Image Generation Module - Run from a05_CREATE_POWERPOINT.py")


# Initialize the module when imported
setup_environment()

# Run main() if script is executed directly
if __name__ == "__main__":
    main()
