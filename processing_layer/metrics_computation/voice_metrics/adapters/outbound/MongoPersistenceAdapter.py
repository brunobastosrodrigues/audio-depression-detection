from pymongo import MongoClient
from ports.PersistencePort import PersistencePort
from collections import defaultdict
import numbers


# Database routing map based on system_mode
DB_MAP = {
    "live": "iotsensing_live",
    "dataset": "iotsensing_dataset",
    "demo": "iotsensing_demo",
    None: "iotsensing_live",  # Default fallback
}


class MongoPersistenceAdapter(PersistencePort):
    def __init__(
        self,
        mongo_url="mongodb://mongodb:27017",
        db_name="iotsensing_live",  # Default to live database
        collection_name="raw_metrics",
    ):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.collection_name = collection_name

    def _get_db(self, system_mode: str = None):
        """Get database based on system_mode for routing."""
        db_name = DB_MAP.get(system_mode, "iotsensing_live")
        return self.client[db_name]

    def save_metrics(self, metrics: list[dict]) -> None:
        """
        Saves metrics to MongoDB.
        Supports both legacy flat format and new grouped format.
        """
        if not metrics:
            print("No metrics to save.")
            return

        # Group metrics by system_mode for database routing
        metrics_by_mode = defaultdict(list)

        for m in metrics:
            # Check for new grouped format (has "metrics" dict instead of "metric_value")
            if "metrics" in m and isinstance(m["metrics"], dict):
                # New Grouped Format
                system_mode = m.pop("system_mode", None)

                # Sanitize numeric values in the metrics dictionary
                sanitized_metrics = {}
                for k, v in m["metrics"].items():
                    try:
                        numeric_val = float(v)
                        if not (numeric_val != numeric_val or numeric_val in [float("inf"), float("-inf")]):
                             sanitized_metrics[k] = numeric_val
                    except (TypeError, ValueError):
                        pass # Skip invalid

                m["metrics"] = sanitized_metrics
                metrics_by_mode[system_mode].append(m)

            else:
                # Legacy Flat Format
                value = m.get("metric_value")
                system_mode = m.pop("system_mode", None)

                try:
                    numeric_value = float(value)

                    if not (
                        numeric_value != numeric_value
                        or numeric_value in [float("inf"), float("-inf")]
                    ):
                        m["metric_value"] = numeric_value
                        metrics_by_mode[system_mode].append(m)
                    else:
                        print(f"Skipped invalid (NaN/inf) metric: {m}")

                except (TypeError, ValueError):
                    print(f"Skipped non-numeric or malformed metric: {m}")

        if not any(metrics_by_mode.values()):
            print("No valid numeric metrics to save.")
            return

        # Save to appropriate database for each system_mode
        total_saved = 0
        for system_mode, mode_metrics in metrics_by_mode.items():
            if mode_metrics:
                db = self._get_db(system_mode)
                collection = db[self.collection_name]
                result = collection.insert_many(mode_metrics)
                db_name = DB_MAP.get(system_mode, "iotsensing_live")
                print(f"Saved {len(result.inserted_ids)} metrics to {db_name}.{self.collection_name}")
                total_saved += len(result.inserted_ids)

        print(f"Total: {total_saved} metric records saved.")
