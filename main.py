import sys
import os
import json
import logging
import asyncio
import io
import fitz  # PyMuPDF
import openai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_gdrive_service():
    gdrive_creds_json = os.environ.get("GDRIVE_CREDENTIALS")
    if not gdrive_creds_json:
        logging.warning("GDRIVE_CREDENTIALS not found, attempting anonymous download...")
        return None
    try:
        cred_info = json.loads(gdrive_creds_json)
        credentials = service_account.Credentials.from_service_account_info(cred_info)
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        logging.error(f"Error initializing Google Drive API: {e}")
        return None

def download_from_gdrive(service, file_id, output_path):
    if service:
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(output_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            if status:
                logging.info(f"Downloading file {file_id}: {int(status.progress() * 100)}%")
    else:
        # Fallback for public files without auth
        import requests
        url = f"https://drive.google.com/uc?id={file_id}&export=download"
        logging.info(f"Downloading {file_id} via public link...")
        session = requests.Session()
        response = session.get(url, stream=True)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(32768):
                if chunk:
                    f.write(chunk)

def extract_pdf_data(pdf_path, output_img_prefix):
    doc = fitz.open(pdf_path)
    text = ""
    image_paths = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text += page.get_text() + "\n"
        
        # Render image
        pix = page.get_pixmap(dpi=150) # Improve resolution slightly
        img_path = f"{output_img_prefix}_page_{page_num}.png"
        pix.save(img_path)
        image_paths.append(img_path)
        
    return text, image_paths

def generate_seo_and_script(pdf_text, focus_keyword, api_key):
    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://litellm.koboi2026.biz.id/v1"
    )

    prompt = f"""
    Kamu adalah pakar SEO YouTube dan penulis naskah video.
    Berdasarkan teks presentasi PDF berikut, buatkan:
    1. Naskah narasi video yang engaging.
    2. Judul YouTube yang sangat clickbait tapi relevan, mengandung kata kunci "{focus_keyword}".
    3. Deskripsi YouTube yang SEO-friendly (minimal 3 paragraf), mengandung kata kunci secara natural, dan sertakan hashtag.
    4. 15 Tags YouTube yang relevan dipisahkan dengan koma.

    Teks PDF:
    {pdf_text[:3000]} # Batasi teks agar tidak melebihi token limit

    Format output WAJIB dalam JSON seperti ini:
    {{
        "narration": "Halo semuanya, selamat datang...",
        "title": "Judul SEO...",
        "description": "Deskripsi SEO...",
        "tags": "tag1, tag2, tag3"
    }}
    """
    
    logging.info("Requesting LiteLLM/Koboi for script and metadata generation...")
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that strictly outputs JSON."},
            {"role": "user", "content": prompt}
        ],
        response_format={ "type": "json_object" }
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON from LLM: {content}")
        raise e

async def generate_audio(text, output_path):
    communicate = edge_tts.Communicate(text, "id-ID-ArdiNeural") # Indonesian male voice
    await communicate.save(output_path)

def create_video(image_paths, audio_path, output_video_path):
    audio_clip = AudioFileClip(audio_path)
    audio_duration = audio_clip.duration
    
    # Calculate duration per slide evenly
    duration_per_image = audio_duration / len(image_paths) if image_paths else 5.0
    
    clips = []
    for img_path in image_paths:
        clip = ImageClip(img_path).set_duration(duration_per_image)
        clips.append(clip)
        
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio_clip)
    # Write at 24fps to save rendering time
    video.write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac")

def get_youtube_service():
    youtube_creds_json = os.environ.get("YOUTUBE_CLIENT_SECRET")
    if not youtube_creds_json:
        logging.error("YOUTUBE_CLIENT_SECRET not found in environment variables.")
        return None
        
    from google.oauth2.credentials import Credentials
    try:
        cred_info = json.loads(youtube_creds_json)
        # Using User Credentials JSON with refresh token
        credentials = Credentials.from_authorized_user_info(cred_info)
        return build('youtube', 'v3', credentials=credentials)
    except Exception as e:
        try:
            cred_info = json.loads(youtube_creds_json)
            credentials = service_account.Credentials.from_service_account_info(cred_info)
            return build('youtube', 'v3', credentials=credentials)
        except Exception as e2:
            logging.error(f"Failed to initialize YouTube service. OAUTH error: {e}. SA error: {e2}")
            return None

