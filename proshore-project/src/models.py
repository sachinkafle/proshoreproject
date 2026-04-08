from pydantic import BaseModel, Field

class TicketExtraction(BaseModel):
    """
    Domain Model representing the exact JSON structure we expect Open AI to return.
    """
    category: str = Field(description="Must be exactly one of: Billing, Technical Support, Bug Report, Feature Request")
    urgency: str = Field(description="Must be exactly one of: Low, Medium, High")
    summary: str = Field(description="A concise one-sentence summary of the user's issue")
