import asyncio
from google import genai
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.document import DocumentChunk
from app.services.vector_store import VectorStoreService
from app.core.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def run_generation_test():
    print("\n[*] Booting Wajahni AI Core...")
    
    user_query = "Do I need to use a VPN for the hacking simulations?"
    print(f"[?] Student asks: '{user_query}'")

    print("[*] Retrieving relevant knowledge...")
    query_vector = await VectorStoreService.generate_embedding(user_query)

    async for db in get_db():
        stmt = select(DocumentChunk).order_by(
            DocumentChunk.embedding.cosine_distance(query_vector)
        ).limit(1)

        result = await db.execute(stmt)
        top_chunk = result.scalars().first()

        if not top_chunk:
            print("[-] No matching knowledge found in the database.")
            return

        print("[+] Context retrieved. Formulating response...\n")

        prompt = f"""
        You are the core intelligence of Wajahni, an AI platform dedicated to assisting students globally with university admissions, academic path planning, and institutional rules.
        
        Your task is to answer the student's question using strictly the provided INSTITUTIONAL KNOWLEDGE below. 
        Do not make up facts. Be helpful, clear, professional, and encouraging.

        INSTITUTIONAL KNOWLEDGE:
        {top_chunk.content}

        STUDENT QUESTION:
        {user_query}
        """

        try:
            # Using the blazing fast 3.5 model authorized by your API key
            response = await client.aio.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt
            )
            
            print("[+] WAJAHNI RESPONDS:")
            print("==================================================")
            print(response.text)
            print("==================================================")
            
        except Exception as e:
            print(f"[-] ERROR during generation: {e}")
            
        break

if __name__ == "__main__":
    asyncio.run(run_generation_test())