def upload_to_youtube(youtube, video_path, title, description, tags):
    if not youtube:
        logging.error("YouTube service is not available. Skipping upload.")
        return

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': [tag.strip() for tag in tags.split(',')],
            'categoryId': '27' # Education
        },
        'status': {
            'privacyStatus': 'private' # Let user publish it manually when they want, or change to public
        }
    }

    media_body = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')
    
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media_body
    )
    
    response = None
    logging.info("Starting YouTube upload...")
    while response is None:
        status, response = request.next_chunk()
        if status:
            logging.info(f"Uploaded {int(status.progress() * 100)}%")
            
    logging.info(f"Video uploaded! Video ID: {response['id']}")

def main():
    if len(sys.argv) < 3:
        logging.error("Usage: python main.py <json_file_ids> <focus_keyword>")
        sys.exit(1)
        
    file_ids_json = sys.argv[1]
    focus_keyword = sys.argv[2]
    
    koboi_api_key = os.environ.get("KOBOI_API_KEY")
    if not koboi_api_key:
        logging.error("KOBOI_API_KEY is missing!")
        sys.exit(1)

    try:
        file_ids = json.loads(file_ids_json)
    except json.JSONDecodeError:
        logging.error("Failed to parse file IDs JSON string.")
        sys.exit(1)
        
    if not isinstance(file_ids, list):
        file_ids = [file_ids_json]

    gdrive_service = get_gdrive_service()
    youtube_service = get_youtube_service()
    
    for i, file_id in enumerate(file_ids):
        logging.info(f"--- Processing File ID {i+1}/{len(file_ids)}: {file_id} ---")
        
        pdf_path = f"temp_presentation_{i}.pdf"
        img_prefix = f"temp_img_{i}"
        audio_path = f"temp_audio_{i}.mp3"
        video_path = f"final_video_{i}.mp4"
        image_paths = []
        
        try:
            # 1. Download
            logging.info("Downloading PDF...")
            download_from_gdrive(gdrive_service, file_id, pdf_path)
            
            # 2. Extract
            logging.info("Extracting PDF text and images...")
            pdf_text, image_paths = extract_pdf_data(pdf_path, img_prefix)
            
            if not pdf_text.strip():
                logging.warning("No text found in PDF, AI generation might be poor.")
            
            # 3. AI Generation
            logging.info("Generating script and SEO metadata...")
            ai_data = generate_seo_and_script(pdf_text, focus_keyword, koboi_api_key)
            logging.info(f"Generated Title: {ai_data.get('title')}")
            
            # 4. Voice Generation
            logging.info("Generating voice TTS...")
            narr = ai_data.get('narration', 'Halo, dokumen ini tidak memiliki teks yang cukup.')
            asyncio.run(generate_audio(narr, audio_path))
            
            # 5. Video Composition
            logging.info("Composing video...")
            create_video(image_paths, audio_path, video_path)
            
            # 6. YouTube Upload
            logging.info("Uploading to YouTube...")
            upload_to_youtube(
                youtube_service, 
                video_path, 
                ai_data.get('title', f"AI Generated Video {i}"), 
                ai_data.get('description', ''), 
                ai_data.get('tags', '')
            )
            
        except Exception as e:
            logging.error(f"Error processing file {file_id}: {e}", exc_info=True)
        finally:
            # Cleanup optionally
            logging.info("Cleaning up temporary files...")
            for path in [pdf_path, audio_path, video_path] + image_paths:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        logging.warning(f"Could not remove {path}: {e}")
                    
    logging.info("All batch processes completed successfully!")

if __name__ == "__main__":
    main()
