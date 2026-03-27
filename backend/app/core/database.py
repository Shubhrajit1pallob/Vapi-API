from pymongo import MongoClient
from backend.app.core.config import settings
from typing import Optional

# Global MongoDB client
client: Optional[MongoClient] = None
db = None


def connect_to_mongo():
    """Connect to MongoDB"""
    global client, db
    client = MongoClient(settings.mongodb_url)
    db = client[settings.database_name]
    print("Connected to MongoDB")


def close_mongo_connection():
    """Close MongoDB connection"""
    global client
    if client is not None:
        client.close()
        print("Closed MongoDB connection")


def get_database():
    """Get the MongoDB database instance"""
    return db
