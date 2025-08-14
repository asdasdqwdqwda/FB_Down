import os
import threading
import time
import logging
import uuid
import re
import json
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key-here")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Global variables to track downloads
downloads_status = {}
downloads_lock = threading.Lock()
current_download_id = None

# Use a temporary directory for processing files
import tempfile
TEMP_DIR = Path(tempfile.gettempdir()) / "facebook_downloader"
TEMP_DIR.mkdir(exist_ok=True)

def is_valid_facebook_url(url):
    """Validate if the URL is a Facebook video URL"""
    try:
        parsed = urlparse(url)
        facebook_domains = ['facebook.com', 'www.facebook.com', 'm.facebook.com', 'fb.watch']
        return parsed.netloc.lower() in facebook_domains
    except Exception:
        return False

def convert_to_mobile_url(url):
    """Convert Facebook URL to mobile version which works better with yt-dlp"""
    try:
        parsed = urlparse(url)
        if 'facebook.com' in parsed.netloc:
            # Convert to mobile URL properly
            if 'www.facebook.com' in url:
                mobile_url = url.replace('www.facebook.com', 'm.facebook.com')
            elif parsed.netloc == 'facebook.com':
                mobile_url = url.replace('facebook.com', 'm.facebook.com')
            else:
                mobile_url = url  # Already mobile or other format
            return mobile_url
        return url
    except Exception:
        return url

