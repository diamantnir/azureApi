import logging
import azure.functions as func
import os
import tempfile
import subprocess
import json
from requests_toolbelt.multipart import decoder
from io import BytesIO

# Define paths to ffmpeg and ffprobe binaries
ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg')
ffprobe_path = os.path.join(os.getcwd(), 'ffprobe')

def shorten_video(input_file, total_duration, fps, desired_duration=4.0, speed_up_audio=True):
    # Get the input video filename and folder
    folder = os.path.dirname(input_file)
    filename = os.path.basename(input_file)
    name, ext = os.path.splitext(filename)

    # Calculate the frame skip factor (X) to get a 4-second video
    total_frames = int(fps * total_duration)
    target_frames = int(fps * desired_duration)
    frame_skip = max(1, total_frames // target_frames)
    print("total_frames:", total_frames, ", target_frames:", target_frames, ", frame_skip:", frame_skip)

    # Output file path
    output_file = os.path.join(folder, f"{name}_shortened{ext}")

    # FFmpeg command for video-only speed adjustment
    if speed_up_audio:
        # Calculate the speed-up factor for both video and audio
        speed_factor = total_duration / desired_duration
        cmd_ffmpeg = (
            f"\"{ffmpeg_path}\" -i \"{input_file}\" -hide_banner -loglevel error "
            f"-vf \"setpts=PTS/{speed_factor}\" -af \"atempo={speed_factor}\" -y \"{output_file}\""
        )
    else:
        # Command for video-only frame selection (no audio speed change)
        cmd_ffmpeg = (
            f"\"{ffmpeg_path}\" -i \"{input_file}\" -hide_banner -loglevel error "
            f"-vf \"select=not(mod(n\\,{frame_skip})),setpts=N/FRAME_RATE/TB\" -vsync vfr -map 0:v -y \"{output_file}\""
        )

    subprocess.run(cmd_ffmpeg, shell=True)
    return output_file

def get_video_duration(input_file):
    cmd_get_metadata = f"\"{ffprobe_path}\" -v quiet -print_format json -show_streams \"{input_file}\""
    result = subprocess.run(cmd_get_metadata, shell=True, capture_output=True, text=True)
    metadata = json.loads(result.stdout)

    # Find the video stream
    video_stream = next(stream for stream in metadata['streams'] if stream['codec_type'] == 'video')

    # Extract duration and fps
    duration = float(video_stream['duration'])
    width = int(video_stream['width'])
    height = int(video_stream['height'])
    fps = eval(video_stream['r_frame_rate'])  # This could be a fraction
    response_data = {"duration": duration, "fps": fps, "width": width, "height": height}
    return response_data

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    content_type = req.headers.get('Content-Type', '')
    filename = 'input_video.mp4'

    if 'multipart/form-data' in content_type:
        # Parse multipart/form-data
        multipart_data = decoder.MultipartDecoder(req.get_body(), content_type)
        file_content = None
        for part in multipart_data.parts:
            if part.headers.get(b'Content-Disposition'):
                content_disposition = part.headers[b'Content-Disposition'].decode()
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[1].strip('\"')
                    file_content = part.content
                    break
        if not file_content:
            return func.HttpResponse("No file found in the request.", status_code=400)
    else:
        # Assume binary data in body
        file_content = req.get_body()
        filename = req.params.get('filename', 'input_video.mp4')

    # Write the file content to a temporary file
    with tempfile.TemporaryDirectory() as tmpdirname:
        input_filepath = os.path.join(tmpdirname, filename)
        with open(input_filepath, 'wb') as f:
            f.write(file_content)

        # Process the file
        try:
            response = get_video_duration(input_filepath)
            total_duration = response['duration']
            fps = response['fps']
            output_filepath = shorten_video(input_filepath, total_duration, fps)
        except Exception as e:
            logging.error(f"Error processing video: {e}")
            return func.HttpResponse("Failed to process video.", status_code=500)

        # Read the output file and return it
        with open(output_filepath, 'rb') as f:
            output_data = f.read()

    # Return the processed file
    response = func.HttpResponse(
        body=output_data,
        status_code=200,
        mimetype='video/mp4'
    )
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
