# yt_dlp_gemini_tagger.py

import os
import requests
from typing import Optional

from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, TIT2, TPE1, TALB, TCON, TDRC, COMM, APIC, TXXX, error,
    TRCK, TPOS, USLT, TPUB, TBPM, TKEY, TSRC, TSSE, TDOR, TCOP,
    WXXX, POPM, TIT3, TPE2, TCOM
)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from yt_dlp.postprocessor.common import PostProcessor

# --- Load API key ---
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")

# --- Define structured metadata model ---
class MP3Tags(BaseModel):
    """
    Data model representing standard and extended ID3 tags for an audio file.
    All fields are Optional and provide sensible defaults or detailed descriptions.
    """
    # Core
    title: str = Field(..., description="Cleaned title of the song/audio track. Mandatory field.")
    artist: Optional[str] = Field("Unknown", description="Name of the singer, artist, band, or channel.")
    album: Optional[str] = Field("Unknown", description="Name of the album, series, or movie the track belongs to.")
    track: Optional[str] = Field(None, description="Track number and total tracks (e.g., '5/12').")
    disc: Optional[str] = Field(None, description="Disc number and total discs (e.g., '1/2').")
    year: Optional[str] = Field("Unknown", description="Publishing year of the song/audio track (YYYY).")
    genre: Optional[str] = Field("Unknown", description="Genre of the song (e.g., 'Rock', 'Classical', 'Podcast').")
    composer: Optional[str] = Field("Unknown", description="Composer of the song or musical work.")
    publisher: Optional[str] = Field("Unknown", description="Publisher or record label of the song.")
    lyrics: Optional[str] = Field("Unknown", description="Full lyrics of the song.")
    comments: Optional[str] = Field("Unknown", description="General comments, notes, or description.")

    # Extended
    album_artist: Optional[str] = Field("Unknown", description="The primary artist for the entire album.")
    bpm: Optional[str] = Field("Unknown", description="Beats per minute.")
    key: Optional[str] = Field(None, description="Musical key of the song (e.g., 'C minor' or 'F# Maj').")
    isrc: Optional[str] = Field(None, description="International Standard Recording Code (a unique identifier for recordings).")
    encoder: Optional[str] = Field(None, description="Software or hardware used to encode the file (e.g., 'LAME 3.99').")
    original_date: Optional[str] = Field(None, description="Original release date, if different from the year field (e.g., '1970-01-01').")
    copyright: Optional[str] = Field(None, description="Copyright statement or legal notice.")
    website: Optional[str] = Field(None, description="Official website URL related to the song or artist.")
    rating: Optional[str] = Field(None, description="User or editorial rating, typically a numerical value (e.g., '5' out of 5).")
    subtitle: Optional[str] = Field(None, description="Secondary title, often used in podcasts or classical music.")
    cover_url: Optional[str] = Field(None, description="URL pointing to the album artwork or cover image.")


# --- Gemini setup ---
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.1,
    # max_output_tokens=1024,
    google_api_key=google_api_key
)
parser = PydanticOutputParser(pydantic_object=MP3Tags)

