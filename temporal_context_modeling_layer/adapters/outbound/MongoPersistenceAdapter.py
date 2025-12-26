from typing import List, Optional
from datetime import datetime
from collections import defaultdict
from core.models.RawMetricRecord import RawMetricRecord
from core.models.AggregatedMetricRecord import AggregatedMetricRecord
from core.models.ContextualMetricRecord import ContextualMetricRecord
from ports.PersistencePort import PersistencePort
from pymongo import MongoClient


# Database routing map based on system_mode
DB_MAP = {
    "live": "iotsensing_live",
    "dataset": "iotsensing_dataset",
    "demo": "iotsensing_demo",
    None: "iotsensing_live",  # Default fallback
}

# All databases to query for comprehensive reads
ALL_DBS = ["iotsensing_live", "iotsensing_dataset", "iotsensing_demo"]


class MongoPersistenceAdapter(PersistencePort):
    def __init__(
        self,
        mongo_url="mongodb://mongodb:27017",
        db_name="iotsensing_live",  # Default to live database
    ):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.collection_raw_metrics = self.db["raw_metrics"]
        self.collection_aggregated_metrics = self.db["aggregated_metrics"]
        self.collection_contextual_metrics = self.db["contextual_metrics"]

    def _get_db(self, system_mode: str = None):
        """Get database based on system_mode for routing."""
        db_name = DB_MAP.get(system_mode, "iotsensing_live")
        return self.client[db_name]

    def get_latest_aggregated_metric_date(self, user_id: int) -> Optional[datetime]:
        """Query all databases and return the latest date."""
        latest = None
        for db_name in ALL_DBS:
            db = self.client[db_name]
            cursor = (
                db["aggregated_metrics"].find({"user_id": user_id})
                .sort("timestamp", -1)
                .limit(1)
            )
            doc = next(cursor, None)
            if doc and doc.get("timestamp"):
                if latest is None or doc["timestamp"] > latest:
                    latest = doc["timestamp"]
        return latest

    def get_latest_contextual_metric_date(self, user_id: int) -> Optional[datetime]:
        """Query all databases and return the latest date."""
        latest = None
        for db_name in ALL_DBS:
            db = self.client[db_name]
            cursor = (
                db["contextual_metrics"].find({"user_id": user_id})
                .sort("timestamp", -1)
                .limit(1)
            )
            doc = next(cursor, None)
            if doc and doc.get("timestamp"):
                if latest is None or doc["timestamp"] > latest:
                    latest = doc["timestamp"]
        return latest

    def get_raw_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[RawMetricRecord]:
        """Query all databases and combine results."""
        query = {"user_id": user_id}
        if start_date:
            query["timestamp"] = {"$gte": start_date}

        all_records = []
        for db_name in ALL_DBS:
            db = self.client[db_name]
            # Determine system_mode from db_name
            system_mode = next((k for k, v in DB_MAP.items() if v == db_name and k is not None), "live")
            docs = db["raw_metrics"].find(query)
            for doc in docs:
                all_records.append(
                    RawMetricRecord(
                        user_id=doc["user_id"],
                        timestamp=doc["timestamp"],
                        metric_name=doc["metric_name"],
                        metric_value=doc["metric_value"],
                        system_mode=doc.get("system_mode", system_mode),
                    )
                )
        return all_records

    def save_aggregated_metrics(self, records: List[AggregatedMetricRecord]) -> None:
        """Route records to appropriate database based on system_mode."""
        if not records:
            return

        # Group by system_mode
        records_by_mode = defaultdict(list)
        for r in records:
            system_mode = r.system_mode
            records_by_mode[system_mode].append(r.to_dict())

        # Save to each database
        total = 0
        for system_mode, dict_records in records_by_mode.items():
            db = self._get_db(system_mode)
            db["aggregated_metrics"].insert_many(dict_records)
            db_name = DB_MAP.get(system_mode, "iotsensing_live")
            print(f"Inserted {len(dict_records)} aggregated metrics to {db_name}")
            total += len(dict_records)
        print(f"Total: {total} aggregated metrics records inserted.")

    def get_aggregated_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Query all databases and combine results as dicts for DataFrame."""
        query = {"user_id": user_id}
        if start_date:
            query["timestamp"] = {"$gte": start_date}

        all_records = []
        for db_name in ALL_DBS:
            db = self.client[db_name]
            system_mode = next((k for k, v in DB_MAP.items() if v == db_name and k is not None), "live")
            docs = db["aggregated_metrics"].find(query)
            for doc in docs:
                all_records.append({
                    "user_id": doc["user_id"],
                    "timestamp": doc["timestamp"],
                    "metric_name": doc["metric_name"],
                    "aggregated_value": doc["aggregated_value"],
                    "system_mode": doc.get("system_mode", system_mode),
                })
        return all_records

    def save_contextual_metrics(self, records: List[ContextualMetricRecord]) -> None:
        """Route records to appropriate database based on system_mode."""
        if not records:
            return

        # Group by system_mode
        records_by_mode = defaultdict(list)
        for r in records:
            system_mode = r.system_mode
            records_by_mode[system_mode].append(r.to_dict())

        # Save to each database
        total = 0
        for system_mode, dict_records in records_by_mode.items():
            db = self._get_db(system_mode)
            db["contextual_metrics"].insert_many(dict_records)
            db_name = DB_MAP.get(system_mode, "iotsensing_live")
            print(f"Inserted {len(dict_records)} contextual metrics to {db_name}")
            total += len(dict_records)
        print(f"Total: {total} contextual metrics records inserted.")

    def get_contextual_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[ContextualMetricRecord]:
        """Query all databases and combine results."""
        query = {"user_id": user_id}
        if start_date:
            query["timestamp"] = {"$gte": start_date}

        all_records = []
        for db_name in ALL_DBS:
            db = self.client[db_name]
            system_mode = next((k for k, v in DB_MAP.items() if v == db_name and k is not None), "live")
            docs = db["contextual_metrics"].find(query)
            for doc in docs:
                all_records.append(
                    ContextualMetricRecord(
                        user_id=doc["user_id"],
                        timestamp=doc["timestamp"],
                        metric_name=doc["metric_name"],
                        contextual_value=doc["contextual_value"],
                        metric_dev=doc.get("metric_dev", 0.0),
                        system_mode=doc.get("system_mode", system_mode),
                    )
                )
        return all_records
