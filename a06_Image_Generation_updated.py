#!/usr/bin/env python3
"""
Enhanced Image Generation Module using new architecture.

This module provides improved image generation functionality with caching,
parallel processing, and better error handling.
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path

from config import config
from llm_client import call_llm
from image_client import image_client
from utils import FileUtils, logger
from cache_manager import cached

# Constants
IMAGE_WIDTH = config.IMAGE_WIDTH
IMAGE_HEIGHT = config.IMAGE_HEIGHT
DEFAULT_IMAGE_DIR = "slide_images"

class ImageGenerationManager:
    """Manager class for image generation operations."""
    
    def __init__(self):
        """Initialize the image generation manager."""
        self.image_dir = self._get_image_directory()
        self.prompt_cache = {}
        
    def _get_image_directory(self) -> str:
        """Get the image directory path."""
        current_dir = config.get_current_directory()
        image_dir = os.path.join(current_dir or ".", DEFAULT_IMAGE_DIR)
        return FileUtils.ensure_directory(image_dir)
    
    def setup_environment(self) -> None:
        """Set up the environment for image generation."""
        logger.info(f"Using image directory: {self.image_dir}")
    
    def extract_slide_info(self, outline_data: dict, max_slides: int = 0) -> List[dict]:
        """Extract all slide titles and content from the outline."""
        slides_info = []
        
        # Handle both new and legacy formats
        if "title" in outline_data and "modules" in outline_data:
            logger.info("Processing simplified outline format...")
            for module in outline_data["modules"]:
                for topic in module.get("topics", []):
                    title = topic.get("title", "")
                    content = self._extract_content_from_subtopics(topic.get("subtopics", []))
                    slides_info.append({"title": title, "content": content})
        else:
            logger.info("Processing legacy outline format...")
            slides_info = self._process_legacy_format(outline_data)
        
        # Limit slides if requested
        if max_slides > 0 and max_slides < len(slides_info):
            slides_info = slides_info[:max_slides]
        
        logger.info(f"Extracted {len(slides_info)} slides for image prompt generation")
        return slides_info
    
    def _extract_content_from_subtopics(self, subtopics: List[dict]) -> str:
        """Extract content from subtopics."""
        if not subtopics:
            return ""
        
        all_content = []
        for subtopic in subtopics:
            if isinstance(subtopic.get("content"), list):
                all_content.extend(subtopic.get("content", []))
            else:
                all_content.append(str(subtopic.get("content", "")))
        return "\n".join(all_content)
    
    def _process_legacy_format(self, outline_data: dict) -> List[dict]:
        """Process legacy outline format."""
        slides_info = []
        
        for module, module_data in outline_data.items():
            if not isinstance(module_data, dict) or "topics" not in module_data:
                continue
                
            try:
                module_number = module.split()[1]
                module_title = f"{module_number}: {module_data['title']}"
                
                # Module slide
                topic_bullets = [f"{topic_data['title']}" for topic, topic_data in module_data["topics"].items()]
                module_content = "\n".join(topic_bullets)
                slides_info.append({"title": module_title, "content": module_content})
                
                # Topics and subtopics
                for topic, topic_data in module_data["topics"].items():
                    topic_parts = topic.split()
                    topic_number = topic_parts[1]
                    topic_title = f"{topic_number}: {topic_data['title']}"
                    
                    subtopic_bullets = [f"{subtopic_data['title']}" for subtopic, subtopic_data in topic_data["subtopics"].items()]
                    topic_content = "\n".join(subtopic_bullets)
                    slides_info.append({"title": topic_title, "content": topic_content})
                    
                    for subtopic, subtopic_data in topic_data["subtopics"].items():
                        subtopic_title = subtopic_data['title']
                        subtopic_content = "\n".join(subtopic_data["points"])
                        slides_info.append({"title": subtopic_title, "content": subtopic_content})
                        
            except (KeyError, IndexError) as e:
                logger.warning(f"Skipping malformed module: {e}")
        
        return slides_info
    
    def clean_json_response(self, response: str) -> str:
        """Clean and extract JSON from LLM response."""
        # Extract JSON from markdown code blocks
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
    
    def save_prompts_to_file(self, prompts_json: str, output_filename: str = "06_Enhanced_Prompts.txt") -> str:
        """Save raw prompt response to file."""
        output_path = os.path.join(config.get_current_directory() or ".", output_filename)
        FileUtils.write_json_file(output_path, {"prompts": prompts_json})
        logger.info(f"Enhanced prompts saved to: {output_path}")
        return output_path
    
    def create_fallback_prompt(self, slide_title: str) -> str:
        """Create a fallback prompt for a slide if AI generation fails."""
        return (f"Create a professional image representing {slide_title}. "
               f"Style: modern business presentation. "
               f"Focus on technology and education concepts with clean, modern design.")
    
    @cached(ttl=1800)
    def generate_all_image_prompts(self, outline_data: dict, max_slides: int = 0) -> Dict[str, str]:
        """Generate image prompts for all slides in the presentation."""
        logger.info("Preparing slide content for batch prompt generation...")
        slides_info = self.extract_slide_info(outline_data, max_slides)
        
        # Build system prompt
        system_prompt = """
