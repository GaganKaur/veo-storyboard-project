import google.generativeai as genai
from google.cloud import storage
import os
import json
import time
import tempfile

# --- Configuration ---
GCP_PROJECT_ID = "<GCP_PROJECT_ID>"
GCS_BUCKET_NAME = "<GCS_BUCKET_NAME>" 
GEMINI_API_KEY = "<GEMINI_API_KEY>"

# --- Initialization ---
genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client(project=GCP_PROJECT_ID)

# --- GCS Helper Functions ---
def upload_string_to_gcs(bucket_name, source_data, destination_blob_name, content_type='text/plain'):
    """MODIFIED: Uploads string data to a GCS bucket with a specified content type."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(source_data, content_type=content_type)
        print(f"Successfully uploaded data to gs://{bucket_name}/{destination_blob_name}")
    except Exception as e:
        print(f"Error uploading to GCS: {e}")
        raise

def download_from_gcs(bucket_name, source_blob_name):
    """Downloads data from a GCS bucket and returns it as bytes for JSON loading."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        return blob.download_as_bytes()
    except Exception as e:
        print(f"Error downloading from GCS: {e}")
        raise

# --- Pipeline Step Functions ---

def step1_analyze_video_in_chunks(gcs_video_uri, output_gcs_path, chunk_duration=8):
    """
    Uses the robust download-then-upload method to handle the video.
    """
    print("--- Starting Step 1: Analyze Video in Time-Based Chunks ---")
    temp_local_filename = None
    try:
        blob_name = gcs_video_uri.replace(f"gs://{GCS_BUCKET_NAME}/", "")
        _, temp_local_filename = tempfile.mkstemp(suffix=".mp4")
        print(f"Downloading {gcs_video_uri} to temporary file: {temp_local_filename}...")
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(temp_local_filename)
        print("Download complete.")

        print("Uploading temporary file to Gemini for processing...")
        video_file = genai.upload_file(path=temp_local_filename)
        
        print("File upload initiated. Waiting for processing to complete...")
        while video_file.state.name == "PROCESSING":
            print("... Checking status in 10 seconds ...")
            time.sleep(10)
            video_file = genai.get_file(name=video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError(f"Video processing failed: {video_file.error}")
        print("Video processed successfully!")

        prompt = """
    Analyze the provided storyboard video. Deconstruct it into a detailed, scene-by-scene breakdown.
    For each scene, provide the following in a JSON object:
    - scene_number: A sequential integer.
    - timestamp_start: The start time of the scene in HH:MM:SS.
    - timestamp_end: The end time of the scene in HH:MM:SS.
    - setting_description: Description of the environment and location.
    - character_actions: Description of character actions, expressions, and movements.
    - dialogue: Transcription of any dialogue.
    - camera_shot: Description of camera angle, shot type, and movement.
    Ensure the output is a single, valid JSON array of scenes.
    """
        model = genai.GenerativeModel(model_name="gemini-2.5-pro")
        response = model.generate_content(
            [prompt, video_file],
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json"),
            request_options={"timeout": 600}
        )
        
        upload_string_to_gcs(GCS_BUCKET_NAME, response.text, output_gcs_path, content_type='application/json')
        genai.delete_file(name=video_file.name)
        print(f"Cleaned up processed file from Gemini service.")
    finally:
        if temp_local_filename and os.path.exists(temp_local_filename):
            os.remove(temp_local_filename)
            print(f"Deleted temporary local file: {temp_local_filename}")
    print("--- Finished Step 1 ---")


def step2_generate_character_descriptions(output_gcs_path):
    """
    Generates character descriptions and saves them as a JSON file to GCS.
    """
    print("\n--- Starting Step 2: Generate Character Descriptions ---")
    model = genai.GenerativeModel(model_name="gemini-2.5-pro")
    prompt = """Create detailed character descriptions for Dracula from the 'Hotel Transylvania' movie franchise for a new animated short.
    The output must be a JSON object with two keys: "dracula" and "martha".
    For each character, detail their:
    - physical_appearance: Look, clothing, art style consistency.
    - personality_traits: Core personality traits.
    - mannerisms_and_gestures: Typical movements and expressions.
    - voice_style: Tone and speaking patterns.
    - For Martha's character from the 'Hotel Transylvania" movie franchise consider Martha as a beautiful female vampire with long, wavy black hair and bright blue eyes. She is slender and pale-skinned, often seen wearing a black long-sleeved dress and a black choker. She also sports black shoes and sometimes has black lipstick and nail polish. 
    """
    response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(response_mime_type="application/json"))
    upload_string_to_gcs(GCS_BUCKET_NAME, response.text, output_gcs_path, content_type='application/json')
    print("--- Finished Step 2 ---")


