import json
import time
from collections import deque

from google import genai
from google.genai import types


class GeminiHandler:
    def __init__(self):
        self.key = json.load(open("credentials/key.json"))["key"]
        self.config = None
        self.model_name = "gemini-2.0-flash-exp" # "gemini-2.0-flash"
        self.client = genai.Client(api_key=self.key)

        self.requests_timestamps = deque(maxlen=10)  # store timestamps of last 10 requests
        self.rate_limit = 10  # requests number
        self.time_window = 60  # seconds before refresh of requests (1 minute)

    def check_rate_limit(self):
        """Check if we can make a new request based on rate limits."""
        current_time = time.time()

        # remove timestamps older than time window
        while self.requests_timestamps and current_time - self.requests_timestamps[0] >= self.time_window:
            self.requests_timestamps.popleft()

        # if less than rate_limit requests in timestamps proceed
        if len(self.requests_timestamps) < self.rate_limit:
            self.requests_timestamps.append(current_time)
            return True

        # calculate wait time if it is at the limit
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

    @staticmethod
    def divide_into_blocks(prompt):
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

        max_block_size = 2000000

        # if text is small enough, return as single block
        if len(prompt) <= max_block_size:
            return [prompt]

        # split into blocks
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
        json_schema = types.Schema(
            type="OBJECT",
            enum=[],
            required=["news"],
            properties={
                "news": types.Schema(
                    type="ARRAY",
                    items=types.Schema(
                        type="OBJECT",
                        enum=[],
                        required=["source", "brief description", "relevancy", "location"],
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

        # define the generation configuration
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

        # content object using the provided prompt
        content_obj = types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )

        # generate the content using the specified model and configuration
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=content_obj,
            config=generation_config,
        )

        print("Response:", response.text)
        return response.text

    def divide_news_gemini(self, prompt):
        json_schema = types.Schema(
            type="OBJECT",
            enum=[],
            required=["news"],
            properties={
                "news": types.Schema(
                    type="ARRAY",
                    items=types.Schema(
                        type="OBJECT",
                        enum=[],
                        required=["title", "source", "location", "description", "summary", "category", "link"],
                        properties={
                            "title": types.Schema(type="STRING"),
                            "source": types.Schema(type="STRING"),
                            "location": types.Schema(type="STRING"),
                            "contact": types.Schema(type="STRING"),
                            "description": types.Schema(type="STRING"),
                            "summary": types.Schema(type="STRING"),
                            "category": types.Schema(type="STRING"),
                            "link": types.Schema(type="STRING"),
                            "image": types.Schema(type="STRING"),
                        },
                    ),
                ),
            },
        )

        # define the generation configuration
        generation_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_schema=json_schema,
            response_mime_type="application/json",
            system_instruction=(
                "- Only include images if provided in the prompt and the path is absolute\n"
                "- If the location is not specified or is an online meeting say Online\n"
                "- If contact is not included don't include it\n"
                "- The description of the news should be a detailed description of the news\n"
                "- The summary of the news should be a really quick bite-sized summary of the news\n"
                "- Only include the link to the article or website of the news\n"
            ),
        )

        # create the content object using the provided prompt
        content_obj = types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )

        # generate the content using the specified model and configuration.
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=content_obj,
            config=generation_config,
        )

        print("Response:", response.text)
        return response.text