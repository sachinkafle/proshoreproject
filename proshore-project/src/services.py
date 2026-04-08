from openai import AsyncAzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from config import get_settings
from models import TicketExtraction
from prompts import SYSTEM_PROMPT

class AIExtractionService:
    """
    Service responsible specifically for communicating with text-completion LLMs.
    """
    def __init__(self):
        settings = get_settings()
        self.deployment_name = settings.AZURE_OPENAI_DEPLOYMENT_NAME
        self.client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-08-01-preview"
        )
        logging.info("⚡ AIExtractionService Initialized.")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def extract_ticket_data(self, content: str) -> TicketExtraction:
        """Invokes structured output completion with automatic exponential backoff."""
        response = await self.client.beta.chat.completions.parse(
            model=self.deployment_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Ticket Content:\n{content}"}
            ],
            response_format=TicketExtraction
        )
        return response.choices[0].message.parsed
