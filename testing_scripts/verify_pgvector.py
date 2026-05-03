import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy import select
from app.core.database import DatabaseManager
from app.core.config import get_settings
from app.models.job import Job
from pgvector.sqlalchemy import Vector

async def verify_pgvector():
    settings = get_settings()
    db_manager = DatabaseManager(settings.database_url.get_secret_value())
    
    async with db_manager.session() as session:
        # 1. Check if we can query Job with embedding
        stmt = select(Job).limit(1)
        job = (await session.execute(stmt)).scalar_one_or_none()
        
        if not job:
            print("No jobs found in DB to verify.")
            return

        print(f"Found job: {job.title}")
        print(f"Embedding type: {type(job.description_embedding)}")
        print(f"Embedding dimensions: {len(job.description_embedding)}")
        
        # 2. Test similarity search
        query_vector = [0.0] * 3072
        query_vector[0] = 1.0 # Simple dummy vector
        
        # Test cosine_distance
        dist_stmt = select(Job, Job.description_embedding.cosine_distance(query_vector).label("dist")).limit(5)
        results = (await session.execute(dist_stmt)).all()
        
        print("\nSimilarity Search Results (Top 5):")
        for j, dist in results:
            print(f"- Job: {j.title}, Distance: {dist}")
            
        print("\nVerification Successful!")

if __name__ == "__main__":
    # We need to run this inside the container or have the DB accessible
    # I'll run it inside the container for ease of environment
    asyncio.run(verify_pgvector())
