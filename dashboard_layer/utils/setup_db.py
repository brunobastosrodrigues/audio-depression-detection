from pymongo import MongoClient

def setup_indexes():
    client = MongoClient("mongodb://mongodb:27017")
    db = client["iotsensing"]
    
    collections = [
        "raw_metrics", 
        "aggregated_metrics", 
        "contextual_metrics", 
        "analyzed_metrics",
        "indicator_scores"
    ]
    
    for coll_name in collections:
        print(f"Ensuring indexes for {coll_name}...")
        db[coll_name].create_index([("user_id", 1), ("timestamp", -1)])
        db[coll_name].create_index([("board_id", 1)])
    
    # Boards collection
    db["boards"].create_index([("mac_address", 1)], unique=True)
    db["boards"].create_index([("user_id", 1)])
    
    print("Indexing complete.")

if __name__ == "__main__":
    setup_indexes()
