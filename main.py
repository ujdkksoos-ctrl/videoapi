from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
import yt_dlp
import uvicorn
import requests
import asyncio
import os
import uuid
from urllib.parse import quote

app = FastAPI()

# --- এই নতুন রুটটি UptimeRobot-এর জন্য যোগ করা হয়েছে ---
@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    return {
        "status": "Alive and kicking!", 
        "message": "API is running successfully. Use /get_video?url=YOUR_URL to fetch video data."
    }
# ---------------------------------------------------------

def fetch_yt_data(url):
    target_headers = {}
    target_user_agent = ""
    cookie_file = ""

    # ১. ফেসবুকের জন্য হেডার এবং কুকি
    if "facebook.com" in url or "fb.watch" in url:
        target_user_agent = 'Mozilla/5.0 (Linux; Android 14; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36'
        cookie_file = 'fb_cookis.txt' 
        target_headers = {
            'authority': 'm.facebook.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
        }
    # ২. ইনস্টাগ্রামের জন্য হেডার এবং কুকি
    elif "instagram.com" in url:
        target_user_agent = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36'
        cookie_file = 'cookies_insta.txt'
        target_headers = {
            'authority': 'www.instagram.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
        }
    # ৩. ইউটিউবের জন্য হেডার এবং কুকি
    else:
        target_user_agent = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36'
        cookie_file = 'youtube_cookies.txt' 
        target_headers = {
            'authority': 'm.youtube.com',
            'accept': 'text/css,*/*;q=0.1',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'style',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'same-origin',
        }

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'user_agent': target_user_agent,
        'http_headers': target_headers,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'format': 'bestvideo+bestaudio/best', # ইউটিউব এরর ফিক্স করার লজিক
    }

    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def download_sync(url: str, dest: str):
    # stream=True ব্যবহার করা হচ্ছে যেন পুরো ফাইল RAM-এ লোড না হয়
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)

async def download_async(url: str, dest: str):
    await asyncio.to_thread(download_sync, url, dest)

def cleanup_files(*file_paths):
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

@app.get("/merge")
async def merge_audio_video(video_url: str, audio_url: str, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    video_path = f"/tmp/{task_id}_video.mp4"
    audio_path = f"/tmp/{task_id}_audio.m4a"
    output_path = f"/tmp/{task_id}_output.mp4"

    try:
        # ফাইলগুলো সার্ভারের হার্ডডিস্কে /tmp ফোল্ডারে সেভ করা হচ্ছে
        await asyncio.gather(
            download_async(video_url, video_path),
            download_async(audio_url, audio_path)
        )

        # -c copy ব্যবহার করে প্রসেস করা ফলে CPU এবং RAM-এ চাপ পড়বে না
        cmd = [
            "ffmpeg", "-y", 
            "-i", video_path, 
            "-i", audio_path,
            "-c:v", "copy", 
            "-c:a", "copy", 
            "-map", "0:v:0", 
            "-map", "1:a:0?",
            "-shortest", 
            output_path
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Merge failed: {stderr.decode()}")
            
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Output file not generated")

        # ফাইলগুলো ডিলিট করার জন্য BackgroundTask সেট করা
        background_tasks.add_task(cleanup_files, video_path, audio_path, output_path)

        return FileResponse(
            path=output_path,
            media_type="video/mp4",
            filename="merged_video.mp4",
            background=background_tasks
        )

    except Exception as e:
        cleanup_files(video_path, audio_path, output_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_video")
async def get_video_info(request: Request, url: str):
    try:
        base_url = str(request.base_url)
        info = await asyncio.to_thread(fetch_yt_data, url)
        
        if not info:
            raise HTTPException(status_code=400, detail="Could not fetch data.")

        formats = info.get('formats', [])
        duration = info.get('duration') 
        available_formats = []

        # Find best audio direct URL for muxing
        best_audio_url = ""
        for f in reversed(formats):
            if f.get('acodec') != 'none' and f.get('vcodec') in ['none', None]:
                best_audio_url = f.get('url', '')
                break
        
        # Fallback if specific audio-only format is not found
        if not best_audio_url:
            for f in reversed(formats):
                if f.get('acodec') != 'none':
                    best_audio_url = f.get('url', '')
                    break

        for f in formats:
            ext = f.get('ext', 'N/A')
            if ext in ['mhtml'] or f.get('vcodec') == 'mhtml':
                continue

            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            direct_url = f.get('url', '')
            format_id = str(f.get('format_id', '')).lower()
            
            width = f.get('width')
            height = f.get('height')
            resolution_str = str(f.get('resolution', ''))

            has_video = vcodec != 'none' or width is not None or height is not None or 'x' in resolution_str
            has_audio = acodec != 'none'
            
            if format_id in ['hd', 'sd'] or 'progressive' in direct_url.lower():
                has_video, has_audio = True, True

            if has_video and has_audio:
                f_type = "Video + Audio"
            elif has_video:
                f_type = "Video Only (No Sound)"
            elif has_audio:
                f_type = "Audio Only"
            else:
                f_type = "Unknown Type"

            if f_type == "Audio Only":
                res = "Audio Only"
            else:
                if width and height: res = f"{width}x{height}"
                else: res = resolution_str if resolution_str != 'none' else "Unknown"

            raw_size = f.get('filesize') or f.get('filesize_approx')
            
            if not raw_size and duration and f.get('tbr'):
                raw_size = (f.get('tbr') * 1000 * duration) / 8
                
            if not raw_size and direct_url:
                try:
                    head_req = requests.head(direct_url, allow_redirects=True, timeout=5)
                    if 'Content-Length' in head_req.headers:
                        raw_size = int(head_req.headers['Content-Length'])
                except:
                    pass
            
            size_str = f"{float(raw_size)/(1024*1024):.2f} MB" if raw_size and raw_size > 0 else "Unknown"

            item_data = {
                "format_id": f.get('format_id', 'N/A'),
                "format_type": f_type,
                "resolution": res,
                "extension": ext,
                "size": size_str,
                "direct_url": direct_url
            }

            if f_type == "Video Only (No Sound)" and best_audio_url:
                merge_url = f"{base_url}merge?video_url={quote(direct_url)}&audio_url={quote(best_audio_url)}"
                item_data["merge_url"] = merge_url

            available_formats.append(item_data)

        available_formats.reverse()
        for index, item in enumerate(available_formats):
            item["sl"] = index + 1

        return {
            "status": "success",
            "platform": info.get('extractor_key', 'Unknown'),
            "title": info.get('title', 'video'),
            "total_formats": len(available_formats),
            "formats_list": available_formats
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