prompt = PromptTemplate(
    template="""
Given the following MP3 filename, extract structured metadata tags suitable for a music song/audio story.
The filename may contain extra information like channel name, album name, upload date or extraneous symbols.
Focus on extracting clean and relevant tags only. 

Filename: {filename}

{format_instructions}
""",
    input_variables=["filename"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)


chain = prompt | model | parser


# --- Helper function to tag MP3 ---
def tag_mp3(file_path: str, tags: MP3Tags):
    audio = MP3(file_path, ID3=ID3)
    try:
        audio.add_tags()
    except error:
        pass

    def set_tag(key, frame):
        if key in audio.tags:
            del audio.tags[key]
        audio.tags.add(frame)

    # Only set if meaningful (not None/Unknown/empty)
    def valid(val: Optional[str]):
        return val and val.strip() and val.strip().lower() != "unknown"
    
    # Core
    if valid(tags.title): set_tag("TIT2", TIT2(encoding=3, text=tags.title))
    if valid(tags.artist): set_tag("TPE1", TPE1(encoding=3, text=tags.artist))
    if valid(tags.album): set_tag("TALB", TALB(encoding=3, text=tags.album))
    if valid(tags.track): set_tag("TRCK", TRCK(encoding=3, text=tags.track))
    if valid(tags.disc): set_tag("TPOS", TPOS(encoding=3, text=tags.disc))
    if valid(tags.year): set_tag("TDRC", TDRC(encoding=3, text=tags.year))
    if valid(tags.genre): set_tag("TCON", TCON(encoding=3, text=tags.genre))
    if valid(tags.composer): set_tag("TCOM", TCOM(encoding=3, text=tags.composer))
    if valid(tags.publisher): set_tag("TPUB", TPUB(encoding=3, text=tags.publisher))
    if valid(tags.lyrics): set_tag("USLT", USLT(encoding=3, lang="eng", desc="", text=tags.lyrics))
    if valid(tags.comments): set_tag("COMM", COMM(encoding=3, desc="desc", text=tags.comments))

    # Extended
    if valid(tags.album_artist): set_tag("TPE2", TPE2(encoding=3, text=tags.album_artist))
    if valid(tags.bpm): set_tag("TBPM", TBPM(encoding=3, text=tags.bpm))
    if valid(tags.key): set_tag("TKEY", TKEY(encoding=3, text=tags.key))
    if valid(tags.isrc): set_tag("TSRC", TSRC(encoding=3, text=tags.isrc))
    if valid(tags.encoder): set_tag("TSSE", TSSE(encoding=3, text=tags.encoder))
    if valid(tags.original_date): set_tag("TDOR", TDOR(encoding=3, text=tags.original_date))
    if valid(tags.copyright): set_tag("TCOP", TCOP(encoding=3, text=tags.copyright))
    if valid(tags.website): set_tag("WXXX", WXXX(encoding=3, desc="Website", url=tags.website))
    if valid(tags.rating):
        try:
            rating_val = int(tags.rating)
            set_tag("POPM", POPM(email="user@example.com", rating=rating_val, count=0))
        except ValueError:
            pass
    if valid(tags.subtitle): set_tag("TIT3", TIT3(encoding=3, text=tags.subtitle))

    # Cover Art
    if valid(tags.cover_url):
        try:
            resp = requests.get(tags.cover_url, timeout=10)
            resp.raise_for_status()
            img_data = resp.content
            set_tag("APIC", APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=img_data,
            ))
        except Exception as e:
            print(f"[WARN] Failed to add cover art: {e}")

    audio.save()


# --- yt-dlp postprocessor class ---
class GeminiID3PostProcessor(PostProcessor):
    """Custom yt-dlp postprocessor to retag MP3 using Gemini API."""

    def run(self, info):
        file_path = info.get("filepath") or info.get("requested_downloads")[0]["filepath"]

        if not file_path.lower().endswith(".mp3"):
            return [], info  # Only process MP3s

        filename = os.path.basename(file_path)
        uploader = info.get("uploader") or info.get("channel")
        thumbnail = info.get("thumbnail")

        try:
            tags = chain.invoke({"filename": filename})
            # Fallbacks for mandatory fields
            if not tags.title:
                tags.title = os.path.splitext(filename)[0]
            if not tags.artist and uploader:
                tags.artist = uploader
            if not tags.cover_url and thumbnail:
                tags.cover_url = thumbnail

            tag_mp3(file_path, tags)
            self.to_screen(f"[GeminiID3] Tagged: {os.path.basename(file_path)}")

        except Exception as e:
            # Minimal fallback
            fallback_title = os.path.splitext(filename)[0]
            fallback_tags = MP3Tags(title=fallback_title, artist=uploader, cover_url=thumbnail)
            tag_mp3(file_path, fallback_tags)
            self.to_screen(f"[GeminiID3] Fallback tagging applied: {e}")

        return [], info