def extract_video_info_fallback(url):
    """Fallback method to extract video info using web scraping"""
    try:
        # Try mobile version first as it's often less restricted
        mobile_url = convert_to_mobile_url(url)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        
        # Try mobile URL first
        for attempt_url in [mobile_url, url]:
            try:
                response = requests.get(attempt_url, headers=headers, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    break
            except:
                continue
        else:
            # If all attempts fail, return basic info
            return {
                'title': 'Facebook Video',
                'duration': 0,
                'webpage_url': url
            }
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to extract title
        title = 'Facebook Video'
        
        # Look for og:title meta tag
        og_title = soup.find('meta', property='og:title')
        if og_title and hasattr(og_title, 'get'):
            content = og_title.get('content')
            if content:
                title = content
        
        # If no og:title, try title tag
        if title == 'Facebook Video':
            title_tag = soup.find('title')
            if title_tag:
                page_title = title_tag.get_text().strip()
                if page_title and 'Facebook' not in page_title:
                    title = page_title
        
        # Try to find video duration
        duration = 0
        og_duration = soup.find('meta', property='og:video:duration')
        if og_duration and hasattr(og_duration, 'get'):
            content = og_duration.get('content')
            if content:
                try:
                    duration = int(content)
                except (ValueError, TypeError):
                    duration = 0
        
        # Try to extract thumbnail URL
        thumbnail_url = None
        og_image = soup.find('meta', property='og:image')
        if og_image and hasattr(og_image, 'get'):
            content = og_image.get('content')
            if content:
                thumbnail_url = content
        
        # Try to extract video description
        description = None
        og_description = soup.find('meta', property='og:description')
        if og_description and hasattr(og_description, 'get'):
            content = og_description.get('content')
            if content:
                description = content
        
        # Try to extract view count from title or other sources
        view_count = None
        if title and ('views' in title.lower() or 'view' in title.lower()):
            import re
            view_match = re.search(r'(\d+(?:\.\d+)?[KMB]?)\s*views?', title, re.IGNORECASE)
            if view_match:
                view_count = view_match.group(1)
        
        return {
            'title': title,
            'duration': duration,
            'webpage_url': url,
            'thumbnail': thumbnail_url,
            'description': description,
            'view_count': view_count
        }
        
    except Exception as e:
        logger.error(f"Fallback info extraction failed: {str(e)}")
        return {
            'title': 'Facebook Video',
            'duration': 0,
            'webpage_url': url
        }

def cleanup_old_files():
    """Clean up temporary files older than 1 hour"""
    try:
        current_time = time.time()
        for file_path in TEMP_DIR.glob("*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > 3600:  # 1 hour
                    file_path.unlink()
                    logger.info(f"Cleaned up old temporary file: {file_path.name}")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

def download_progress_hook(d):
    """Progress hook for yt-dlp"""
    global current_download_id
    
    if not current_download_id:
        return
    
    with downloads_lock:
        if current_download_id not in downloads_status:
            return
            
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            
            if total > 0:
                progress = (downloaded / total) * 100
                downloads_status[current_download_id]['progress'] = progress
                downloads_status[current_download_id]['downloaded_bytes'] = downloaded
                downloads_status[current_download_id]['total_bytes'] = total
                downloads_status[current_download_id]['speed'] = d.get('speed', 0)
                
        elif d['status'] == 'finished':
            downloads_status[current_download_id]['status'] = 'completed'
            downloads_status[current_download_id]['progress'] = 100
            # Store just the filename, not the full path
            downloads_status[current_download_id]['filename'] = Path(d['filename']).name

def download_video(url, download_id, quality):
    """Download video using yt-dlp with improved Facebook support"""
    try:
        # Initialize download status first
        with downloads_lock:
            downloads_status[download_id] = {
                'status': 'starting',
                'progress': 0,
                'error': None,
                'filename': None,
                'title': 'Loading...',
                'downloaded_bytes': 0,
                'total_bytes': 0,
                'speed': 0,
                'duration': 0,
                'thumbnail': None,
                'description': None,
                'view_count': None
            }
        
        # Convert to mobile URL for better compatibility
        mobile_url = convert_to_mobile_url(url)
        logger.info(f"Original URL: {url}")
        logger.info(f"Mobile URL: {mobile_url}")
        
        # Extract video info first using fallback method
        info_data = extract_video_info_fallback(url)
        with downloads_lock:
            downloads_status[download_id]['title'] = info_data['title']
            downloads_status[download_id]['duration'] = info_data['duration']
            downloads_status[download_id]['thumbnail'] = info_data.get('thumbnail')
            downloads_status[download_id]['description'] = info_data.get('description')
            downloads_status[download_id]['view_count'] = info_data.get('view_count')
            downloads_status[download_id]['status'] = 'downloading'
        
        # Set quality format - improved for Facebook compatibility
        if quality == 'best':
            format_selector = 'best[ext=mp4]/best'
        elif quality == 'worst':
            format_selector = 'worst[ext=mp4]/worst'
        else:
            # For specific quality, try different approaches
            format_selector = f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best[ext=mp4]/best'

        # Updated yt-dlp options for 2024+ version
        ydl_opts = {
            'outtmpl': str(TEMP_DIR / f'{download_id}_%(title)s.%(ext)s'),
            'format': format_selector,
            'progress_hooks': [download_progress_hook],
            'no_warnings': False,
            'ignoreerrors': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'extractor_args': {
                'facebook': {
                    'tab_name': 'videos'
                }
            }
        }



        # Set the download ID for the progress hook
        global current_download_id
        current_download_id = download_id

        # Try multiple strategies for downloading with latest yt-dlp
        strategies = [
            # Strategy 1: Mobile URL with updated options (often works best)
            (mobile_url, ydl_opts),
            # Strategy 2: Original URL with updated options
            (url, ydl_opts),
            # Strategy 3: Mobile URL with minimal options
            (mobile_url, {
                'outtmpl': str(TEMP_DIR / f'{download_id}_%(title)s.%(ext)s'),
                'format': 'best',
                'progress_hooks': [download_progress_hook],
                'no_warnings': True,
                'ignoreerrors': False,
            }),
            # Strategy 4: Generic extractor as last resort
            (url, {
                'outtmpl': str(TEMP_DIR / f'{download_id}_%(title)s.%(ext)s'),
                'format': 'best',
                'progress_hooks': [download_progress_hook],
                'force_generic_extractor': True,
                'no_warnings': True,
            })
        ]
        
        # Remove duplicate strategies
        seen_urls = set()
        filtered_strategies = []
        for url_str, opts in strategies:
            if url_str not in seen_urls:
                seen_urls.add(url_str)
                filtered_strategies.append((url_str, opts))
        
        success = False
        last_error = None
        
        for i, (attempt_url, opts) in enumerate(filtered_strategies):
            if success:
                break
                
            logger.info(f"Strategy {i+1}: Attempting download with URL: {attempt_url}")
            
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    # Try to download directly
                    ydl.download([attempt_url])
                    success = True
                    logger.info(f"Strategy {i+1} succeeded!")
                    break
                        
            except Exception as strategy_error:
                last_error = strategy_error
                logger.error(f"Strategy {i+1} failed: {str(strategy_error)}")
                continue
        
        if not success:
            # Enhanced error message based on the type of error
            error_msg = str(last_error)
            if "No video formats found" in error_msg or "Cannot parse data" in error_msg:
                raise Exception("This Facebook video cannot be downloaded. It may be private, age-restricted, or require login. Try a different public video.")
            else:
                raise Exception(f"All download strategies failed. Facebook may have updated their security measures.")

    except Exception as e:
        logger.error(f"Download error for {download_id}: {str(e)}")
        with downloads_lock:
            # Ensure the download status exists before trying to update it
            if download_id not in downloads_status:
                downloads_status[download_id] = {
                    'status': 'error',
                    'progress': 0,
                    'error': None,
                    'filename': None,
                    'title': 'Failed to load',
                    'downloaded_bytes': 0,
                    'total_bytes': 0,
                    'speed': 0,
                    'duration': 0
                }
            
            downloads_status[download_id]['status'] = 'error'
            # Provide user-friendly error messages
            error_msg = str(e)
            if "Cannot parse data" in error_msg:
                error_msg = "Facebook has changed their format. This video might be private or require login. Try a different video or check if the URL is publicly accessible."
            elif "Video unavailable" in error_msg:
                error_msg = "This video is not available for download. It might be private, deleted, or region-restricted."
            elif "Requested format is not available" in error_msg:
                error_msg = "The requested quality is not available for this video. Try selecting 'Best Quality' instead."
            elif "No video formats found" in error_msg:
                error_msg = "No downloadable video found at this URL. Make sure it's a direct link to a Facebook video."
            elif "400 Client Error" in error_msg:
                error_msg = "Facebook blocked access to this video. Try a different public video or check if the URL is correct."
            elif "Cannot parse data" in error_msg:
                error_msg = "Facebook has enhanced their security measures and is blocking this download. This affects most videos from 2024-2025. The video information was extracted successfully, but the actual download is blocked by Facebook's protection systems."
            else:
                error_msg = f"Download failed: {error_msg}"
            
            downloads_status[download_id]['error'] = error_msg

@app.route('/')
def index():
    """Main page"""
    cleanup_old_files()
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def start_download():
    """Start video download"""
    url = request.form.get('url', '').strip()
    quality = request.form.get('quality', 'best')
    
    if not url:
        flash('Please provide a Facebook video URL', 'error')
        return redirect(url_for('index'))
    
    if not is_valid_facebook_url(url):
        flash('Please provide a valid Facebook video URL', 'error')
        return redirect(url_for('index'))
    
    # Generate unique download ID
    download_id = str(uuid.uuid4())
    
    # Start download in background thread
    thread = threading.Thread(
        target=download_video,
        args=(url, download_id, quality)
    )
    thread.daemon = True
    thread.start()
    
    flash(f'Download started! Your download ID is: {download_id}', 'success')
    return render_template('index.html', download_id=download_id)

@app.route('/status/<download_id>')
def download_status(download_id):
    """Get download status"""
    with downloads_lock:
        status = downloads_status.get(download_id, {'status': 'not_found'})
    
    return jsonify(status)

@app.route('/download_file/<download_id>')
def download_file(download_id):
    """Download completed file directly to user's Downloads folder"""
    with downloads_lock:
        status = downloads_status.get(download_id)
    
    if not status or status.get('status') != 'completed':
        flash('File not ready or not found', 'error')
        return redirect(url_for('index'))
    
    filename = status.get('filename')
    if not filename:
        flash('File not found', 'error')
        return redirect(url_for('index'))
    
    # Construct full file path using TEMP_DIR
    file_path = TEMP_DIR / filename
    if not file_path.exists():
        flash('File not found', 'error')
        return redirect(url_for('index'))
    
    # Get clean filename without download ID prefix
    clean_filename = filename
    if '_' in filename:
        parts = filename.split('_')
        if len(parts) > 1:
            clean_filename = '_'.join(parts[1:])
    
    # Schedule cleanup after download
    def schedule_cleanup():
        def cleanup_file():
            import time
            time.sleep(60)  # Wait 1 minute after download
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up file: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_file)
        cleanup_thread.daemon = True
        cleanup_thread.start()
    
    schedule_cleanup()
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=clean_filename,
        mimetype='video/mp4'
    )

@app.route('/cleanup')
def manual_cleanup():
    """Manual cleanup endpoint"""
    cleanup_old_files()
    flash('Cleanup completed', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
