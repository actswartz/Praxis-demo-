#!/usr/bin/env python3
"""
PowerPoint to Video Converter with Audio Narration

This script converts a PowerPoint presentation into a video with audio narration.
It extracts slides as images, generates audio for each slide using Google Cloud Text-to-Speech API
based on speaker notes from 06_Enhanced_Notes.txt, and combines them into a video.

Requirements:
- Google Cloud account with Text-to-Speech API enabled
- Service account credentials with permission to access the API

Usage:
    To run as a script:
        python a10_Audio_Generation_for_Slides.py
    
    To use as a module:
        from a10_Audio_Generation_for_Slides import main
        main()
"""

import os
import sys
import json
import time
import subprocess
import shutil
import re
import tempfile
from datetime import datetime
import traceback
import importlib
from pathlib import Path

# Third-party libraries
try:
    from pptx import Presentation
    from PIL import Image
    from google.cloud import texttospeech
    import requests
    print("Base libraries loaded successfully.")
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    print("Please install required libraries with:")
    print("pip install python-pptx pillow google-cloud-texttospeech requests")
    sys.exit(1)

# Try a more direct approach for importing and create fallbacks if needed
try:
    # For video generation, we can use OpenCV and ffmpeg directly as alternatives
    # if moviepy fails. First, try to import moviepy traditionally
    import moviepy.editor as mp
    USE_MOVIEPY = True
    print("MoviePy loaded successfully.")
except ImportError as e:
    print(f"Warning: MoviePy import failed: {e}")
    print("Switching to alternative video creation method...")
    USE_MOVIEPY = False
    
    # Try to import cv2 as fallback
    try:
        import cv2
        print("Using OpenCV as fallback for video generation.")
    except ImportError:
        print("OpenCV not available. Will use ffmpeg directly via subprocess.")
        import subprocess

# Constants
CURRENT_DIRECTORY_FILE = "current_directory.txt"
ENHANCED_NOTES_FILE = "06_Enhanced_Notes.txt"
OUTPUT_VIDEO_NAME = "course_video.mp4"
SLIDE_DURATION = 1  # Default duration per slide in seconds if no audio
GCP_SERVICE_ACCOUNT_FILE = "gcp-service-account.json"  # Update this to your service account file
CURRENT_DIR = None

# Audio settings for Google Cloud Text-to-Speech
VOICE_NAME = "en-US-Neural2-F"  # Professional female voice
VOICE_LANGUAGE_CODE = "en-US"
SPEAKING_RATE = 1.0  # 1.0 is normal speed, adjust as needed
PITCH = 0.0  # Default pitch


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


def setup_directories(base_dir=None):
    """
    Set up necessary directories for the conversion process.
    
    Args:
        base_dir: Base directory path. If None, will use the global CURRENT_DIR or getcwd()
        
    Returns:
        Dictionary of paths
    """
    # Use provided base_dir, or fall back to global CURRENT_DIR, or finally use current working directory
    if base_dir is None:
        base_dir = CURRENT_DIR if CURRENT_DIR else os.getcwd()
    
    # Create directory structure
    paths = {
        "base": base_dir,
        "images": os.path.join(base_dir, "slide_snapshots"),  # Using slide snapshots instead of slide images
        "audio": os.path.join(base_dir, "audio"),
        "video": os.path.join(base_dir, "video"),
    }
    
    # Ensure directories exist
    for path in paths.values():
        if path != base_dir and not os.path.exists(path):
            os.makedirs(path)
            print(f"Created directory: {path}")
    
    return paths


