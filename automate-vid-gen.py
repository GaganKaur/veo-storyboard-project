# -*- coding: utf-8 -*-
import os
import time
from google.cloud import storage
from google import genai
from google.genai import types
from moviepy.editor import VideoFileClip, concatenate_videoclips
from IPython.display import Video, display, Markdown

# --- Configuration ---
PROJECT_ID = "veo-storyboard"  # @param {type:"string"}
LOCATION = "us-central1"            # @param {type:"string"}
GCS_BUCKET_NAME = "storyboard_video_veo"  # @param {type:"string"}
PROMPT_FOLDER = "final_prompts/"          # @param {type:"string"} # Optional: If prompts are in a subfolder
LOCAL_WORKSPACE = "video_generation_workspace"

# --- Model Configuration ---
video_model_text = "veo-3.0-generate-001"
video_model_image = "veo-3.0-generate-preview"
video_model_fast = "veo-3.0-fast-generate-001"


# --- Function Definitions ---

def initialize_clients():
    """Initializes and returns the Vertex AI and GCS clients."""
    print("Initializing clients...")
    cleaned_project_id = PROJECT_ID.strip()
    if not cleaned_project_id:
        raise ValueError("PROJECT_ID cannot be empty.")
    
    print(f"Using sanitized Project ID: '{cleaned_project_id}'")
    client = genai.Client(vertexai=True, project=cleaned_project_id, location=LOCATION)
    storage_client = storage.Client(project=cleaned_project_id)
    print("Clients initialized successfully.")
    return client, storage_client

def get_prompts_from_gcs(storage_client, bucket_name, folder):
    """Fetches and sorts prompts from a GCS bucket."""
    print(f"Fetching prompts from gs://{bucket_name}/{folder}...")
    bucket = storage_client.bucket(bucket_name)
    # Ensure the folder name ends with a '/' if it's not empty
    if folder and not folder.endswith('/'):
        folder += '/'
    blobs = list(bucket.list_blobs(prefix=folder))
    
    prompts = {}
    for blob in blobs:
        # Ensure we only read files and not the folder object itself
        if blob.name.endswith(".txt"):
            file_name = blob.name.split('/')[-1]
            if file_name: # check if filename is not empty
                content = blob.download_as_text()
                prompts[file_name] = content
            
    if not prompts:
         print(f"Warning: No .txt files found in gs://{bucket_name}/{folder}")
         return []
            
    sorted_prompts = [prompts[key] for key in sorted(prompts.keys())]
    print(f"Found and sorted {len(sorted_prompts)} prompts.")
    return sorted_prompts

def generate_video_from_text(client, prompt, output_filename):
    """Generates a video from a text prompt and saves it."""
    print(f"Generating video for prompt: '{prompt[:50]}...'")
    operation = client.models.generate_videos(
        model=video_model_fast,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            number_of_videos=1,
            duration_seconds=8,
            resolution="1080p",
            person_generation="allow_adult",
            enhance_prompt=True,
            generate_audio=True,
        ),
    )
    
    while not operation.done:
        print("Waiting for video generation to complete...")
        time.sleep(20)
        operation = client.operations.get(operation)

    if operation.response:
        video_bytes = operation.result.generated_videos[0].video.video_bytes
        with open(output_filename, "wb") as f:
            f.write(video_bytes)
        print(f"Video saved to {output_filename}")
        return output_filename
    else:
        raise Exception("Video generation failed. The operation completed without a response.")

# --- Generae Video from image and text ---
def generate_video_from_image_and_text(client, prompt, image_path, output_filename):
    """
    Generates a video from an image and text prompt using the correct
    types.Image.from_file() method.
    """
    print(f"Generating video from image '{image_path}' and prompt: '{prompt[:50]}...'")

    operation = client.models.generate_videos(
        model=video_model_image,
        prompt=prompt,
        image=types.Image.from_file(location=image_path),
        config=types.GenerateVideosConfig(
            aspect_ratio="16:9",
            number_of_videos=1,
            duration_seconds=8,
            resolution="1080p",
            person_generation="allow_adult",
            enhance_prompt=True,
            generate_audio=True,
        ),
    )

    while not operation.done:
        print("Waiting for video generation to complete...")
        time.sleep(20)
        operation = client.operations.get(operation)
        
    if operation.response:
        video_bytes = operation.result.generated_videos[0].video.video_bytes
        with open(output_filename, "wb") as f:
            f.write(video_bytes)
        print(f"Video saved to {output_filename}")
        return output_filename
    else:
        raise Exception("Video generation with image failed. The operation completed without a response.")

# --- Extract last frame ---
def extract_last_frame(video_path, output_image_path):
    """
    Extracts the last frame of a video and saves it as a an image.
    Includes validation to ensure the output file is created and not empty.
    """
    print(f"Extracting last frame from {video_path}...")
    try:
        with VideoFileClip(video_path) as clip:
            clip.save_frame(output_image_path, t=clip.duration - 0.1)

        # --- VALIDATION STEP ---
        # Check if the file was actually created and is not empty
        if not os.path.exists(output_image_path) or os.path.getsize(output_image_path) == 0:
            raise IOError(f"Failed to create a valid image file at {output_image_path}. The file is missing or empty.")
            
        print(f"Successfully extracted last frame to {output_image_path} (Size: {os.path.getsize(output_image_path)} bytes)")

    except Exception as e:
        print(f"An error occurred during frame extraction with moviepy: {e}")
        raise

def stitch_videos(video_paths, final_output_path):
    """Stitches multiple video clips into one."""
    print("Stitching all generated scenes together...")
    clips = [VideoFileClip(path) for path in video_paths]
    final_clip = concatenate_videoclips(clips, method="compose")
    final_clip.write_videofile(final_output_path, codec="libx264", audio_codec="aac")
    
    for clip in clips:
        clip.close()
    
    print(f"Final video saved to {final_output_path}")
    return final_output_path

def main():
    """Main function to run the video generation workflow."""
    if not os.path.exists(LOCAL_WORKSPACE):
        os.makedirs(LOCAL_WORKSPACE)
        
    client, storage_client = initialize_clients()
    prompts = get_prompts_from_gcs(storage_client, GCS_BUCKET_NAME, PROMPT_FOLDER)
    
    if not prompts:
        print("No prompts found in the specified GCS location. Exiting.")
        return

    generated_scene_paths = []
    last_frame_image_path = os.path.join(LOCAL_WORKSPACE, "last_frame.png")

    for i, prompt in enumerate(prompts):
        scene_number = i + 1
        output_video_path = os.path.join(LOCAL_WORKSPACE, f"scene_{scene_number}.mp4")
        
        print(f"\n--- Processing Scene {scene_number} ---")
        
        if i == 0:
            generate_video_from_text(client, prompt, output_video_path)
        else:
            previous_video_path = generated_scene_paths[i-1]
            extract_last_frame(previous_video_path, last_frame_image_path)
            generate_video_from_image_and_text(client, prompt, last_frame_image_path, output_video_path)
            
        generated_scene_paths.append(output_video_path)

    if generated_scene_paths:
        final_video_path = os.path.join(LOCAL_WORKSPACE, "final_movie.mp4")
        stitch_videos(generated_scene_paths, final_video_path)
        
        print("\n--- Final Movie ---")
        display(Video(final_video_path, embed=True, width=800))
    else:
        print("No scenes were generated.")

if __name__ == "__main__":
    main()