from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, MONGO_DB_NAME

client: AsyncIOMotorClient = None
db = None


async def connect_db():
    """Open a MongoDB connection pool on startup."""
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    # Verify connection
    await client.admin.command("ping")
    print(f"[DB] Connected to MongoDB — database: '{MONGO_DB_NAME}'")


async def close_db():
    """Close the connection pool on shutdown."""
    global client
    if client:
        client.close()
        print("[DB] MongoDB connection closed")


def get_db():
    """Return the active database instance."""
    return db