def extract_slides_as_images(pptx_file, output_dir):
    """
    Find existing slide snapshots instead of extracting from PowerPoint.
    
    Args:
        pptx_file: Path to PowerPoint file (not used, kept for compatibility)
        output_dir: Directory where slide snapshots are located
        
    Returns:
        List of slide snapshot image paths in order
    """
    if not os.path.exists(output_dir):
        print(f"Error: Slide snapshot directory not found at {output_dir}")
        return []
    
    try:
        # Find all snapshot images in the directory
        print(f"Looking for slide snapshots in {output_dir}...")
        
        # Get all snapshot image files - look for both numbered (001_snapshot_) and old format (snapshot_) files
        snapshot_files = [f for f in os.listdir(output_dir) 
                        if (re.search(r'^\d+_snapshot_', f) or f.startswith("snapshot_")) 
                        and (f.endswith(".png") or f.endswith(".jpg"))]
        
        if not snapshot_files:
            print(f"Warning: No slide snapshot images found in {output_dir}")
            # Check if there are any PNG files at all
            all_image_files = [f for f in os.listdir(output_dir) if f.endswith(".png") or f.endswith(".jpg")]
            if all_image_files:
                print(f"Found {len(all_image_files)} non-snapshot image files. Will use those instead.")
                snapshot_files = all_image_files
            else:
                print("No image files found at all. Unable to continue.")
                return []
        
        # Sort snapshot files naturally
        # Try to sort by slide number first if they follow a numeric pattern
        try:
            # Try to extract numbers from filenames (like "01_" in "01_slide.png")
            def extract_number(filename):
                match = re.search(r'^(\d+)', filename)
                if match:
                    return int(match.group(1))
                return float('inf')  # No number, sort at end
                
            snapshot_files.sort(key=extract_number)
        except (ValueError, IndexError):
            # If number extraction fails, sort alphabetically
            snapshot_files.sort()
        
        # Create full paths
        slide_image_paths = [os.path.join(output_dir, f) for f in snapshot_files]
        
        print(f"Found {len(slide_image_paths)} slide snapshot images")
        
        # Print the first few slide paths to help debugging
        if slide_image_paths and len(slide_image_paths) > 0:
            print("\nDetected slide order:")
            for i, path in enumerate(slide_image_paths[:min(5, len(slide_image_paths))]):
                basename = os.path.basename(path)
                print(f"  Slide {i+1}: {basename}")
            
            if len(slide_image_paths) > 5:
                print(f"  ... plus {len(slide_image_paths) - 5} more slides")
        
        return slide_image_paths
        
    except Exception as e:
        print(f"Error finding slide snapshots: {str(e)}")
        traceback.print_exc()
        return []


def load_speaker_notes(notes_file):
    """
    Load speaker notes from the enhanced notes JSON file.
    
    Args:
        notes_file: Path to the enhanced notes JSON file
        
    Returns:
        Dictionary mapping slide titles/identifiers to speaker notes
    """
    print(f"Loading speaker notes from {notes_file}...")
    
    try:
        with open(notes_file, 'r') as f:
            content = f.read()
            # Check if the file is in JSON format
            try:
                notes_data = json.loads(content)
                print(f"Loaded {len(notes_data)} speaker notes entries.")
                return notes_data
            except json.JSONDecodeError:
                # If it's not valid JSON, try to extract JSON from the content
                json_match = re.search(r'```json\n(.+?)\n```', content, re.DOTALL)
                if json_match:
                    notes_data = json.loads(json_match.group(1))
                    print(f"Extracted and loaded {len(notes_data)} speaker notes entries.")
                    return notes_data
                else:
                    print("Error: Could not parse speaker notes as JSON.")
                    return {}
    except FileNotFoundError:
        print(f"Error: Speaker notes file not found at {notes_file}")
        return {}
    except Exception as e:
        print(f"Error loading speaker notes: {str(e)}")
        traceback.print_exc()
        return {}


def match_slides_to_notes(slide_image_paths, notes_data):
    """
    Match slide images to their corresponding speaker notes.
    
    Args:
        slide_image_paths: List of slide image file paths
        notes_data: Dictionary mapping slide titles/identifiers to speaker notes
        
    Returns:
        List of tuples containing (slide_image_path, speaker_note)
    """
    print("Matching slides to speaker notes...")
    
    matches = []
    notes_keys = list(notes_data.keys())
    
    # Sort slide images numerically
    slide_image_paths = sorted(slide_image_paths, 
                              key=lambda x: int(re.search(r'slide(\d+)', os.path.basename(x)).group(1)) 
                              if re.search(r'slide(\d+)', os.path.basename(x)) else 0)
    
    # Match slides to notes based on position/index
    for i, slide_path in enumerate(slide_image_paths):
        if i < len(notes_keys):
            note_key = notes_keys[i]
            note_text = notes_data[note_key]
            matches.append((slide_path, note_text))
        else:
            # If we run out of notes, use empty text
            matches.append((slide_path, ""))
    
    print(f"Matched {len(matches)} slides with speaker notes.")
    return matches


