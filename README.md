# Veo Storyboard Project

## Project Details

This project provides an automated pipeline to accelerate the pre-production workflow for creating animated short films. The core function is to take an existing video (such as a storyboard, animatic, or another movie) and transform it into a series of detailed, scene-by-scene text prompts.

These prompts are specifically engineered for a generative video AI model like Google's Veo. They re-imagine the original video's action, timing, and camera work, but with new, specified characters (e.g., Dracula and Martha from Hotel Transylvania). The output is a collection of numbered text files, with each file containing a prompt for a single 8-second video clip.

The primary goal is to automate the most time-consuming parts of prompt engineering, ensuring consistency in art style and character descriptions across all generated scenes. This allows creators to focus on the final video generation and post-production.

*   **Stage 1:** Prompt Generation (prompts_gen.py)
This script analyzes the source video, breaking it down into chronological, 8-second chunks. It then creatively re-interprets the action in each chunk for a new set of characters (e.g., Dracula and Martha from Hotel Transylvania). The final output is a collection of numbered text files containing detailed prompts, which are saved to a Google Cloud Storage (GCS) bucket.
*   **Stage 2:** Chained Video Generation (automate-vid-gen.py)
This script iterates through the generated prompts. For each prompt, it calls a generative video AI model like Google's Veo to create a video clip. To ensure scene-to-scene continuity, from the second prompt onwards, it captures the last frame of the previously generated clip and uses it as an additional visual input alongside the text prompt. This "frame-chaining" technique helps the AI model create a seamless and coherent final animation.

## Features

*   **Video Ingestion:** Ingests a source video directly from a Google Cloud Storage (GCS) bucket.
*   **Automated Analysis:** Breaks the source video down into chronological, 8-second chunks and analyzes the action within each.
*   **Character Replacement:** Uses Gemini to creatively re-interpret the analyzed actions for a new set of characters.
*   **Consistent Prompt Engineering:** Automatically generates detailed prompts for each video chunk, embedding character descriptions in every prompt to maintain visual consistency.
*   **Organized Output:** Saves each prompt as a separate, numbered .txt file in a dedicated GCS bucket folder, ready for the next stage of the production pipeline.

## Project Structure

STORYBOARD-PROJECT/
├── .gitignore # Specifies files and folders for Git to ignore.
├── prompts_gen.py # STAGE 1: Analyzes video and generates prompt files.
├── automate-vid-gen.py # STAGE 2: Iterates prompts and generates video clips using frame-chaining.
├── stitch.py # Utility script to combine final video clips.
├── prompts&actions.json # Example input file for prompts and actions.
├── requirements.txt # Lists all Python dependencies for the project.
└── README.md # This documentation file.

## Getting Started

Follow these steps to set up and run the full pipeline.

### Prerequisites

-   A Google Cloud Platform (GCP) project.
-   A Google Cloud Storage (GCS) bucket within that project.
-   A Google AI Studio API Key with access to the Gemini and Veo APIs.
-   Python 3.8 or higher installed.
-   Git installed for version control.

### Project Setup

1. **Clone the Repository**

Clone this repository to your local machine:

```bash
git clone https://github.com/your-username/storyboard-project.git
cd storyboard-project
```

2. **Install Dependencies**

This project uses several Python libraries. It is highly recommended to do this within a Python virtual environment to avoid conflicts with other projects.
Create and activate a virtual environment (optional but recommended):

```bash
python3 -m venv venv
source venv/bin/activate
```

**Install all required packages**
```bash
pip install -r requirements.txt
```

3. **Configure Your Environment**
Both prompts_gen.py and automate-vid-gen.py require you to set your specific GCP and API details. Open each file and update the configuration variables at the top:
File(s): prompts_gen.py and automate-vid-gen.py
# --- Configuration ---
GCP_PROJECT_ID = "your-gcp-project-id"        # <-- Replace with your GCP Project ID
GCS_BUCKET_NAME = "your-gcs-bucket-name"    # <-- Replace with your GCS Bucket Name
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"      # <-- Replace with your actual API Key

4. **Prepare Your Source Video**
Upload the source video you want to analyze to the root of your GCS bucket.

## Running the Pipeline
The process is broken into two main stages.
**Stage 1:** Generate the Prompts
First, run the prompts_gen.py script to analyze your video and create the necessary text prompts.
1. **Configure the script:** Open prompts_gen.py and update the SOURCE_VIDEO_FILENAME variable at the bottom to match the name of the file you uploaded to GCS.
# In prompts_gen.py, at the bottom
if __name__ == "__main__":
    SOURCE_VIDEO_FILENAME = "your_source_video.mp4" # <-- Replace
    run_prompt_generation_pipeline(SOURCE_VIDEO_FILENAME)

2. **Execute the script:**
```bash
python prompts_gen.py
```

Output of Stage 1: Upon successful completion, you will find a new folder in your GCS bucket named final_prompts/, containing numbered .txt files (e.g., 001_chunk_prompt.txt, 002_chunk_prompt.txt, etc.).

**Stage 2:** Generate the Chained Video Clips
Next, run the automate-vid-gen.py script. This script will automatically find the prompts generated in Stage 1 and use them to create the video clips.
Execute the script:
```bash
python automate-vid-gen.py
```

This script will iterate through your prompts, generating a video for each one. For every scene after the first, it will save the last frame, use it as input for the next scene, and then save the newly generated clip.
Output of Stage 2: You will have a local folder (e.g., generated_clips/) containing all the final, numbered video scene files.

**(Optional) Stage 3:** Stitch the Final Movie
After all the individual clips have been generated, you can combine them into a single movie using the stitch.py utility.
Configure the stitcher: Open stitch.py and ensure the CLIPS_DIRECTORY variable points to the folder where your clips were saved in Stage 2.
Execute the script:
```bash
python stitch.py
```

This will create a final .mp4 file containing your complete animated short.