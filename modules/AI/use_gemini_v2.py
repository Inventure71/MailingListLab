import logging
import os
import re
import json
import time
from time import sleep
from datetime import datetime
from collections import deque
from enum import Enum
from typing import List, Tuple, Optional, Dict

from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError


class GeminiHandler:
    """Unified handler that merges the capabilities of two earlier prototypes.

    Key features retained from **version 1**:
    - Category‑aware news parsing (`retrieve_news_gemini`, `divide_news_gemini`).
    - Prompt chunking with a flexible token/length guard (`divide_into_blocks`).
    - Fine‑grained deque‑based rate‑limiting.

    Enhancements adopted from **version 2**:
    - Robust API‑key discovery (env var → .env → credentials file).
    - Higher default throughput (configurable `rate_limit` and `time_window`).
    - Exponential‑back‑off retry logic for 429/503 errors.
    - Chat‑style history management (`generate`).
    """

    # ---------------------------------------------------------------------
    # ▶ INITIALISATION -----------------------------------------------------
    # ---------------------------------------------------------------------

    def __init__(
        self,
        *,
        model: str = "gemini-2.0-flash-exp",
        rate_limit: int = 30,
        time_window: int = 60,
        max_retries: int = 5,
        initial_retry_delay: int = 5,
        max_retry_delay: int = 60,
    ) -> None:
        # API key discovery -------------------------------------------------
        self._api_key: str = self._discover_api_key()
        self.client = genai.Client(api_key=self._api_key)

        # Model / config ----------------------------------------------------
        self.model = model
        self.config: Optional[types.GenerateContentConfig] = None

        # Category setup ----------------------------------------------------
        with open("configs/mail_configs.json", "r", encoding="utf‑8") as f:
            category_colors = json.load(f)["category_colors"]
        self.NewsCategory = Enum(
            "NewsCategory", {name.upper(): name for name in category_colors.keys()}
        )

        # Rate limiting -----------------------------------------------------
        self.requests_timestamps: deque[float] = deque(maxlen=rate_limit)
        self.rate_limit = rate_limit
        self.time_window = time_window

        # Retry parameters --------------------------------------------------
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay

    # ------------------------------------------------------------------
    # ▶ PRIVATE HELPERS ------------------------------------------------
    # ------------------------------------------------------------------

    @staticmethod
    def _discover_api_key() -> str:
        """Locate a Gemini API key via env‑var, .env file or JSON creds."""
        if (key := os.environ.get("GEMINI_API_KEY")):
            return key

        # .env fallback --------------------------------------------------
        try:
            with open(".env", "r", encoding="utf‑8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY"):
                        return line.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass

        # credentials/key.json fallback ----------------------------------
        try:
            with open("credentials/key.json", "r", encoding="utf‑8") as f:
                return json.load(f)["key"]
        except FileNotFoundError:
            raise RuntimeError(
                "Gemini API key not found – set GEMINI_API_KEY or supply .env/credentials/key.json"
            )

    # ------------------------------------------------------------------
    # ▶ RATE‑LIMITING ---------------------------------------------------
    # ------------------------------------------------------------------

    def _check_rate_limit(self) -> None:
        """Block until a new request is allowed under the moving window."""
        now = time.time()

        # Drop timestamps older than the window -------------------------
        while self.requests_timestamps and now - self.requests_timestamps[0] >= self.time_window:
            self.requests_timestamps.popleft()

        # If window full, wait until head expires ----------------------
        if len(self.requests_timestamps) >= self.rate_limit:
            wait_for = self.time_window - (now - self.requests_timestamps[0])
            if wait_for > 0:
                print(f"⏳  Rate‑limit hit – sleeping {wait_for:.1f}s …")
                sleep(wait_for)
            # Clean up after wait
            while self.requests_timestamps and time.time() - self.requests_timestamps[0] >= self.time_window:
                self.requests_timestamps.popleft()

        # Record this request ------------------------------------------
        self.requests_timestamps.append(time.time())

    # ------------------------------------------------------------------
    # ▶ LOW‑LEVEL REQUEST WRAPPER --------------------------------------
    # ------------------------------------------------------------------

    def _generate(self, *, contents: List[types.Content], config: types.GenerateContentConfig) -> types.GenerateContentResponse:
        """Unified calling layer: rate‑limit + retries + error handling."""
        delay = self.initial_retry_delay
        for attempt in range(self.max_retries + 1):
            self._check_rate_limit()
            try:
                return self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            except (ServerError, ClientError) as e:
                msg = str(e)
                overloaded = "503" in msg and "overloaded" in msg.lower()
                quota = "429" in msg and "quota" in msg.lower()
                if not (overloaded or quota) or attempt == self.max_retries:
                    # Non‑retryable or exhausted attempts
                    raise

                # Back‑off ------------------------------------------------
                suggested = None
                if quota and (m := re.search(r"retryDelay\": \"(\d+)s\"", msg)):
                    suggested = int(m.group(1))
                wait = suggested or delay
                print(
                    f"⚠️  {'Overloaded' if overloaded else 'Quota'} – retry {attempt + 1}/{self.max_retries} in {wait}s …"
                )
                sleep(wait)
                if not suggested:
                    delay = min(delay * 1.5, self.max_retry_delay)
        # Should never be reached
        raise RuntimeError("Unexpected fall‑through in retry loop")

    # ------------------------------------------------------------------
    # ▶ PUBLIC UTILITIES -----------------------------------------------
    # ------------------------------------------------------------------

    @staticmethod
    def divide_into_blocks(text: str, max_block_size: int = 2_000_000) -> List[str]:
        """Return a list of <= `max_block_size` chunks, splitting at sentence ends when possible."""
        if len(text) <= max_block_size:
            return [text]
        blocks: List[str] = []
        start = 0
        while start < len(text):
            end = min(start + max_block_size, len(text))
            if end < len(text):
                # Prefer split on last period
                last_dot = text[start:end].rfind(".")
                if last_dot != -1:
                    end = start + last_dot + 1
            blocks.append(text[start:end])
            start = end
        return blocks

    # ------------------------------------------------------------------
    # ▶ GENERIC ASK (non‑chat) -----------------------------------------
    # ------------------------------------------------------------------
    def generic_ask_gemini(self, prompt: str, *, temperature: float = 1.0) -> List[str]:
        """Ask Gemini, chunking long prompts and returning each block's response."""
        blocks = self.divide_into_blocks(prompt)
        out: List[str] = []
        for block in blocks:
            cfg = types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="text/plain",
            )
            content_obj = [types.Content(role="user", parts=[types.Part.from_text(text=block)])]
            response = self._generate(contents=content_obj, config=cfg)
            out.append(response.text)
        return out

    # ------------------------------------------------------------------
    # ▶ CHAT‑STYLE GENERATE --------------------------------------------
    # ------------------------------------------------------------------
    def convert_to_gemini(self, history: List[Tuple[str, str]]) -> List[types.Content]:
        contents: List[types.Content] = []
        for role, text in history:
            contents.append(
                types.Content(role="user" if role == "user" else "model", parts=[types.Part.from_text(text=text)])
            )
        return contents

    def generate(
        self,
        prompt: str,
        history: List[Tuple[str, str]],
        *,
        system_instruction: str = "",
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """Chat‑style generation with history and system instruction support."""
        contents = self.convert_to_gemini(history)
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))

        cfg = types.GenerateContentConfig(
            response_mime_type="text/plain",
            system_instruction=[types.Part.from_text(text=system_instruction)] if system_instruction else None,
        )
        response = self._generate(contents=contents, config=cfg)
        history.extend([("user", prompt), ("model", response.text)])
        return response.text, history

    # ------------------------------------------------------------------
    # ▶ NEWS‑SPECIFIC ENDPOINTS ----------------------------------------
    # ------------------------------------------------------------------

    def _news_call(self, prompt: str, *, schema: types.Schema, system_instruction: str) -> str:
        cfg = types.GenerateContentConfig(
            temperature=1.0,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_schema=schema,
            response_mime_type="application/json",
            system_instruction=system_instruction,
        )
        content_obj = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        response = self._generate(contents=content_obj, config=cfg)
        return response.text

    def evaluate_articles_gemini(self, prompt: str) -> str:
        """Filter raw text into future‑relevant tech news items (JSON)."""

        json_schema = types.Schema(
            type="OBJECT",
            required=["news"],
            properties={
                "news": types.Schema(
                    type="ARRAY",
                    items=types.Schema(
                        type="OBJECT",
                        required=["source", "brief description", "relevancy"],
                        properties={
                            "ID": types.Schema(type="STRING"),
                            "source": types.Schema(type="STRING"),
                            "brief description": types.Schema(type="STRING"),
                            "reasoning": types.Schema(type="STRING"),
                            "relevancy": types.Schema(type="INTEGER"),
                        },
                    ),
                )
            },
        ) 

        today_date = datetime.now().strftime("%Y/%m/%d") 
        
        system_instruction = (
            "You are in charge of creating a newsletter for a university."
            "You are a helpful assistant that evaluates the quality of the articles and the level of relvancy to the user. "
            "You are given a list of articles and their related sources content. "
            "Your task is to evaluate the relevancy of the articles for the user."
            "IMPORTANT: For each article, use the exact ARTICLE_ID provided in the input text (e.g., ARTICLE_0, ARTICLE_1, etc.) as the ID field in your response."
            "Only include news that match these themes: Cyber\n‑Physical Systems\n-Digital\n‑Physical Integration\nRobotics\nHuman\n‑Computer Interaction\nArtificial Intelligence\nAutomation\nDecentralized Technologies\nEthics in Technology\nInterdisciplinary Research\nInnovation and Design.\n\n"
            f"‑Today is {today_date} – include only events that have not happened yet.\n"
            "‑Target audience: undergraduate & graduate students.\n"
            #"‑ Job opportunities ➜ exclude.\n"
            "‑Score relevancy 0‑100; if similar news appear drastically decrease the scores of the copies.\n"
        )
        return self._news_call(prompt, schema=json_schema, system_instruction=system_instruction)

    def divide_news_gemini(self, prompt: str) -> str:
        """Transform news JSON into categorised/colour‑coded digest."""
        json_schema = types.Schema(
            type="OBJECT",
            required=["news"],
            properties={
                "news": types.Schema(
                    type="ARRAY",
                    items=types.Schema(
                        type="OBJECT",
                        required=["description", "title", "source", "location", "summary", "category", "link"],
                        properties={
                            "description": types.Schema(type="STRING"),
                            "title": types.Schema(type="STRING"),
                            "source": types.Schema(type="STRING"),
                            "location": types.Schema(type="STRING"),
                            "contact": types.Schema(type="STRING"),
                            "summary": types.Schema(type="STRING"),
                            "category": types.Schema(
                                type="STRING",
                                enum=[cat.value for cat in self.NewsCategory],
                            ),
                            "link": types.Schema(type="STRING"),
                        },
                    ),
                )
            },
        )
        system_instruction = (
            """
            You are in charge of creating a newsletter for a university.
            You are given a list of articles and all the related information for each.
            You write using simple terms but still in a professional way.
            Your task is to process each article and identify the components:
            - Title: A simple concise title that you would give to the article.
            - Source: The source of the article.
            - Location: The location of the article. 
            -- Use 'Online' for unspecified locations
            - Contact: The contact of the article.
            -- If not provided don't include in response
            - Description: A medium-detailed description of the article.
            - Summary: Bite‑sized headline that makes you understand the general idea and vibes of the article.
            - Category: The category of the article.
            -- News: General announcements, updates, or developments related to technology, academia, or research that do not involve a specific scheduled event or speaker.
            --- Examples: New research lab opens, a major award granted, a report released, a partnership announced.
            -- Talks: One-off academic or expert-led lectures, panels, seminars, or public keynotes.
            --- Must include a speaker and a scheduled time.
            --- Examples: Guest lecture on AI Ethics, Seminar by Prof. Smith on robotics.
            -- Events: Multiday or large-scale organized gatherings such as conferences, symposiums, fairs, or networking meetups.
            --- Often involve multiple speakers or sessions.
            --- Examples: ACM Conference on HCI, International Robotics Expo.
            -- Workshops: Hands-on, skill-focused training sessions or short courses, typically with limited participation.
            --- Aimed at learning-by-doing.
            --- Examples: Python for Data Analysis bootcamp, AR prototyping workshop.
            -- Opportunity: Jobs, internships, fellowships, grants, calls for papers, or student competitions.
            --- The item offers a chance to apply or participate in something external.
            --- Examples: Research internship at MIT, Google Summer of Code.
            -- Other: For articles that don’t clearly fit any of the categories above.
            --- Use only if none of the others apply.
            --- Examples: Miscellaneous blog posts, ambiguous updates without context or timing.
            - Link: most relevant link to the article, the one that once clicked enables the users to read the article.
            -- Include only a single authoritative link per item.
            """
        )
        return self._news_call(prompt, schema=json_schema, system_instruction=system_instruction)

    def evaluate_images_gemini(self, prompt: str, images: List[Dict[str, str]],) -> str:
        """
        Evaluate the images (each with its context) and return up to one
        relevant image per article, along with that image’s context.
        """
        # Expect response to be an object with an array of { image: string, context: string }
        json_schema = types.Schema(
            type="OBJECT",
            required=["images"],
            properties={
                "images": types.Schema(
                    type="ARRAY",
                    items=types.Schema(
                        type="OBJECT",
                        required=["image_path", "short_justification"],
                        properties={
                            "image_path": types.Schema(type="STRING"),
                            "short_justification": types.Schema(type="STRING"),
                        },
                    ),
                ),
            },
        )

        logging.info(f"Uploading {len(images)} images with contexts")
        uploaded_files = []
        contexts = []
        for item in images:
            path = item["image_path"]
            ctx  = item["article_id"]
            # upload the image
            uploaded = self.client.files.upload(file=path, purpose="ARTICLE_IMAGE")
            uploaded_files.append(uploaded)
            contexts.append(ctx)
        logging.info(f"Uploaded {len(uploaded_files)} images")

        # Enhance the system instruction to remind the model that each image has context
        system_instruction = (
            "You are in charge of creating a newsletter for a university.\n"
            "You are given a list of images, each paired with a short context description.\n"
            "Your task is to select at most one image per article—and for each selected image,\n"
            "return both the image identifier and its context.\n"
            "- Only include images that are relevant to the article.\n"
            "- Only include images that enrich the article.\n"
            "- You don't have to include an image for every article.\n"
            "- If you want to include an image provide the image path and a short justification for why you chose it. If no image is relevant, return an empty array.\n"
            "\n"
            "Here are the image contexts (in the same order as the uploads):\n"
            + "\n".join(f"{i+1}. {ctx}" for i, ctx in enumerate(contexts))
        )

        # Call into your wrapper; pass both the file handles and their contexts
        response = self._news_call(
            prompt=prompt,
            schema=json_schema,
            system_instruction=system_instruction,
            uploaded_files=uploaded_files,
            file_contexts=contexts,
        )

        logging.info(f"Deleting {len(uploaded_files)} images")
        for f in uploaded_files:
            self.client.files.delete(file_id=f.id)
        logging.info("All uploaded images deleted")

        return response

# ---------------------------------------------------------------------
# ▶ STAND‑ALONE TEST ---------------------------------------------------
# ---------------------------------------------------------------------
if __name__ == "__main__":
    gh = GeminiHandler()
    hist: List[Tuple[str, str]] = []
    while True:
        try:
            user_prompt = input("› ")
        except (EOFError, KeyboardInterrupt):
            break
        reply, hist = gh.generate(user_prompt, hist)
        print(reply)