def setup_text_to_speech_client():
    """
    Set up the Google Cloud Text-to-Speech client.
    
    Returns:
        Text-to-Speech client or None if setup fails
    """
    try:
        # Check for service account file
        service_account_path = os.path.join(os.getcwd(), GCP_SERVICE_ACCOUNT_FILE)
        if os.path.exists(service_account_path):
            # Set environment variable for authentication
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
        
        # Create the client
        client = texttospeech.TextToSpeechClient()
        print("Google Cloud Text-to-Speech client initialized successfully.")
        return client
    except Exception as e:
        print(f"Error setting up Text-to-Speech client: {str(e)}")
        print("Make sure you have set up a Google Cloud project with Text-to-Speech API enabled")
        print("and downloaded your service account key.")
        return None


def generate_audio_for_slide(text, output_file, tts_client):
    """
    Generate audio for a single slide using Google Cloud TTS.
    If Google Cloud TTS fails, falls back to local TTS if available.
    
    Args:
        text: Text to convert to speech
        output_file: Output audio file path
        tts_client: Google Cloud TTS client
        
    Returns:
        Path to generated audio file, or None if generation failed
    """
    if not text.strip():
        print("No text provided for speech synthesis.")
        return None
    
    # First try: Google Cloud TTS
    try:
        # Set the text input to be synthesized
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Build the voice request
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Studio-O",  # A premium female voice
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        # Select the type of audio file
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Perform the text-to-speech request
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Write the response to the output file
        with open(output_file, "wb") as out:
            out.write(response.audio_content)
        
        print(f"Audio content written to: {output_file} (using Google Cloud TTS)")
        return output_file
        
    except Exception as e:
        print(f"Error with Google Cloud TTS: {e}")
        print("Attempting to use local TTS fallback...")
        
        # Try local TTS using pyttsx3
        try:
            return generate_audio_local_tts(text, output_file)
        except Exception as local_e:
            print(f"Local TTS also failed: {local_e}")
            
            # Try one more approach: macOS say command
            try:
                return generate_audio_macos_say(text, output_file)
            except Exception as mac_e:
                print(f"macOS TTS also failed: {mac_e}")
                return None


