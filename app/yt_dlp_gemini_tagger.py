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
from pydantic import BaseModel
from dotenv import load_dotenv

from yt_dlp.postprocessor.common import PostProcessor

# --- Load API key ---
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")

# --- Define structured metadata model ---
class MP3Tags(BaseModel):
    # Core
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    track: Optional[str] = None   # e.g. "5/12"
    disc: Optional[str] = None    # e.g. "1/2"
    year: Optional[str] = None
    genre: Optional[str] = None
    composer: Optional[str] = None
    publisher: Optional[str] = None
    lyrics: Optional[str] = None
    comments: Optional[str] = None

    # Extended
    album_artist: Optional[str] = None
    bpm: Optional[str] = None
    key: Optional[str] = None
    isrc: Optional[str] = None
    encoder: Optional[str] = None
    original_date: Optional[str] = None
    copyright: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[str] = None
    subtitle: Optional[str] = None  # podcast / show
    cover_url: Optional[str] = None


# --- Gemini setup ---
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    temperature=0.5,
    max_output_tokens=1024,
    google_api_key=google_api_key,
)
parser = PydanticOutputParser(pydantic_object=MP3Tags)

prompt = PromptTemplate(
    template="""
Given the raw MP3 metadata, return a cleaned JSON.
- All fields must exist.
- If unknown, use "" (empty string) instead of null.
- "title" must never be empty; if unavailable, use the filename without extension.

Raw metadata:
{metadata}

{format_instructions}
""",
    input_variables=["metadata"],
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

    # Core
    if tags.title: set_tag("TIT2", TIT2(encoding=3, text=tags.title))
    if tags.artist: set_tag("TPE1", TPE1(encoding=3, text=tags.artist))
    if tags.album: set_tag("TALB", TALB(encoding=3, text=tags.album))
    if tags.track: set_tag("TRCK", TRCK(encoding=3, text=tags.track))
    if tags.disc: set_tag("TPOS", TPOS(encoding=3, text=tags.disc))
    if tags.year: set_tag("TDRC", TDRC(encoding=3, text=tags.year))
    if tags.genre: set_tag("TCON", TCON(encoding=3, text=tags.genre))
    if tags.composer: set_tag("TCOM", TCOM(encoding=3, text=tags.composer))
    if tags.publisher: set_tag("TPUB", TPUB(encoding=3, text=tags.publisher))
    if tags.lyrics: set_tag("USLT", USLT(encoding=3, lang="eng", desc="", text=tags.lyrics))
    if tags.comments: set_tag("COMM", COMM(encoding=3, desc="desc", text=tags.comments))

    # Extended
    if tags.album_artist: set_tag("TPE2", TPE2(encoding=3, text=tags.album_artist))
    if tags.bpm: set_tag("TBPM", TBPM(encoding=3, text=tags.bpm))
    if tags.key: set_tag("TKEY", TKEY(encoding=3, text=tags.key))
    if tags.isrc: set_tag("TSRC", TSRC(encoding=3, text=tags.isrc))
    if tags.encoder: set_tag("TSSE", TSSE(encoding=3, text=tags.encoder))
    if tags.original_date: set_tag("TDOR", TDOR(encoding=3, text=tags.original_date))
    if tags.copyright: set_tag("TCOP", TCOP(encoding=3, text=tags.copyright))
    if tags.website: set_tag("WXXX", WXXX(encoding=3, desc="Website", url=tags.website))
    if tags.rating:
        try:
            rating_val = int(tags.rating)
            set_tag("POPM", POPM(email="user@example.com", rating=rating_val, count=0))
        except ValueError:
            pass
    if tags.subtitle: set_tag("TIT3", TIT3(encoding=3, text=tags.subtitle))

    # Cover Art
    if tags.cover_url:
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

        raw_metadata = info.get("metadata", {})

        try:
            tags = chain.invoke({"metadata": raw_metadata})
            if not tags.title:
                tags.title = os.path.splitext(os.path.basename(file_path))[0]

            tag_mp3(file_path, tags)
            self.to_screen(f"[GeminiID3] Tagged: {os.path.basename(file_path)}")
        except Exception as e:
            # Fallback to minimal tagging if Gemini fails
            fallback_title = os.path.splitext(os.path.basename(file_path))[0]
            fallback_tags = MP3Tags(title=fallback_title)
            tag_mp3(file_path, fallback_tags)
            self.to_screen(f"[GeminiID3] Fallback tagging applied: {e}")

        return [], info
