import asyncio
from sqlalchemy.future import select

# We import get_db directly to avoid naming mismatches with the session factory
from app.core.database import get_db
from app.models.university import University
from app.models.document import Document, DocumentChunk
from app.services.vector_store import VectorStoreService

async def run_test():
    print("\n[*] Initializing Wajahni Vector Test...")
    
    # Using the get_db generator safely inside an async context
    async for db in get_db():
        
        # 1. Verify or create the institutional tenant
        result = await db.execute(select(University).filter_by(domain="gju.edu.jo"))
        uni = result.scalars().first()
        
        if not uni:
            print("[*] Creating institutional tenant...")
            uni = University(
                name="German Jordanian University", 
                domain="gju.edu.jo", 
                primary_color="#003366", 
                secondary_color="#e6f2ff"
            )
            db.add(uni)
            await db.commit()
            await db.refresh(uni)

        # 2. The Raw Knowledge Payload
        sample_text = (
            "The Cybersecurity lab provides access to multi-threaded port scanners, network sniffers, "
            "and RSA cryptanalysis tools. Students practicing ethical hacking and red-blue enterprise "
            "simulations must connect through the designated SIEM-monitored VPN to maintain a secure environment."
        )

        print(f"[*] Ingesting document for Tenant ID: {uni.id}")
        
        # 3. Execute the Ingestion Pipeline
        try:
            doc_id = await VectorStoreService.ingest_document(
                db=db,
                university_id=uni.id,
                title="Advanced Cyber Security Syllabus",
                content=sample_text,
                source_url="https://gju.edu.jo/cyber-syllabus"
            )
            print(f"[+] SUCCESS! Document ingested with internal ID: {doc_id}")

            # 4. Verify the pgvector data actually saved
            chunk_result = await db.execute(select(DocumentChunk).filter_by(document_id=doc_id))
            chunks = chunk_result.scalars().all()

            print(f"[+] Discovered {len(chunks)} vectorized chunks in database.")
            for chunk in chunks:
                print(f"    -> Extracted Text: '{chunk.content[:50]}...'")
                print(f"    -> Vector Dimensions: {len(chunk.embedding)}")
                print(f"    -> Mathematical Coordinates (Snippet): {chunk.embedding[:5]}...\n")
                
        except Exception as e:
            print(f"[-] ERROR: {e}")
            
        # Break the generator loop after one iteration
        break

if __name__ == "__main__":
    asyncio.run(run_test())