from datetime import datetime, timezone

from app.db.id_utils import as_object_id, is_valid_object_id
from app.domain.entities.machine import MachineEntity
from app.domain.repositories.machine_repository import MachineRepository


def machine_from_mongo(doc: dict) -> MachineEntity:
    return MachineEntity(
        id=str(doc["_id"]),
        owner_id=doc["owner_id"],
        name=doc["name"],
        token_hash=doc["token_hash"],
        token_prefix=doc.get("token_prefix", ""),
        token_last4=doc.get("token_last4", ""),
        allowed_paths=doc.get("allowed_paths", []),
        created_at=doc["created_at"],
        last_seen=doc.get("last_seen"),
        revoked_at=doc.get("revoked_at"),
        is_active=doc.get("is_active", True),
    )


class MongoMachineRepository(MachineRepository):
    def __init__(self, db):
        self.collection = db["machines"]

    async def create(self, owner_id: str, name: str, allowed_paths: list[str], token_hash: str, token_prefix: str, token_last4: str, expires_at=None) -> MachineEntity:
        now = datetime.now(timezone.utc)
        doc = {
            "owner_id": owner_id,
            "name": name,
            "allowed_paths": allowed_paths,
            "token_hash": token_hash,
            "token_prefix": token_prefix,
            "token_last4": token_last4,
            "created_at": now,
            "last_seen": None,
            "expires_at": expires_at,
            "revoked_at": None,
            "is_active": True,
        }
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return machine_from_mongo(doc)

    async def list_by_owner(self, owner_id: str, limit: int = 200) -> list[MachineEntity]:
        safe_limit = max(1, min(limit, 1000))
        cursor = self.collection.find({"owner_id": owner_id}).sort("created_at", -1).limit(safe_limit)
        docs = await cursor.to_list(length=safe_limit)
        return [machine_from_mongo(doc) for doc in docs]

    async def get_by_id(self, machine_id: str, owner_id: str) -> MachineEntity | None:
        if not is_valid_object_id(machine_id):
            return None
        doc = await self.collection.find_one({"_id": as_object_id(machine_id), "owner_id": owner_id})
        return machine_from_mongo(doc) if doc else None

    async def get_active_by_hash(self, token_hash: str):
        doc = await self.collection.find_one({"token_hash": token_hash, "is_active": True})
        if doc is None:
            return None
        expires_at = doc.get("expires_at")
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            return None
        return machine_from_mongo(doc)

    async def revoke(self, machine_id: str, owner_id: str) -> bool:
        if not is_valid_object_id(machine_id):
            return False
        now = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"_id": as_object_id(machine_id), "owner_id": owner_id, "is_active": True},
            {"$set": {"is_active": False, "revoked_at": now}},
        )
        return result.modified_count == 1

    async def touch_last_seen(self, machine_id: str) -> None:
        if not is_valid_object_id(machine_id):
            return
        await self.collection.update_one(
            {"_id": as_object_id(machine_id)},
            {"$set": {"last_seen": datetime.now(timezone.utc)}},
        )

    async def update_allowed_paths(self, machine_id: str, allowed_paths: list[str]) -> MachineEntity | None:
        if not is_valid_object_id(machine_id):
            return None

        normalized_allowed_paths = [path.strip() for path in allowed_paths if isinstance(path, str) and path.strip()]
        await self.collection.update_one(
            {"_id": as_object_id(machine_id)},
            {"$set": {"allowed_paths": normalized_allowed_paths}},
        )
        doc = await self.collection.find_one({"_id": as_object_id(machine_id)})
        return machine_from_mongo(doc) if doc else None
