from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
from langdetect import detect  # Importing language detection library
from fastapi.responses import StreamingResponse
import io

load_dotenv()

# Initialize API key for Google Gemini Pro
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

# Default prompt for Google Gemini Pro
base_prompt = """
You are an expert summarizer for YouTube videos. Your task is to create a clear and insightful summary based on the transcript. Include:

1. **Key Points**: Main ideas discussed.
2. **Conclusions**: Important takeaways or recommendations.
3. **Insights**: Notable facts, figures, or unique ideas shared.

Here is the transcript to summarize:
"""

# Define input structure for the request
class VideoRequest(BaseModel):
    youtube_video_url: str

def extract_transcript(youtube_video_url):
    try:
        # Extract video ID from various YouTube URL formats
        if "youtu.be" in youtube_video_url:
            video_id = youtube_video_url.split("/")[-1]
        elif "v=" in youtube_video_url:
            video_id = youtube_video_url.split("v=")[1].split("&")[0]
        else:
            raise HTTPException(status_code=400, detail="Invalid YouTube link. Please enter a valid link.")

        # Try to retrieve the English transcript first
        try:
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        except NoTranscriptFound:
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi'])

        transcript = " ".join([item["text"] for item in transcript_data])
        return transcript  # Only return the transcript text, not a tuple
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching transcript: {str(e)}. Please check the video URL or try another video.")

def generate_summarys(transcript_text, prompt):
    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt + transcript_text)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating summary: {str(e)}")  # Log the error for debugging
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

# Function to stream the summary response
def stream_summary(summary: str):
    # Create an in-memory byte stream
    summary_stream = io.StringIO(summary)
    return StreamingResponse(summary_stream, media_type="text/plain")

@app.post("/generate_summary/")
async def generate_summary(request: VideoRequest):
    youtube_video_url = request.youtube_video_url

    # Extract the transcript text
    transcript_text = extract_transcript(youtube_video_url)  # This will now just return the text

    if not transcript_text:
        raise HTTPException(status_code=404, detail="Transcript not found")

    summary_length = 400
    summary_format = "Paragraph"
    # Configure prompt based on settings
    prompt = base_prompt
    if summary_format == "Bullet Points":
        prompt += f" Summarize in bullet points, keeping within {summary_length} words."
    elif summary_format == "Paragraph":
        prompt += f" Provide a single coherent paragraph, strictly avoiding bullet points and within {summary_length} words."

    # Generate summary using Google Gemini Pro
    summary = generate_summarys(transcript_text, prompt)  # Pass only transcript text

    # Return the summary as a stream
    return stream_summary(summary)