# --- Step 3 with parsing logic ---
def step3_generate_and_upload_separate_prompts(chunk_analysis_gcs_path, characters_gcs_path, output_gcs_folder):
    """
    MODIFIED: Generates prompts and uploads each one as a separate .txt file to a GCS folder.
    Includes more robust parsing logic.
    """
    print("\n--- Starting Step 3: Generate and Upload Separate Prompts ---")
    
    chunk_json_bytes = download_from_gcs(GCS_BUCKET_NAME, chunk_analysis_gcs_path)
    character_json_bytes = download_from_gcs(GCS_BUCKET_NAME, characters_gcs_path)
    model = genai.GenerativeModel(model_name="gemini-2.5-pro")

    # Prompt
    prompt = f"""
    You are an expert AI prompt engineer. Your task is to translate a series of action descriptions into detailed video prompts for Veo, ensuring character consistency.
    Use the provided video chunk analysis and the new character descriptions.

    **Character Descriptions to Embed:**
    {character_json_bytes.decode('utf-8')}

    **Original Video Chunk Analysis:**
    {chunk_json_bytes.decode('utf-8')}

    **Instructions:**
    For each chunk in the analysis, create a JSON object with a single key: "veo_prompt".
    
    CRITICAL: The `veo_prompt` string you generate MUST begin with a 'Character Consistency' section that includes the detailed physical descriptions of Dracula and Martha. This forces the video model to maintain their look across all clips.
    
    The rest of the prompt must include:
    - **Art Style:** "Vibrant 3D cartoon style of the Hotel Transylvania movies."
    - **Action:** A detailed description of Dracula and Martha performing the chunk's `action_description`, adapted to fit their unique personalities.
    - **Camera Work:** Retain the camera work (pan, close-up, static, etc.) from the original description.
    - **Duration:** The prompt must specify it is for an "8-second shot".

    The final output must be a single, valid JSON array of these new objects.
    """
    
    # Generate the single JSON response containing all prompts
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(response_mime_type="application/json"),
        request_options={"timeout": 600}
    )

    # --- PARSING LOGIC ---
    print("Generation complete. Parsing response and uploading individual prompt files...")
    prompts_data = json.loads(response.text)

    uploaded_count = 0
    for i, item in enumerate(prompts_data):
        prompt_text = None
        # Check if the item is a dictionary and has the 'veo_prompt' key
        if isinstance(item, dict) and 'veo_prompt' in item:
            prompt_text = item.get('veo_prompt')
        # ELSE, check if the item is just a string (the likely scenario)
        elif isinstance(item, str):
            prompt_text = item
        
        if not prompt_text:
            print(f"Skipping item {i+1} as no valid prompt text could be extracted.")
            continue
        
        # Create a numbered filename, e.g., "001_chunk_prompt.txt"
        chunk_number = i + 1
        destination_filename = f"{chunk_number:03d}_chunk_prompt.txt"
        
        # Create the full path in the GCS bucket folder
        destination_blob_name = f"{output_gcs_folder}{destination_filename}"

        # Upload the single prompt string to the new file
        upload_string_to_gcs(GCS_BUCKET_NAME, prompt_text, destination_blob_name)
        uploaded_count += 1
        
    print(f"--- Finished Step 3: Uploaded {uploaded_count} prompt files. ---")


# --- Main Pipeline Controller ---
def run_prompt_generation_pipeline(source_video_filename):
    """
    Executes the entire automated pipeline to generate prompts as separate files.
    """
    gcs_video_uri = f"gs://{GCS_BUCKET_NAME}/{source_video_filename}"
    chunk_analysis_path = "intermediate_assets/chunk_analysis.json"
    character_descriptions_path = "intermediate_assets/character_descriptions.json"
    final_prompts_gcs_folder = "final_prompts/"

    try:
        # Step 1: Analyze the source video into chunks
        step1_analyze_video_in_chunks(gcs_video_uri, chunk_analysis_path)
        
        # Step 2: Create the character sheets
        step2_generate_character_descriptions(character_descriptions_path)

        # Step 3: Final combined prompt and store in gcs
        step3_generate_and_upload_separate_prompts(
            chunk_analysis_path,
            character_descriptions_path,
            final_prompts_gcs_folder
        )
        
        print("\n\nPIPELINE COMPLETED SUCCESSFULLY!")
        print(f"The final individual prompts have been saved to your GCS bucket in the folder:")
        print(f"gs://{GCS_BUCKET_NAME}/{final_prompts_gcs_folder}")

    except Exception as e:
        print(f"\n\nPIPELINE FAILED. Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # --- TO RUN: Configure and Execute ---
    
    # 2. Set the exact filename of the video
    SOURCE_VIDEO_FILENAME = "your_input_video.mp4" 
    
    # 3. Run the script 
    run_prompt_generation_pipeline(SOURCE_VIDEO_FILENAME)