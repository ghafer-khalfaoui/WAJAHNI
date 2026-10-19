import asyncio
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.document import DocumentChunk
from app.services.vector_store import VectorStoreService

async def run_search_test():
    print("\n[*] Initializing Wajahni Semantic Search...")
    
    # 1. The simulated student question
    user_query = "Do I need to use a VPN for the hacking simulations?"
    print(f"[?] Student asks: '{user_query}'")

    # 2. Translate the question into math
    print("[*] Generating vector for the question...")
    query_vector = await VectorStoreService.generate_embedding(user_query)

    # Open database connection
    async for db in get_db():
        print("[*] Scanning memory core for closest mathematical match...")
        
        try:
            # 3. Query pgvector using Cosine Distance
            # We order the results so the closest mathematical match rises to the top
            stmt = select(DocumentChunk).order_by(
                DocumentChunk.embedding.cosine_distance(query_vector)
            ).limit(1)

            result = await db.execute(stmt)
            top_chunk = result.scalars().first()

            if top_chunk:
                print("\n[+] SUCCESS! Retrieved context:")
                print("==================================================")
                print(top_chunk.content)
                print("==================================================")
            else:
                print("\n[-] No matching knowledge found in the database.")
                
        except Exception as e:
            print(f"\n[-] ERROR during search: {e}")
            
        break

if __name__ == "__main__":
    asyncio.run(run_search_test())