from typing import List, Optional
from datetime import datetime
from core.models.ContextualMetricRecord import ContextualMetricRecord
from core.models.AnalyzedMetricRecord import AnalyzedMetricRecord
from core.models.IndicatorScoreRecord import IndicatorScoreRecord
from core.models.Board import Board
from core.models.Environment import Environment
from ports.PersistencePort import PersistencePort
from pymongo import MongoClient


class MongoPersistenceAdapter(PersistencePort):
    def __init__(
        self,
        mongo_url="mongodb://mongodb:27017",
        db_name="iotsensing",
    ):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.collection_contextual_metrics = self.db["contextual_metrics"]
        self.collection_analyzed_metrics = self.db["analyzed_metrics"]
        self.collection_indicator_scores = self.db["indicator_scores"]
        self.collection_phq9 = self.db["phq9"]
        self.collection_boards = self.db["boards"]
        self.collection_environments = self.db["environments"]

    def get_latest_analyzed_metric_date(self, user_id: int) -> Optional[datetime]:
        cursor = (
            self.collection_analyzed_metrics.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(1)
        )
        doc = next(cursor, None)

        if doc:
            return doc["timestamp"]
        return None

    def get_first_indicator_score_date(self, user_id: int) -> Optional[datetime]:
        cursor = (
            self.collection_indicator_scores.find({"user_id": user_id})
            .sort("timestamp", 1)
            .limit(1)
        )
        doc = next(cursor, None)

        if doc:
            return doc["timestamp"]
        return None

    def get_latest_indicator_score_date(self, user_id: int) -> Optional[datetime]:
        cursor = (
            self.collection_indicator_scores.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(1)
        )
        doc = next(cursor, None)

        if doc:
            return doc["timestamp"]
        return None

    def get_latest_indicator_score(
        self, user_id: int
    ) -> Optional[IndicatorScoreRecord]:
        latest_score_doc = self.collection_indicator_scores.find_one(
            {"user_id": user_id},
            sort=[("timestamp", -1)],
        )
        return latest_score_doc

    def get_contextual_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[ContextualMetricRecord]:

        query = {"user_id": user_id}

        if start_date:
            query["timestamp"] = {"$gte": start_date}

        docs = self.collection_contextual_metrics.find(query)

        return [
            ContextualMetricRecord(
                user_id=doc["user_id"],
                timestamp=doc["timestamp"],
                metric_name=doc["metric_name"],
                contextual_value=doc["contextual_value"],
                metric_dev=doc["metric_dev"],
            )
            for doc in docs
        ]

    def get_analyzed_metrics(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
    ) -> List[AnalyzedMetricRecord]:

        query = {"user_id": user_id}

        if start_date:
            query["timestamp"] = {"$gte": start_date}

        docs = self.collection_analyzed_metrics.find(query)

        return [
            AnalyzedMetricRecord(
                user_id=doc["user_id"],
                timestamp=doc["timestamp"],
                metric_name=doc["metric_name"],
                analyzed_value=doc["analyzed_value"],
            )
            for doc in docs
        ]

    def save_analyzed_metrics(self, records: List[AnalyzedMetricRecord]) -> None:
        if not records:
            return
        dict_records = [r.to_dict() for r in records]
        self.collection_analyzed_metrics.insert_many(dict_records)
        print(f"Inserted {len(dict_records)} analyzed metrics records.")

    def save_indicator_scores(self, scores: List[IndicatorScoreRecord]) -> None:
        if not scores:
            return
        dict_records = [r.to_dict() for r in scores]
        self.collection_indicator_scores.insert_many(dict_records)
        print(f"Inserted {len(dict_records)} indicator score records.")

    def save_phq9(
        self, user_id, phq9_scores, total_score, functional_impact, timestamp
    ) -> None:
        doc = {
            "user_id": user_id,
            "timestamp": timestamp,
            "phq9_scores": phq9_scores,
            "total_score": total_score,
            "functional_impact": functional_impact,
        }
        self.collection_phq9.insert_one(doc)
        print(f"Inserted PHQ-9 answers for user {user_id} into DB.")

    # Board operations
    def get_boards_by_user(self, user_id: int) -> List[Board]:
        docs = self.collection_boards.find({"user_id": user_id})
        return [
            Board(
                board_id=doc["board_id"],
                user_id=doc["user_id"],
                mac_address=doc["mac_address"],
                name=doc["name"],
                environment_id=doc["environment_id"],
                port=doc.get("port", 0),
                is_active=doc.get("is_active", False),
                last_seen=doc.get("last_seen"),
                created_at=doc.get("created_at"),
            )
            for doc in docs
        ]

    def get_board_by_id(self, board_id: str) -> Optional[Board]:
        doc = self.collection_boards.find_one({"board_id": board_id})
        if not doc:
            return None
        return Board(
            board_id=doc["board_id"],
            user_id=doc["user_id"],
            mac_address=doc["mac_address"],
            name=doc["name"],
            environment_id=doc["environment_id"],
            port=doc.get("port", 0),
            is_active=doc.get("is_active", False),
            last_seen=doc.get("last_seen"),
            created_at=doc.get("created_at"),
        )

    def get_board_by_mac(self, mac_address: str) -> Optional[Board]:
        doc = self.collection_boards.find_one({"mac_address": mac_address})
        if not doc:
            return None
        return Board(
            board_id=doc["board_id"],
            user_id=doc["user_id"],
            mac_address=doc["mac_address"],
            name=doc["name"],
            environment_id=doc["environment_id"],
            port=doc.get("port", 0),
            is_active=doc.get("is_active", False),
            last_seen=doc.get("last_seen"),
            created_at=doc.get("created_at"),
        )

    def save_board(self, board: Board) -> str:
        result = self.collection_boards.insert_one(board.to_dict())
        print(f"Inserted board {board.board_id} into DB.")
        return board.board_id

    def update_board(self, board: Board) -> None:
        self.collection_boards.replace_one(
            {"board_id": board.board_id},
            board.to_dict(),
        )
        print(f"Updated board {board.board_id}.")

    def delete_board(self, board_id: str) -> bool:
        result = self.collection_boards.delete_one({"board_id": board_id})
        if result.deleted_count > 0:
            print(f"Deleted board {board_id}.")
            return True
        return False

    # Environment operations
    def get_environments_by_user(self, user_id: int) -> List[Environment]:
        docs = self.collection_environments.find({"user_id": user_id})
        return [
            Environment(
                environment_id=doc["environment_id"],
                user_id=doc["user_id"],
                name=doc["name"],
                description=doc.get("description"),
                created_at=doc.get("created_at"),
            )
            for doc in docs
        ]

    def get_environment_by_id(self, environment_id: str) -> Optional[Environment]:
        doc = self.collection_environments.find_one({"environment_id": environment_id})
        if not doc:
            return None
        return Environment(
            environment_id=doc["environment_id"],
            user_id=doc["user_id"],
            name=doc["name"],
            description=doc.get("description"),
            created_at=doc.get("created_at"),
        )

    def save_environment(self, environment: Environment) -> str:
        result = self.collection_environments.insert_one(environment.to_dict())
        print(f"Inserted environment {environment.environment_id} into DB.")
        return environment.environment_id

    def update_environment(self, environment: Environment) -> None:
        self.collection_environments.replace_one(
            {"environment_id": environment.environment_id},
            environment.to_dict(),
        )
        print(f"Updated environment {environment.environment_id}.")

    def delete_environment(self, environment_id: str) -> bool:
        result = self.collection_environments.delete_one(
            {"environment_id": environment_id}
        )
        if result.deleted_count > 0:
            print(f"Deleted environment {environment_id}.")
            return True
        return False
