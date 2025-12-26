from pymongo import MongoClient
import os

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://mongodb:27017")
DB_NAME = "iotsensing_live"

def setup_ttl_index():
    print(f"Connecting to MongoDB at {MONGO_URL}...")
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    collection = db["raw_metrics"]

    # 30 days in seconds
    ttl_seconds = 30 * 24 * 3600

    print("Checking existing indexes...")
    indexes = collection.index_information()
    print(indexes)

    # Create or update TTL index
    print(f"Creating/Updating TTL index on 'timestamp' for {ttl_seconds} seconds (30 days)...")

    # Note: If index exists with different options, this might fail or need dropping first.
    # We try to create it. If it exists with different expireAfterSeconds, we might need to drop it.
    try:
        collection.create_index("timestamp", expireAfterSeconds=ttl_seconds)
        print("TTL index created successfully.")
    except Exception as e:
        print(f"Error creating index (might already exist with different params): {e}")
        print("Attempting to drop and recreate...")
        try:
            collection.drop_index("timestamp_1") # Default name usually
            collection.create_index("timestamp", expireAfterSeconds=ttl_seconds)
            print("TTL index recreated successfully.")
        except Exception as e2:
            print(f"Failed to recreate index: {e2}")

if __name__ == "__main__":
    setup_ttl_index()
