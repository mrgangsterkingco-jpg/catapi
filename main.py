import subprocess
import json
from fastapi import FastAPI, Query, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_video_metadata(url):
    """ভিডিওর দৈর্ঘ্য এবং টাইটেল চেক করার জন্য"""
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except:
        return None

@app.get("/download")
async def stream_media(url: str = Query(...), type: str = Query("video")):
    
    # ১. ভিডিওর তথ্য নেওয়া
    meta = get_video_metadata(url)
    if not meta:
        return Response(content="Invalid URL or Private Video", status_code=400)

    title = meta.get('title', 'video').replace('"', '').replace("'", "")
    duration = meta.get('duration', 0) # সেকেন্ডে

    # ==================================================
    # স্মার্ট কোয়ালিটি লজিক (Smart Quality Logic)
    # ==================================================
    
    # ফ্রি সার্ভারের জন্য সেইফ লিমিট (৫ মিনিট = ৩০০ সেকেন্ড)
    SAFE_DURATION_LIMIT = 300 
    
    format_cmd = []
    ext = "mp4"

    if type == "audio":
        # অডিওর জন্য সবসময় সেরা কোয়ালিটি
        format_cmd = ['-f', 'bestaudio/best', '-x', '--audio-format', 'mp3']
        ext = "mp3"
    else:
        # ভিডিওর জন্য লজিক
        if duration < SAFE_DURATION_LIMIT:
            # ছোট ভিডিও: 4K বা সর্বোচ্চ কোয়ালিটি (Video+Audio Merge) ট্রাই করবে
            # ফ্রি সার্ভারে এটি হাই রিস্ক, কিন্তু আপনি চেয়েছেন তাই রাখা হলো
            format_cmd = ['-f', 'bestvideo+bestaudio/best', '--merge-output-format', 'mp4']
        else:
            # বড় ভিডিও: ক্র্যাশ এড়াতে সেইফ মোড (সাধারণত 720p/1080p Single File)
            # এটিতে সার্ভার প্রসেসিং লাগে না, তাই ফাস্ট ডাউনলোড হয়
            format_cmd = ['-f', 'best[ext=mp4]/best']
    
    # ফাইলের নাম সেট করা
    filename = f"{title}.{ext}"
    filename_header = filename.encode('ascii', 'ignore').decode('ascii') # নন-ইংলিশ ক্যারেক্টার বাদ দেওয়া

    # ২. yt-dlp কে প্রসেস হিসেবে চালানো এবং আউটপুট পাইপ করা
    # আমরা '-o', '-' ব্যবহার করছি যার মানে ফাইল ডিস্ক-এ সেভ না হয়ে স্ট্যান্ডার্ড আউটপুটে যাবে
    cmd = [
        'yt-dlp', 
        '--no-part', 
        '--quiet', 
        '-o', '-', 
        url
    ] + format_cmd

    # সাব-প্রসেস ওপেন করা
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # ৩. জেনারেটর ফাংশন: এটি একটু একটু করে ডেটা ব্রাউজারে পাঠাবে
    def iterfile():
        try:
            while True:
                chunk = proc.stdout.read(1024 * 64) # 64KB chunk
                if not chunk:
                    break
                yield chunk
        finally:
            proc.kill()

    # ৪. রেসপন্স পাঠানো
    headers = {
        "Content-Disposition": f'attachment; filename="{filename_header}"',
        "Content-Type": "application/octet-stream" if type == "video" else "audio/mpeg"
    }

    return StreamingResponse(iterfile(), headers=headers)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
