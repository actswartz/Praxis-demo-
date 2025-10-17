#!/usr/bin/env python3
"""
Slide Snapshot Generator

This module creates enhanced slide snapshots by combining:
1. A template background image (1920x1080)
2. AI-generated slide image on the right side
3. Slide title at the top in large font
4. Slide content below the title in normal font

These snapshots are intended for use in Markdown exports of presentations.

Usage:
    from a07_Slide_Snapshot_Generator import generate_snapshots_for_presentation

    snapshot_paths = generate_snapshots_for_presentation(slides_data, image_paths, output_dir)
"""

import os
import textwrap
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Constants for image generation
SLIDE_WIDTH = 1920
SLIDE_HEIGHT = 1080
TITLE_FONT_SIZE = 60
CONTENT_FONT_SIZE = 48  # Increased from 36
BULLET_FONT_SIZE = 40  # Increased from 32
CONTENT_TEXT_WIDTH = 1600  # Width for slide content text in pixels
BULLET_INDENT = 30  # Indentation for bullet point text

# Image positioning
IMAGE_POSITION = "right"  # Options: "right", "left", "center", "bottom"
IMAGE_WIDTH_PERCENT = 0.33  # Percentage of slide width (0.0-1.0)
IMAGE_VERTICAL_POSITION = 0.5  # Vertical position factor (0.0-1.0), 0.5 = centered

# Colors
BACKGROUND_COLOR = (245, 245, 245)  # Light gray background
TITLE_COLOR = (0, 68, 129)  # Dark blue
TEXT_COLOR = (50, 50, 50)  # Dark gray
PADDING = 50  # Padding from edges

def create_slide_snapshot(title, content, ai_image_path, output_path, template_path=None):
    """
    Create a slide snapshot with title, content, and AI-generated image.
    
    Args:
        title: The title text for the slide
        content: List of bullet points for the slide content
        ai_image_path: Path to the AI-generated image to include
        output_path: Path where the snapshot will be saved
        template_path: Optional path to a template background image
        
    Returns:
        The path to the generated snapshot image
    """
    try:
        # Create base image - either from template or blank canvas
        if template_path and os.path.exists(template_path):
            # Use template if provided
            slide = Image.open(template_path).convert("RGBA")
            slide = slide.resize((SLIDE_WIDTH, SLIDE_HEIGHT))
        else:
            # Create blank canvas with background color
            slide = Image.new("RGBA", (SLIDE_WIDTH, SLIDE_HEIGHT), BACKGROUND_COLOR)
        
        # Create drawing context
        draw = ImageDraw.Draw(slide)
        
        # Load fonts (using default if custom font not available)
        try:
            title_font = ImageFont.truetype("Arial Bold.ttf", TITLE_FONT_SIZE)
            content_font = ImageFont.truetype("Arial.ttf", CONTENT_FONT_SIZE)
            bullet_font = ImageFont.truetype("Arial.ttf", BULLET_FONT_SIZE)
        except IOError:
            # Fall back to default font if Arial is not available
            title_font = ImageFont.load_default().font_variant(size=TITLE_FONT_SIZE)
            content_font = ImageFont.load_default().font_variant(size=CONTENT_FONT_SIZE)
            bullet_font = ImageFont.load_default().font_variant(size=BULLET_FONT_SIZE)
        
        # Add title at the top
        draw.text((PADDING, PADDING), title, font=title_font, fill=TITLE_COLOR)
        
        # Calculate layout based on image position and content width
        # Determine max image width based on IMAGE_WIDTH_PERCENT
        max_image_width = int(SLIDE_WIDTH * IMAGE_WIDTH_PERCENT)
        
        # Calculate available content width based on image position
        if IMAGE_POSITION in ["left", "right"]:
            available_text_width = SLIDE_WIDTH - max_image_width - (PADDING * 3)
        else:  # center or bottom - content can use full width
            available_text_width = SLIDE_WIDTH - (PADDING * 2)
        
        # Ensure content width doesn't exceed the defined maximum
        content_width = min(CONTENT_TEXT_WIDTH, available_text_width)
        
        # Add AI-generated image if available
        if ai_image_path and os.path.exists(ai_image_path):
            try:
                ai_image = Image.open(ai_image_path).convert("RGBA")
                # Calculate aspect ratio to maintain proportions
                aspect_ratio = ai_image.width / ai_image.height
                
                # Size image appropriately based on position
                if IMAGE_POSITION == "bottom":
                    # Bottom position: wider but shorter
                    image_height = SLIDE_HEIGHT * 0.4  # 40% of slide height
                    image_width_adjusted = min(SLIDE_WIDTH - (PADDING * 2), image_height * aspect_ratio)
                else:
                    # Side or center position
                    image_width_adjusted = min(max_image_width, SLIDE_WIDTH - (PADDING * 2))
                    image_height = min(SLIDE_HEIGHT - (PADDING * 2), image_width_adjusted / aspect_ratio)
                    image_width_adjusted = int(image_height * aspect_ratio)  # Recalculate to maintain aspect ratio
                
                # Resize AI image maintaining aspect ratio
                ai_image = ai_image.resize((int(image_width_adjusted), int(image_height)))
                
                # Position image based on IMAGE_POSITION
                if IMAGE_POSITION == "right":
                    img_x = SLIDE_WIDTH - int(image_width_adjusted) - PADDING
                    img_y = int((SLIDE_HEIGHT - image_height) * IMAGE_VERTICAL_POSITION)
                elif IMAGE_POSITION == "left":
                    img_x = PADDING
                    img_y = int((SLIDE_HEIGHT - image_height) * IMAGE_VERTICAL_POSITION)
                elif IMAGE_POSITION == "center":
                    img_x = (SLIDE_WIDTH - int(image_width_adjusted)) // 2
                    img_y = int((SLIDE_HEIGHT - image_height) * IMAGE_VERTICAL_POSITION)
                else:  # bottom
                    img_x = (SLIDE_WIDTH - int(image_width_adjusted)) // 2
                    img_y = SLIDE_HEIGHT - int(image_height) - PADDING
                
                # Paste the AI image
                slide.paste(ai_image, (img_x, img_y), ai_image)
            except Exception as e:
                print(f"Error processing AI image: {e}")
        
        # Add content bullet points
        y_position = PADDING + TITLE_FONT_SIZE + 40  # Start below title
        for point in content:
            # Add bullet point
            bullet = "• "
            draw.text((PADDING, y_position), bullet, font=bullet_font, fill=TEXT_COLOR)
            
            # Wrap text to fit content area
            wrap_width = int(content_width / (CONTENT_FONT_SIZE * 0.6))  # Calculate characters that fit in content width
            wrapped_text = textwrap.wrap(point, width=wrap_width)
            
            # Add each line of wrapped text
            line_spacing = int(BULLET_FONT_SIZE * 1.2)  # Increased spacing between lines
            for i, line in enumerate(wrapped_text):
                line_y = y_position if i == 0 else y_position + (i * line_spacing)
                draw.text((PADDING + BULLET_INDENT, line_y), line, font=content_font, fill=TEXT_COLOR)
            
            # Move position for next bullet point
            y_position += (len(wrapped_text) * line_spacing) + 25  # Increased space between bullet points
        
        # Save the resulting image
        slide.save(output_path)
        return output_path
    
    except Exception as e:
        print(f"Error creating slide snapshot: {e}")
        return None