You are an expert AI image prompt engineer for presentations.

I will provide you with a list of slide titles and content.
For EACH slide, create an AI image generation concise prompt that would produce a visually appealing 
image representing that slide's idea or concept.

The image prompts should:
- Be visually appealing and suitable for a professional business presentation
- NOT generate any text
- Focus on technology and education concepts
- Use modern, clean design

Provide your response as a JSON object with the following structure:
{"slide_title": "prompt"}

Only include the JSON response with no additional explanations or text.
"""
        
        # Build user prompt
        slides_json = json.dumps(slides_info, indent=2)
        user_prompt = f"Generate unique image prompts for each of these presentation slides:\n{slides_json}"
        
        try:
            logger.info(f"Sending batch request to generate {len(slides_info)} slide prompts...")
            enhanced_prompts_json = call_llm(user_prompt, system_prompt)
            
            # Save the raw enhanced prompts
            self.save_prompts_to_file(enhanced_prompts_json)
            
            # Parse JSON response
            cleaned_json = self.clean_json_response(enhanced_prompts_json)
            prompt_cache = json.loads(cleaned_json)
            logger.info(f"Successfully received {len(prompt_cache)} enhanced prompts")
            
            return prompt_cache
            
        except Exception as e:
            logger.error(f"Error generating enhanced prompts: {e}")
            # Use fallback prompts
            prompt_cache = {}
            for slide_info in slides_info:
                slide_title = slide_info["title"]
                prompt_cache[slide_title] = self.create_fallback_prompt(slide_title)
            
            return prompt_cache
    
    def get_enhanced_prompt(self, slide_title: str, slide_content: str = "") -> str:
        """Get an enhanced prompt for a specific slide."""
        if slide_title in self.prompt_cache:
            logger.debug(f"Using pre-generated prompt for: {slide_title}")
            return self.prompt_cache[slide_title]
        else:
            logger.debug(f"Using fallback prompt for: {slide_title}")
            return self.create_fallback_prompt(slide_title)
    
    def sanitize_filename(self, name: str, max_length: int = 30) -> str:
        """Create a safe filename from a slide title."""
        import re
        safe_name = re.sub(r'[^\w\-_.]+', '_', name)
        if len(safe_name) > max_length:
            safe_name = safe_name[:max_length]
        return safe_name
    
    def generate_image_for_slide(self, slide_title: str, slide_content: str = "") -> Optional[str]:
        """Generate an image for a slide based on its title and content."""
        prompt = self.get_enhanced_prompt(slide_title, slide_content)
        safe_title = self.sanitize_filename(slide_title)
        image_filename = f"slide_{safe_title}.png"
        image_path = os.path.join(self.image_dir, image_filename)
        
        logger.info(f"Generating image for slide: {slide_title}")
        
        try:
            image_urls = image_client.generate_image(
                prompt=prompt,
                width=config.IMAGE_WIDTH,
                height=config.IMAGE_HEIGHT,
                num_images=1
            )
            
            if image_urls:
                # Download the image
                success = image_client.download_image(image_urls[0], image_path)
                return image_path if success else None
            else:
                logger.warning(f"No images generated for slide '{slide_title}'")
                return None
                
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return None
    
    def generate_slide_images_parallel(self, slides_data, batch_size: int = 25) -> Dict[str, str]:
        """Generate images for all slides in parallel."""
        # First, ensure all prompts are pre-generated
        all_titles = [slide["title"] for slide in slides_data]
        logger.info(f"Preparing to generate images for {len(all_titles)} slides")
        
        # Generate prompts if not already done
        if not self.prompt_cache:
            outline_data = {"modules": [{"topics": slides_data}]}
            self.generate_all_image_prompts(outline_data)
        
        # Generate images in parallel
        prompts_and_paths = []
        for i, slide in enumerate(slides_data):
            prompt = self.get_enhanced_prompt(slide["title"], slide["content"])
            image_filename = f"{i+1:02d}_slide.png"
            image_path = os.path.join(self.image_dir, image_filename)
            prompts_and_paths.append((prompt, image_path))
        
        # Use parallel processing
        image_paths_by_title = {}
        for i, (prompt, image_path) in enumerate(prompts_and_paths):
            try:
                image_urls = image_client.generate_image(prompt, width=config.IMAGE_WIDTH, height=config.IMAGE_HEIGHT)
                if image_urls:
                    success = image_client.download_image(image_urls[0], image_path)
                    if success:
                        image_paths_by_title[slides_data[i]["title"]] = image_path
            except Exception as e:
                logger.error(f"Error generating image for slide {i+1}: {e}")
        
        logger.info(f"Completed image generation. Generated {len(image_paths_by_title)} images.")
        return image_paths_by_title

# Global manager instance
image_manager = ImageGenerationManager()

# Backward compatibility functions
def setup_environment() -> None:
    """Set up the environment for image generation."""
    image_manager.setup_environment()

def get_current_directory() -> Optional[str]:
    """Get current working directory from configuration file."""
    return config.get_current_directory()

def extract_slide_info(outline_data: dict, max_slides: int = 0) -> List[dict]:
    """Extract all slide titles and content from the outline."""
    return image_manager.extract_slide_info(outline_data, max_slides)

def clean_json_response(response: str) -> str:
    """Clean and extract JSON from LLM response."""
    return image_manager.clean_json_response(response)

def save_prompts_to_file(prompts_json: str, output_filename: str = "06_Enhanced_Prompts.txt") -> str:
    """Save raw prompt response to file."""
    return image_manager.save_prompts_to_file(prompts_json, output_filename)

def create_fallback_prompt(slide_title: str) -> str:
    """Create a fallback prompt for a slide if AI generation fails."""
    return image_manager.create_fallback_prompt(slide_title)

def generate_all_image_prompts(outline_data: dict, max_slides: int = 0) -> Dict[str, str]:
    """Generate image prompts for all slides in the presentation."""
    return image_manager.generate_all_image_prompts(outline_data, max_slides)

def get_enhanced_prompt(slide_title: str, slide_content: str = "") -> str:
    """Get an enhanced prompt for a specific slide."""
    return image_manager.get_enhanced_prompt(slide_title, slide_content)

def sanitize_filename(name: str, max_length: int = 30) -> str:
    """Create a safe filename from a slide title."""
    return image_manager.sanitize_filename(name, max_length)

def generate_image_for_slide(slide_title: str, slide_content: str = "") -> Optional[str]:
    """Generate an image for a slide based on its title and content."""
    return image_manager.generate_image_for_slide(slide_title, slide_content)

def generate_slide_images_parallel(slides_data, batch_size: int = 25) -> Dict[str, str]:
    """Generate images for all slides in parallel."""
    return image_manager.generate_slide_images_parallel(slides_data, batch_size)

def main():
    """Main function for testing the module independently."""
    logger.info("Image Generation Module - Enhanced version")

if __name__ == "__main__":
    main()