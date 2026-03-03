from fastapi import FastAPI, HTTPException
import yt_dlp
import uvicorn
import requests
import asyncio

app = FastAPI()

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

@app.get("/get_video")
async def get_video_info(url: str):
    try:
        info = await asyncio.to_thread(fetch_yt_data, url)
        
        if not info:
            raise HTTPException(status_code=400, detail="Could not fetch data. Cookies might be expired or invalid.")

        formats = info.get('formats', [])
        duration = info.get('duration') 
        available_formats = []

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

            available_formats.append({
                "format_id": f.get('format_id', 'N/A'),
                "format_type": f_type,
                "resolution": res,
                "extension": ext,
                "size": size_str,
                "direct_url": direct_url
            })

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
