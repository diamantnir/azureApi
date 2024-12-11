Before deploying, make sure the binaries are executable.

chmod +x ffmpeg
chmod +x ffprobe


Example usage:

curl -X POST \
     --data-binary "@/Users/yourname/Videos/sample_video.mp4" \
     "https://myfunctionapp.azurewebsites.net/api/shorten_video?filename=output.mp4"


For reference, my original function is trim.py which can be run from Windows DOS prompt with python trim.py filename.mp4