def generate_audio_local_pyttsx3(text, output_file):
    """
    Generate audio using local pyttsx3 TTS engine.
    
    Args:
        text: Text to convert to speech
        output_file: Output audio file path
        
    Returns:
        Path to generated audio file, or None if generation failed
    """
    try:
        import pyttsx3
        
        # Initialize the TTS engine
        engine = pyttsx3.init()
        
        # Set properties
        engine.setProperty('rate', 150)  # Speed of speech
        engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        
        # Get available voices and set a good one if available
        voices = engine.getProperty('voices')
        if voices:
            # Try to find a good voice
            for voice in voices:
                if 'en' in voice.languages and ('US' in voice.id or 'GB' in voice.id):
                    engine.setProperty('voice', voice.id)
                    break
        
        # Use a temporary WAV file since pyttsx3 doesn't support MP3 directly
        temp_wav = output_file.replace('.mp3', '.wav')
        
        # Convert text to speech and save to file
        engine.save_to_file(text, temp_wav)
        engine.runAndWait()
        
        # Convert WAV to MP3 if needed
        if output_file.endswith('.mp3'):
            try:
                # Try using ffmpeg to convert
                cmd = [
                    'ffmpeg', '-y', '-i', temp_wav,
                    '-acodec', 'libmp3lame', '-q:a', '2',
                    output_file
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Remove the temporary WAV file
                os.remove(temp_wav)
            except Exception:
                # If ffmpeg conversion fails, just use the WAV file
                output_file = temp_wav
                
        print(f"Audio content written to: {output_file} (using local TTS)")
        return output_file
    except ImportError:
        print("pyttsx3 not installed. Please install with: pip install pyttsx3")
        raise
    except Exception as e:
        print(f"Error with local TTS: {e}")
        raise


def generate_audio_macos_say(text, output_file):
    """
    Generate audio using macOS 'say' command.
    
    Args:
        text: Text to convert to speech
        output_file: Output audio file path
        
    Returns:
        Path to generated audio file, or None if generation failed
    """
    try:
        # Check if we're on macOS
        if sys.platform != 'darwin':
            print("macOS 'say' command only available on macOS.")
            raise OSError("Not running on macOS")
        
        # Create a temporary AIFF file (macOS say supports this)
        temp_aiff = output_file.replace('.mp3', '.aiff')
        
        # Use macOS say command to generate speech
        # Create a temporary file for the text to avoid command line length limitations
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(text)
            temp_file_path = temp_file.name
            
        # Use the say command with the text file
        subprocess.run(
            ['say', '-f', temp_file_path, '-o', temp_aiff],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        # Clean up the temporary text file
        os.unlink(temp_file_path)
        
        # Convert AIFF to MP3 if the output should be MP3
        if output_file.endswith('.mp3'):
            try:
                # Try using ffmpeg to convert
                cmd = [
                    'ffmpeg', '-y', '-i', temp_aiff,
                    '-acodec', 'libmp3lame', '-q:a', '2',
                    output_file
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Remove the temporary AIFF file
                os.remove(temp_aiff)
            except Exception:
                # If ffmpeg conversion fails, just use the AIFF file
                output_file = temp_aiff
        
        print(f"Audio content written to: {output_file} (using macOS TTS)")
        return output_file
    except Exception as e:
        print(f"Error with macOS TTS: {e}")
        raise


def generate_audio_local_tts(text, output_file):
    """
    Generate audio using any available local TTS engine.
    Tries multiple methods in sequence.
    
    Args:
        text: Text to convert to speech
        output_file: Output audio file path
        
    Returns:
        Path to generated audio file, or None if generation failed
    """
    # Try pyttsx3 first
    try:
        return generate_audio_local_pyttsx3(text, output_file)
    except Exception:
        # If pyttsx3 fails, try macOS say command
        if sys.platform == 'darwin':
            try:
                return generate_audio_macos_say(text, output_file)
            except Exception:
                pass
    
    # If all fallbacks fail
    print("All local TTS methods failed.")
    return None


def create_slide_videos(slide_matches, audio_dir):
    """
    Create individual video clips for each slide with its audio.
    
    Args:
        slide_matches: List of tuples containing (slide_image_path, speaker_note)
        audio_dir: Directory to save audio files
        
    Returns:
        List of video clips if using MoviePy, or list of (image_path, audio_path, duration) tuples for fallback
    """
    print("Creating individual slide videos...")
    
    # Setup Text-to-Speech client
    tts_client = setup_text_to_speech_client()
    if not tts_client:
        print("Warning: Text-to-Speech client not available. Creating silent video.")
    
    slide_data = []
    
    for i, (slide_path, note_text) in enumerate(slide_matches):
        print(f"Processing slide {i+1}/{len(slide_matches)}...")
        
        # Generate audio file name
        audio_file = os.path.join(audio_dir, f"slide_{i+1:03d}.mp3")
        
        # Check slide type (title, module, or content)
        is_title_slide = False
        is_module_slide = False
        course_title = ""
        module_title = ""
        slide_filename = os.path.basename(slide_path)
        
        # Detect title slide (00_ prefix)
        if "00_snapshot" in slide_filename:
            is_title_slide = True
            # Extract course title from the provided note text or try to infer it from the filename
            if note_text:
                course_title = note_text.split('\n')[0]  # Use first line as title
            else:
                # Try to extract course title from other sources
                base_dir = os.path.dirname(os.path.dirname(slide_path))
                course_dir = os.path.basename(base_dir)
                course_title = course_dir.replace('_', ' ')
            print(f"Detected title slide! Course title: {course_title}")
            
        # Detect module slides (usually contain "Module" in the filename or have a specific pattern)
        elif "Module" in slide_filename or re.search(r'\d+_snapshot_Module', slide_filename):
            is_module_slide = True
            # Extract module name from filename
            module_match = re.search(r'\d+_snapshot_(.+?)\.png', slide_filename)
            if module_match:
                module_title = module_match.group(1).replace('_', ' ')
                # Clean up module title
                module_title = re.sub(r'Module_\d+__\d+__', '', module_title)
                module_title = module_title.replace('__', ': ')
            print(f"Detected module slide! Module title: {module_title}")
        
        # Generate audio for speaker notes
        audio_path = None
        if tts_client:
            # Always use the notes from 06_Enhanced_Notes.txt if available
            if note_text and note_text.strip():
                print(f"Using enhanced notes from 06_Enhanced_Notes.txt")
                audio_path = generate_audio_for_slide(note_text, audio_file, tts_client)
            # Only if no notes are available in the enhanced notes file, generate fallback content
            elif is_title_slide:
                # Create fallback welcome message for title slide
                welcome_message = f"Welcome to the course: {course_title}"
                print(f"No enhanced notes found. Using fallback title slide welcome audio: '{welcome_message}'")
                audio_path = generate_audio_for_slide(welcome_message, audio_file, tts_client)
                
            elif is_module_slide:
                # Create fallback introduction for module slides
                module_intro = f"Module: {module_title}"
                print(f"No enhanced notes found. Using fallback module introduction audio: '{module_intro}'")
                audio_path = generate_audio_for_slide(module_intro, audio_file, tts_client)
        
        # Determine slide duration
        duration = SLIDE_DURATION
        
        # If audio was generated, get its duration
        if audio_path and os.path.exists(audio_path):
            try:
                if USE_MOVIEPY:
                    audio_clip = mp.AudioFileClip(audio_path)
                    duration = audio_clip.duration
                else:
                    # For fallback: use ffprobe to get audio duration
                    import subprocess
                    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                           '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
                    try:
                        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if result.returncode == 0:
                            duration = float(result.stdout.decode('utf-8').strip())
                    except Exception as e:
                        print(f"Could not determine audio duration, using default: {e}")
            except Exception as e:
                print(f"Error getting audio duration for slide {i+1}: {str(e)}")
        
        # Process differently based on which library we're using
        if USE_MOVIEPY:
            # Create MoviePy clip
            img_clip = mp.ImageClip(slide_path)
            img_clip = img_clip.set_duration(duration)
            
            if audio_path and os.path.exists(audio_path):
                try:
                    audio_clip = mp.AudioFileClip(audio_path)
                    img_clip = img_clip.set_audio(audio_clip)
                except Exception as e:
                    print(f"Error setting audio for slide {i+1}: {str(e)}")
            
            slide_data.append(img_clip)
        else:
            # Store paths for alternative processing
            slide_data.append((slide_path, audio_path, duration))
    
    return slide_data


def create_final_video(slide_data, output_path):
    """
    Create the final video by concatenating individual slide videos.
    
    Args:
        slide_data: List of video clips or (image_path, audio_path, duration) tuples
        output_path: Path to save the final video
        
    Returns:
        Path to the final video or None if creation fails
    """
    try:
        print("Creating final video...")
        
        if USE_MOVIEPY:
            # Using MoviePy - set method to 'chain' to eliminate gaps between slides
            final_clip = mp.concatenate_videoclips(slide_data, method="chain")
            
            # Write the final video
            final_clip.write_videofile(
                output_path,
                fps=24,  # Higher fps for smoother transitions
                codec="libx264",
                audio_codec="aac"
            )
        else:
            # Fallback: use ffmpeg directly
            print("Using ffmpeg directly to create video...")
            temp_dir = os.path.dirname(output_path)
            file_list_path = os.path.join(temp_dir, "file_list.txt")
            
            # Create temporary folder for intermediate files
            temp_video_dir = os.path.join(temp_dir, "temp_videos")
            os.makedirs(temp_video_dir, exist_ok=True)
            
            # Create individual video segments for each slide
            segment_files = []
            for i, (img_path, audio_path, duration) in enumerate(slide_data):
                segment_path = os.path.join(temp_video_dir, f"segment_{i:03d}.mp4")
                
                # Command to create video segment from image with optional audio
                cmd = ['ffmpeg', '-y', '-loop', '1', '-i', img_path]
                if audio_path and os.path.exists(audio_path):
                    cmd.extend(['-i', audio_path, '-c:a', 'aac', '-shortest'])
                else:
                    cmd.extend(['-t', str(duration)])
                
                # These options ensure full slide image is visible with proper aspect ratio
                # -vf scale ensures the image is scaled properly while maintaining aspect ratio
                # -vf "scale='min(1920,iw)':min(1080,ih):force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
                cmd.extend([
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-vf', 'scale=1920:1080:force_original_aspect_ratio=1,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white',
                    '-r', '24',
                    segment_path
                ])
                
                try:
                    print(f"Creating segment {i+1}/{len(slide_data)}...")
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    segment_files.append(segment_path)
                except subprocess.CalledProcessError as e:
                    print(f"Error creating segment {i+1}: {e}")
            
            # Create file list for ffmpeg concat
            with open(file_list_path, 'w') as f:
                for segment in segment_files:
                    # Use relative path from the file_list.txt location
                    rel_segment = os.path.relpath(segment, os.path.dirname(file_list_path))
                    f.write(f"file '{rel_segment}'\n")
            
            # Concatenate all segments
            concat_cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', file_list_path, '-c', 'copy', output_path
            ]
            
            subprocess.run(concat_cmd, check=True)
        
        print(f"Final video saved to: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error creating final video: {str(e)}")
        traceback.print_exc()
        return None


def main(max_slides=None):
    """
    Main function to convert PowerPoint to video with audio narration.
    
    Args:
        max_slides: Maximum number of slides to process (for testing). None means process all slides.
    """
    print("=" * 70)
    print("PowerPoint to Video Converter with Audio Narration".center(70))
    print("=" * 70)
    
    # Get the current directory from file
    current_dir = get_current_directory()
    
    # Setup directories
    paths = setup_directories()
    
    # Determine PowerPoint file path
    pptx_files = [f for f in os.listdir(paths["base"]) 
                 if f.endswith(".pptx") and not f.startswith("~$")]
    
    if not pptx_files:
        print("Error: No PowerPoint file found in the current directory.")
        return
    
    pptx_file = os.path.join(paths["base"], pptx_files[0])
    print(f"Using PowerPoint file: {pptx_file}")
    
    # Determine speaker notes file path
    notes_file = os.path.join(paths["base"], ENHANCED_NOTES_FILE)
    
    # Extract slides
    slide_image_paths = extract_slides_as_images(pptx_file, paths["images"])
    
    if not slide_image_paths:
        return
    
    # Load speaker notes
    notes_data = load_speaker_notes(notes_file)
    
    if not notes_data:
        print("Warning: No speaker notes found. Creating silent video.")
    
    # Limit slides for testing if max_slides is specified
    if max_slides is not None and max_slides > 0:
        original_count = len(slide_image_paths)
        slide_image_paths = slide_image_paths[:max_slides]
        print(f"Testing mode: Limited to first {len(slide_image_paths)} slides out of {original_count}")
    
    # Match slides to speaker notes
    slide_matches = match_slides_to_notes(slide_image_paths, notes_data)
    
    # Create slide videos with audio
    slide_data = create_slide_videos(slide_matches, paths["audio"])
    
    if not slide_data:
        print("Error: Failed to create slide data.")
        return
    
    # Create final video
    output_name = OUTPUT_VIDEO_NAME
    if max_slides is not None:
        # Add 'test' to the output filename if in test mode
        name, ext = os.path.splitext(OUTPUT_VIDEO_NAME)
        output_name = f"{name}_test{ext}"
    
    output_video = os.path.join(paths["video"], output_name)
    create_final_video(slide_data, output_video)


def rename_slides(slides_dir):
    """
    Utility function to rename slides to the preferred format: '01-slide.png', '02-slide.png', etc.
    
    Args:
        slides_dir: Directory containing the slide images
        
    Returns:
        List of renamed slide paths
    """
    print(f"Renaming slides in {slides_dir} to standard format...")
    
    # Get all image files
    image_files = [f for f in os.listdir(slides_dir) 
                  if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not image_files:
        print("No slide images found.")
        return []
    
    # Sort files by their existing numbers if available
    # We use the same function from extract_slides_as_images but need to handle the tuple return
    def extract_slide_number(filename):
        # Use the main get_slide_number function but only return the number part
        _, number = get_slide_number(filename)
        if isinstance(number, int):
            return number
        return float('inf')
        
    # Sort files by their existing numbers if available
    image_files.sort(key=extract_slide_number)
    
    # Rename files
    renamed_paths = []
    for i, old_name in enumerate(image_files):
        # Keep original extension
        ext = os.path.splitext(old_name)[1]
        # Create new name: 01-slide.png, 02-slide.png, etc.
        new_name = f"{i+1:02d}-slide{ext}"
        old_path = os.path.join(slides_dir, old_name)
        new_path = os.path.join(slides_dir, new_name)
        
        # Don't rename if already in correct format
        if old_name == new_name:
            print(f"Slide {i+1} already has correct name: {old_name}")
            renamed_paths.append(new_path)
            continue
            
        # Rename file
        try:
            os.rename(old_path, new_path)
            print(f"Renamed: {old_name} -> {new_name}")
            renamed_paths.append(new_path)
        except Exception as e:
            print(f"Error renaming {old_name} to {new_name}: {e}")
            renamed_paths.append(old_path)  # Keep original path if rename fails
    
    print(f"Renamed {len(renamed_paths)} slides.")
    return renamed_paths


def alternative_approach_without_gcp():
    """
    An alternative approach using locally available TTS libraries.
    This function demonstrates how to use pyttsx3 instead of Google Cloud TTS.
    """
    try:
        import pyttsx3
        
        def generate_audio_local(text, output_file):
            engine = pyttsx3.init()
            # Set properties (optional)
            engine.setProperty('rate', 150)  # Speed of speech
            engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
            
            # Use a female voice if available
            voices = engine.getProperty('voices')
            for voice in voices:
                if "female" in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break
            
            # Save to file
            engine.save_to_file(text, output_file)
            engine.runAndWait()
            return output_file
            
        print("Alternative approach using pyttsx3 is available if you can't use Google Cloud TTS.")
        print("Install with: pip install pyttsx3")
    except ImportError:
        print("Alternative TTS library pyttsx3 not installed.")


def check_dependencies():
    """
    Check for required dependencies and provide helpful info if missing.
    """
    missing = []
    optional = []
    
    # Required dependencies
    try:
        import pptx
    except ImportError:
        missing.append("python-pptx")
    
    try:
        from PIL import Image
    except ImportError:
        missing.append("pillow")
    
    # Optional dependencies with fallback implementations
    try:
        from google.cloud import texttospeech
    except ImportError:
        optional.append("google-cloud-texttospeech")
    
    # MoviePy is now optional since we have a direct ffmpeg fallback
    if not USE_MOVIEPY:
        optional.append("moviepy")
    
    # Check for ffmpeg if MoviePy is not available
    if not USE_MOVIEPY:
        try:
            import shutil
            if not shutil.which('ffmpeg'):
                print("Warning: ffmpeg command-line tool not found.")
                print("Please install ffmpeg for the fallback video creation method:")
                print("  macOS: brew install ffmpeg")
                print("  Linux: apt-get install ffmpeg")
                print("  Windows: Download from https://ffmpeg.org/download.html")
                missing.append("ffmpeg-cli")
        except Exception:
            pass
    
    if missing:
        print("Missing required dependencies:")
        print(f"pip install {' '.join([dep for dep in missing if not dep.endswith('-cli')])}")
        return False
    
    if optional:
        print("Optional dependencies (fallbacks available):")
        print(f"pip install {' '.join(optional)}")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert PowerPoint to video with audio narration")
    parser.add_argument("--max-slides", type=int, help="Maximum number of slides to process (for testing)")
    parser.add_argument("--rename-slides", action="store_true", help="Only rename slides to preferred format (01-slide.png) without creating video")
    args = parser.parse_args()
    
    check_dependencies()
    
    if args.rename_slides:
        # Get the current directory
        current_dir = get_current_directory()
        if not current_dir:
            print("Error: Could not determine current directory.")
            sys.exit(1)
            
        # Setup directories
        paths = setup_directories(current_dir)
        
        # Find PowerPoint file
        pptx_files = [f for f in os.listdir(current_dir) if f.lower().endswith(".pptx")]
        if not pptx_files:
            print("Error: No PowerPoint file found in the current directory.")
            sys.exit(1)
            
        pptx_file = os.path.join(current_dir, pptx_files[0])
        print(f"Using PowerPoint file: {pptx_file}")
        
        # Rename slides
        rename_slides(paths["images"])
    else:
        # Run the main process
        if check_dependencies():
            main(max_slides=args.max_slides)
        else:
            print("Please install missing dependencies before running this script.")
