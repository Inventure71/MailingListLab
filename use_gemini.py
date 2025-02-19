import json
import time

from google import genai
from collections import deque
import json
import time

from google import genai
from google.genai import types
from google.genai.types import HttpOptions
from collections import deque

class GeminiHandler:
    def __init__(self):
        # read json file and extract token
        self.key = json.load(open("credentials/key_paid.json"))["key"]
        self.config = None
        #self.model_name = "gemini-2.0-flash"
        self.model_name = "gemini-2.0-flash-exp"
        self.client = genai.Client(api_key=self.key)

        self.requests_timestamps = deque(maxlen=10)  # Store timestamps of last 10 requests
        self.rate_limit = 10  # requests
        self.time_window = 60  # seconds (1 minute)

    def check_rate_limit(self):
        """Check if we can make a new request based on rate limits."""
        current_time = time.time()

        # Remove timestamps older than our time window
        while self.requests_timestamps and current_time - self.requests_timestamps[0] >= self.time_window:
            self.requests_timestamps.popleft()

        # If we have less than rate_limit requests in our window, we can proceed
        if len(self.requests_timestamps) < self.rate_limit:
            self.requests_timestamps.append(current_time)
            return True

        # Calculate wait time if we're at the limit
        if self.requests_timestamps:
            wait_time = self.time_window - (current_time - self.requests_timestamps[0])
            if wait_time > 0:
                time.sleep(wait_time)
                self.requests_timestamps.append(current_time + wait_time)
                return True

        return False

    def generic_ask_gemini(self, prompt):
        if not self.check_rate_limit():
            print("Rate limit exceeded. Please wait before making more requests.")
            time.sleep(5)
            return self.generic_ask_gemini(prompt)

        blocks = self.divide_into_blocks(prompt)
        responses = []
        for block in blocks:
            if self.config is None:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
            else:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=self.config,
                )
            print(response.text)
            responses.append(response.text)

        return responses

    def divide_into_blocks(self, prompt):
        """
        # Use the existing client instance instead of creating a new one
        response = self.client.models.count_tokens(
            model=self.model_name,
            contents=prompt,
        )
        print("Token count response:", response)
        total_tokens = response.total_tokens
        print("Total tokens:", total_tokens)

        # If token count is under a threshold, return the whole prompt as one block.
        if total_tokens <= 500000:
            return [prompt]
        else:
            blocks = []
            start = 0
            block_size = 450000  # Adjust as needed to stay under the limit.
            while start < len(prompt):
                end = start + block_size
                blocks.append(prompt[start:end])
                start = end
            print("Number of blocks:", len(blocks))
            return blocks"""

        # Define maximum block size in characters (approximately 100K chars)
        max_block_size = 2000000

        # If text is small enough, return as single block
        if len(prompt) <= max_block_size:
            return [prompt]

        # Split into blocks
        blocks = []
        start = 0
        while start < len(prompt):
            # Find the last period before max_block_size to maintain sentence integrity
            end = min(start + max_block_size, len(prompt))
            if end < len(prompt):
                # Look for the last period before the max_block_size
                last_period = prompt[start:end].rfind('.')
                if last_period != -1:
                    end = start + last_period + 1

            blocks.append(prompt[start:end])
            start = end

        print("Number of blocks:", len(blocks))
        return blocks

    def retrieve_news_gemini(self, prompt):
        # Load your API key from a JSON credentials file.
        key = json.load(open("credentials/key_paid.json"))["key"]
        client = genai.Client(api_key=key)

        # Define the JSON schema for the news extraction.
        json_schema = types.Schema(
            type="OBJECT",
            enum=[],  # No enum values.
            required=["news"],
            properties={
                "news": types.Schema(
                    type="ARRAY",
                    items=types.Schema(
                        type="OBJECT",
                        enum=[],  # No enum values.
                        required=["source", "brief description", "relevancy"],
                        properties={
                            "source": types.Schema(type="STRING"),
                            "brief description": types.Schema(type="STRING"),
                            "requirements": types.Schema(type="STRING"),
                            "imageVideosLinks": types.Schema(type="STRING"),
                            "linkToAricle": types.Schema(type="STRING"),
                            "linkToMeeting": types.Schema(type="STRING"),
                            "relevancy": types.Schema(type="INTEGER"),
                            "location": types.Schema(type="STRING"),
                            "contact": types.Schema(type="STRING"),
                        },
                    ),
                ),
            },
        )

        # Define the generation configuration.
        generation_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_schema=json_schema,
            response_mime_type="application/json",
            system_instruction=(
                "Your objective is to divide and filter all the different news in the given text. "
                "You should only include the news that follow the following mindset:\n"
                "Cyber-Physical Systems\nDigital-Physical Integration\nRobotics\nHuman-Computer Interaction\n"
                "Artificial Intelligence\nAutomation\nDecentralized Technologies\nEthics in Technology\n"
                "Interdisciplinary Research\nInnovation and Design\n\n"
                "- Today is the 19/02/2025, so include only events that have not happened yet. "
                "For the news, the exact date is not important.\n"
                "- The main targets for the news are undergraduate, graduate, and master students."
                "- Include the link to the article if available.\n"
                "- In the imageVideoLinks include all the links of images and videos that are related to the news.\n"
            ),
        )

        # Create the content object using the provided prompt.
        content_obj = types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )

        # Generate the content using the specified model and configuration.
        response = client.models.generate_content(
            model=self.model_name,
            contents=content_obj,
            config=generation_config,
        )

        print("Response:", response.text)
        return response.text






