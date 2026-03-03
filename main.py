from fastapi import FastAPI, HTTPException
import yt_dlp
import uvicorn
import requests

app = FastAPI()

@app.get("/get_video")
async def get_video_info(url: str):
    # প্ল্যাটফর্ম অনুযায়ী হেডার নির্বাচন
    target_headers = {}
    target_user_agent = ""

    if "facebook.com" in url or "fb.watch" in url:
        # Facebook Mobile Headers (Android 14)
        target_user_agent = 'Mozilla/5.0 (Linux; Android 14; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36'
        target_headers = {
            'authority': 'm.facebook.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'sec-ch-prefers-color-scheme': 'light',
            'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="125.0.6422.134", "Chromium";v="125.0.6422.134"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua-platform-version': '"14"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'viewport-width': '980',
        }
    elif "instagram.com" in url:
        # Instagram Mobile Headers (Pixel 5/Android 13)
        target_user_agent = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36'
        target_headers = {
            'authority': 'www.instagram.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-prefers-color-scheme': 'light',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-full-version-list': '"Not:A-Brand";v="99.0.0.0", "Google Chrome";v="145.0.7632.117", "Chromium";v="145.0.7632.117"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-model': '"Pixel 5"',
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua-platform-version': '"13"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'viewport-width': '383',
            'referer': 'https://www.google.com/',
        }
    else:
        # YouTube Mobile Headers (Pixel 7/Android 13)
        target_user_agent = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36'
        target_headers = {
            'authority': 'm.youtube.com',
            'accept': 'text/css,*/*;q=0.1',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-model': '"Pixel 5"',
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua-platform-version': '"13"',
            'sec-fetch-dest': 'style',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'same-origin',
            'x-browser-channel': 'stable',
            'x-browser-copyright': 'Copyright 2026 Google LLC. All Rights reserved.',
            'x-browser-year': '2026',
            'priority': 'u=0',
        }

    ydl_opts_info = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'user_agent': target_user_agent,
        'http_headers': target_headers,
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = info.get('formats', [])
            duration = info.get('duration') 
            available_formats = []

            for f in formats:
                if f.get('ext') in ['mhtml'] or f.get('vcodec') == 'mhtml':
                    continue

                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                direct_url = f.get('url')
                format_id = str(f.get('format_id', '')).lower()

                # Identify if format has video, audio, or both
                # Smart Fix for hd/sd progressive formats
                has_video = vcodec != 'none' or f.get('width') is not None
                has_audio = acodec != 'none'
                
                if format_id in ['hd', 'sd'] or 'progressive' in (direct_url or '').lower():
                    has_video = True
                    has_audio = True

                # Define clear format type
                if has_video and has_audio:
                    format_type = "Video + Audio"
                elif has_video and not has_audio:
                    format_type = "Video Only (No Sound)"
                elif not has_video and has_audio:
                    format_type = "Audio Only"
                else:
                    format_type = "Unknown Type"

                # Resolution
                if not has_video and has_audio:
                    res = "Audio Only"
                else:
                    width = f.get('width', '?')
                    height = f.get('height', '?')
                    res = f"{width}x{height}" if width != '?' else f.get('resolution', 'Unknown')
                    
                    if res == 'Unknown' and format_id == 'hd': res = "HD Video"
                    elif res == 'Unknown' and format_id == 'sd': res = "SD Video"
                
                fps = f.get('fps')
                fps_str = f"{fps}fps" if fps else "N/A"
                quality_note = f.get('format_note', 'N/A')
                
                # Size calculation logic
                raw_size = f.get('filesize') or f.get('filesize_approx')

                if not raw_size and duration:
                    tbr = f.get('tbr')
                    if tbr:
                        raw_size = (tbr * 1000 * duration) / 8

                if not raw_size and direct_url:
                    try:
                        headers = {'User-Agent': target_user_agent}
                        head_req = requests.head(direct_url, headers=headers, allow_redirects=True, timeout=2)
                        if 'Content-Length' in head_req.headers:
                            raw_size = int(head_req.headers['Content-Length'])
                    except Exception:
                        pass 

                size_str = f"{float(raw_size)/(1024*1024):.2f} MB" if raw_size and raw_size > 0 else "Unknown"

                # Append to list
                available_formats.append({
                    "format_id": f.get('format_id', 'N/A'),
                    "format_type": format_type,
                    "has_video": has_video,
                    "has_audio": has_audio,
                    "resolution": res,
                    "quality_note": quality_note,
                    "fps": fps_str,
                    "extension": f.get('ext', 'N/A'),
                    "size": size_str,
                    "vcodec": vcodec,
                    "acodec": acodec,
                    "direct_url": direct_url
                })

            available_formats.reverse()

            for index, item in enumerate(available_formats):
                item["sl"] = index + 1

            return {
                "status": "success",
                "platform": info.get('extractor_key', 'Unknown'),
                "title": info.get('title', 'Unknown Title'),
                "total_formats": len(available_formats),
                "formats_list": available_formats
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
