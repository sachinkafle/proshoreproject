import numpy as np
import logging
import os
from typing import Optional, Tuple
from openai import AsyncAzureOpenAI
import redis.asyncio as redis
from redisvl.index import AsyncSearchIndex
from redisvl.schema import IndexSchema
from redisvl.query import VectorQuery

from config import get_settings

class RedisSemanticCache:
    """
    High-performance semantic cache using Redis Stack (Vector Similarity Search).
    This persists across reboots and scales to millions of records.
    """
    def __init__(self, similarity_threshold: float = 0.95):
        settings = get_settings()
        self.similarity_threshold = similarity_threshold
        
        # 1. Initialize OpenAI client for embeddings
        self.ai_client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-08-01-preview"
        )
        self.embedding_deployment = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
        
        # 2. Define Redis Index Schema
        schema_dict = {
            "index": {
                "name": settings.REDIS_INDEX_NAME,
                "prefix": "ticket:",
                "storage_type": "hash"
            },
            "fields": [
                {"name": "category", "type": "tag"},
                {"name": "urgency", "type": "tag"},
                {"name": "summary", "type": "text"},
                {
                    "name": "content_vector",
                    "type": "vector",
                    "attrs": {
                        "dims": 1536,
                        "algorithm": "hnsw",
                        "distance_metric": "cosine",
                        "datatype": "float32"
                    }
                }
            ]
        }
        self.schema = IndexSchema.from_dict(schema_dict)
        
        # 3. Create Async Redis Client and Search Index
        # We relax SSL cert requirements for local-to-azure testing
        # If Managed Identity (Entra ID) is enabled, we use a credential provider
        credential_provider = None
        if settings.REDIS_USE_ENTRA_ID:
            from redis_entraid.cred_provider import create_from_default_azure_credential
            logging.info("🔐 Initializing Redis Entra ID (Managed Identity) Authentication...")
            # Azure Redis Scope: https://redis.azure.com/.default
            credential_provider = create_from_default_azure_credential(
                ("https://redis.azure.com/.default",)
            )

        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=None if settings.REDIS_USE_ENTRA_ID else settings.REDIS_PASSWORD,
            credential_provider=credential_provider,
            ssl=settings.REDIS_USE_SSL,
            ssl_cert_reqs=None, 
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        self.index = AsyncSearchIndex(self.schema, redis_client=self.redis_client)
        logging.info(f"🧠 Redis Semantic Cache Initialized on: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        logging.info(f"👉 Index Name: {settings.REDIS_INDEX_NAME} | SSL: {settings.REDIS_USE_SSL}")

    async def _check_connection(self):
        """Diagnostic ping to confirm the network path is open."""
        try:
            await self.redis_client.ping()
            logging.info("⚡ Redis Ping Successful!")
            return True
        except Exception as e:
            logging.error(f"❌ Redis Connection Failed: {str(e)}")
            return False

    async def _get_embedding(self, text: str) -> np.ndarray:
        """Calls Azure OpenAI to convert text into a dense vector asynchronously."""
        response = await self.ai_client.embeddings.create(
            input=text,
            model=self.embedding_deployment
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    async def search_cache(self, text: str) -> Tuple[Optional[dict], np.ndarray]:
        """
        Performs a Vector Similarity Search in Redis.
        Returns (result, embedding).
        """
        # 1. Diagnostic Ping
        if not await self._check_connection():
            return None, await self._get_embedding(text)

        query_embedding = await self._get_embedding(text)
        logging.info("📟 Embedding received from Azure OpenAI.")
        
        try:
            # 1. Check if index exists, create if not (first run)
            if not await self.index.exists():
                logging.info(f"🏗️ Index '{self.index.name}' not found. Creating it now...")
                await self.index.create()
                logging.info("✅ Index created successfully.")
                return None, query_embedding

            logging.info(f"🔎 Executing Vector Query on Redis...")
            
            # Using raw redis-py Search for maximum compatibility
            from redis.commands.search.query import Query

            query_str = "(*)=>[KNN 1 @content_vector $vec_param AS vector_score]"
            params = {"vec_param": query_embedding.astype(np.float32).tobytes()}
            
            # Prepare actual search command
            search_query = (
                Query(query_str)
                .sort_by("vector_score")
                .paging(0, 1)
                .return_fields("category", "urgency", "summary", "vector_score")
                .dialect(2)
            )

            # Search directly on the index via the underlying client
            results_obj = await self.redis_client.ft(self.index.name).search(search_query, query_params=params)
            results = results_obj.docs
            logging.info(f"📊 Redis search returned {len(results)} matches.")

            if not results:
                return None, query_embedding

            best_match = results[0]
            # Similarity = 1 - Distance (Cosine)
            similarity_score = 1.0 - float(best_match.vector_score)
            logging.info(f"Best Redis vector match score: {similarity_score:.4f}")

            # Threshold check
            if similarity_score > 0.95:
                logging.info(f"🎯 Redis Semantic Cache HIT! (Similarity: {similarity_score:.4f})")
                return {
                    "category": best_match.category,
                    "urgency": best_match.urgency,
                    "summary": best_match.summary
                }, query_embedding
            
            logging.info(f"⚪ Redis Cache Miss (Score {similarity_score:.4f} below threshold).")
            return None, query_embedding

        except Exception as e:
            error_str = str(e)
            # If search logic is failing due to an old/incompatible index, we clear it and try once more
            if "No such parameter" in error_str:
                logging.warning(f"⚠️ Index compatibility issue detected. Deleting '{self.index.name}' to reset...")
                try:
                    await self.index.delete()
                    await self.index.create()
                    logging.info("✅ Index reset complete. Next run will be optimal.")
                except Exception as drop_error:
                    logging.error(f"Failed to reset index: {str(drop_error)}")
            else:
                logging.error(f"❌ Redis Search error: {error_str}")
            return None, query_embedding

        if similarity_score >= self.similarity_threshold:
            logging.info("🎯 Redis Semantic Cache HIT!")
            return {
                "category": best_match["category"],
                "urgency": best_match["urgency"],
                "summary": best_match["summary"]
            }, query_embedding
        
        return None, query_embedding

    async def store_in_cache(self, embedding: np.ndarray, result: dict):
        """Persists the result and its vector in Redis."""
        try:
            # Check connection first
            if not await self._check_connection():
                logging.warning("⚠️ Skipping Redis save due to connection failure.")
                return

            doc = {
                "category": result["category"],
                "urgency": result["urgency"],
                "summary": result["summary"],
                "content_vector": embedding.astype(np.float32).tobytes()
            }
            
            import uuid
            key = str(uuid.uuid4())
            
            await self.index.load([doc], keys=[f"ticket:{key}"])
            logging.info("✅ Result persisted in Redis Vector Store.")
        except Exception as e:
            logging.error(f"❌ Failed to save to Redis: {str(e)}")
