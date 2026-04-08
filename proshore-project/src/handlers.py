import logging
from services import AIExtractionService
from redis_cache import RedisSemanticCache

class TicketActionHandler:
    """
    The Action Handler coordinates the workflow between our highly decoupled services.
    It doesn't care HOW things are cached or extracted, it just directs the flow.
    """
    def __init__(self):
        # Initialize services once to reuse network connections
        self.ai_service = AIExtractionService()
        self.vector_cache = RedisSemanticCache(similarity_threshold=0.95)

    async def handle_ticket(self, content: str, filename: str) -> dict:
        """Main action handler workflow for incoming tickets."""
        
        # 1. Protective Truncation
        if len(content) > 4000:
            logging.warning(f"File {filename} is too large. Truncating.")
            content = content[:4000] + "\n...[TRUNCATED FOR TOKENS]"
        
        # 2. Vector Cache Interception
        logging.info(f"🔍 Checking semantic cache for {filename}...")
        cached_result, query_embedding = await self.vector_cache.search_cache(content)
        
        if cached_result:
            logging.info(f"🎯 Cache HIT for {filename}")
            final_doc = cached_result
            final_doc["CacheStatus"] = "HIT"
        else:
            logging.info(f"❌ Cache MISS for {filename}. Calling OpenAI GPT-4o...")
            # 3. LLM Extraction
            extracted_data = await self.ai_service.extract_ticket_data(content)
            logging.info(f"✅ OpenAI extraction complete for {filename}")
            final_doc = extracted_data.model_dump()
            
            # 4. Save to Cache
            logging.info(f"💾 Saving {filename} to Redis vector store...")
            await self.vector_cache.store_in_cache(query_embedding, final_doc)
            final_doc["CacheStatus"] = "MISS"
            
        final_doc["OriginalFile"] = filename
        final_doc["Status"] = "Processed"
        
        return final_doc