def generate_snapshots_for_presentation(slides_data, ai_image_paths, output_dir, template_path=None, title_image_path=None, course_title=None):
    """
    Generate snapshots for all slides in a presentation.
    
    Args:
        slides_data: List of dictionaries with slide information (title, content)
        ai_image_paths: Dictionary mapping slide titles to AI-generated image paths
        output_dir: Directory where snapshot images will be saved
        template_path: Optional path to a template background image
        title_image_path: Optional path to the title slide image
        course_title: Optional title of the course for the title slide
        
    Returns:
        Dictionary mapping slide titles to snapshot image paths
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize snapshot paths dictionary
    snapshot_paths = {}
    
    # Generate title slide snapshot if title image is provided
    if title_image_path and os.path.exists(title_image_path) and course_title:
        # Create a special snapshot for the title slide with 00_ prefix
        title_snapshot_filename = "00_snapshot_title_slide.png"
        title_snapshot_path = os.path.join(output_dir, title_snapshot_filename)
        
        # For the title slide, we'll resize it to exactly 1920x1080 resolution
        # This ensures the title slide appears first in sorted listings and has the right dimensions
        try:
            from PIL import Image
            
            # Open the image
            with Image.open(title_image_path) as img:
                # Resize to 1920x1080 with high quality resampling
                resized_img = img.resize((1920, 1080), Image.LANCZOS)
                
                # Convert to RGB if it has an alpha channel
                if resized_img.mode == 'RGBA':
                    resized_img = resized_img.convert('RGB')
                    
                # Save as the title slide snapshot
                resized_img.save(title_snapshot_path, quality=95)
                
            print(f"Created title slide snapshot (1920x1080): {title_snapshot_path}")
            
            # Add to snapshot paths with the course title as key
            snapshot_paths[course_title] = title_snapshot_path
        except Exception as e:
            print(f"Error creating title slide snapshot: {e}")
    
    # Process each slide
    for slide in slides_data:
        title = slide["title"]
        content = slide.get("content", [])
        
        # Get AI image path if available
        ai_image_path = ai_image_paths.get(title)
        
        # Debug: print if we found a match in the image_paths dictionary
        print(f"Looking for image for '{title}': {'Found' if ai_image_path else 'Not found'} in image_paths")
        
        # If we have a path, check if the file exists
        if ai_image_path:
            if os.path.exists(ai_image_path):
                print(f"Image found at: {ai_image_path}")
            else:
                print(f"Warning: AI image not found for '{title}': {ai_image_path}")
                ai_image_path = None
        
        # Generate safe filename from title with slide number prefix (001_, 002_, etc.)
        slide_index = list(slides_data).index(slide) + 1  # 1-based indexing
        safe_title = "".join(c if c.isalnum() else "_" for c in title)
        snapshot_filename = f"{slide_index:03d}_snapshot_{safe_title}.png"
        snapshot_path = os.path.join(output_dir, snapshot_filename)
        
        # Create snapshot
        result_path = create_slide_snapshot(
            title, 
            content, 
            ai_image_path, 
            snapshot_path, 
            template_path
        )
        
        if result_path:
            snapshot_paths[title] = result_path
            print(f"Created snapshot for '{title}'")
    
    return snapshot_paths

if __name__ == "__main__":
    # Example usage for testing
    test_title = "Example Slide"
    test_content = [
        "This is the first bullet point with some longer text that should wrap.",
        "This is the second bullet point.",
        "This is the third bullet point with additional information and details that should definitely wrap to multiple lines."
    ]
    
    # Create test directory if it doesn't exist
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_snapshots")
    os.makedirs(test_dir, exist_ok=True)
    
    output_path = os.path.join(test_dir, "test_snapshot.png")
    
    # Example AI image path - replace with an actual image for testing
    ai_image_path = None  # Replace with a test image path if available
    
    result = create_slide_snapshot(test_title, test_content, ai_image_path, output_path)
    
    if result:
        print(f"Test snapshot created at: {result}")
    else:
        print("Failed to create test snapshot")
