
from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.document import Document, DocumentChunk

# Initialize with the v1alpha endpoint for maximum global model support
client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options={'api_version': 'v1alpha'})

class VectorStoreService:
    @staticmethod
    async def generate_embedding(text: str) -> list[float]:
        try:
            # Attempt 1: Try the newest model using the true async (.aio) client
            response = await client.aio.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            return response.embeddings[0].values
        except Exception:
            # Fallback: If the regional node blocks 004, use the universally stable 001 model
            response = await client.aio.models.embed_content(
                model="embedding-001",
                contents=text
            )
            return response.embeddings[0].values

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 300) -> list[str]:
        words = text.split()
        return [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

    @staticmethod
    async def ingest_document(
        db: AsyncSession, 
        university_id: int, 
        title: str, 
        content: str, 
        source_url: str = None
    ) -> int:
        doc = Document(university_id=university_id, title=title, source_url=source_url)
        db.add(doc)
        await db.flush()  

        chunks = VectorStoreService.chunk_text(content)
        
        for chunk_text in chunks:
            vector_array = await VectorStoreService.generate_embedding(chunk_text)
            
            doc_chunk = DocumentChunk(
                document_id=doc.id,
                content=chunk_text,
                embedding=vector_array
            )
            db.add(doc_chunk)
        
        await db.commit()
        return doc.id
