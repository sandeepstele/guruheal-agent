import asyncpg
import asyncio
import psycopg2

async def test_connection():
    try:
        conn = await asyncpg.connect(
            host='aws-0-ap-south-1.pooler.supabase.com',
            port=5432,
            user='postgres.foartimacvkfjphhgjxm',
            password='pwI95AFNsBEa47Gs',
            database='postgres'
        )
        print("Connected successfully!")
        await conn.close()
    except Exception as e:
        print(f"Connection error: {repr(e)}")

asyncio.run(test_connection())