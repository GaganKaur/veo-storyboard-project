import os
import re
from moviepy.editor import VideoFileClip, concatenate_videoclips

# --- USER CONFIGURATION ---

# 1. Set the path to the folder containing your 9 video scene files.
#    - If the clips are in the SAME folder as this script, you can just use '.'
#    - Otherwise, provide the full path, e.g., '/Users/gagankaur/Workspace/storyboard-project/my_clips'
CLIPS_DIRECTORY = 'video_generation_workspace/'

# 2. Set the name you want for the final combined movie file.
FINAL_OUTPUT_FILE = 'final_animated_short.mp4'

# --- END OF CONFIGURATION ---


def stitch_videos(clips_folder, output_filename):
    """
    Finds all .mp4 video clips in a directory, sorts them numerically,
    and stitches them into a single video file.
    """
    print(f"--- Starting Video Stitching Process ---")
    print(f"Searching for video clips in: '{os.path.abspath(clips_folder)}'")

    # Get all .mp4 files from the directory
    try:
        clip_files = [f for f in os.listdir(clips_folder) if f.endswith(".mp4")]
    except FileNotFoundError:
        print(f"\nERROR: The directory was not found.")
        print(f"Please make sure '{clips_folder}' is the correct path to your video clips.")
        return

    if not clip_files:
        print("\nERROR: No video clips (.mp4) were found in this directory.")
        return

    # --- IMPORTANT: Sort the clips numerically based on the numbers in their filenames ---
    def get_scene_number(filename):
        # This regular expression finds the first sequence of digits in the filename
        match = re.search(r'(\d+)', filename)
        return int(match.group(1)) if match else -1

    clip_files.sort(key=get_scene_number)
    
    print("\nFound and sorted the following clips to be stitched:")
    for clip_name in clip_files:
        print(f"  -> {clip_name}")

    try:
        # Create a list of VideoFileClip objects
        print("\nLoading clips into memory...")
        video_clips = [VideoFileClip(os.path.join(clips_folder, f)) for f in clip_files]

        # Concatenate the clips into one long clip
        print("Stitching clips together...")
        final_clip = concatenate_videoclips(video_clips, method="compose")

        # Write the final movie to a file
        print(f"Writing final movie to '{output_filename}'... (This may take a moment)")
        final_clip.write_videofile(output_filename, codec="libx264", audio_codec="aac")
        
        # Close all clips to release memory and file handles
        for clip in video_clips:
            clip.close()
        final_clip.close()
        
        print("\n--- SCRIPT FINISHED SUCCESSFULLY! ---")
        print(f"Your final movie has been saved as: {output_filename}")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED DURING STITCHING ---")
        print(f"Error: {e}")
        print("Please check that the video files are not corrupt and that you have enough memory.")


# This part runs the function when you execute the script
if __name__ == "__main__":
    stitch_videos(CLIPS_DIRECTORY, FINAL_OUTPUT_FILE)