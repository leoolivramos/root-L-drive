from abc import ABC, abstractmethod
from app.domain.entities.machine import MachineEntity


class MachineRepository(ABC):
    @abstractmethod
    async def create(self, owner_id: str, name: str, allowed_paths: list[str], token_hash: str, token_prefix: str, token_last4: str, expires_at=None) -> MachineEntity:
        raise NotImplementedError()

    @abstractmethod
    async def list_by_owner(self, owner_id: str, limit: int = 200) -> list[MachineEntity]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_id(self, machine_id: str, owner_id: str) -> MachineEntity | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_active_by_hash(self, token_hash: str) -> MachineEntity | None:
        raise NotImplementedError()

    @abstractmethod
    async def revoke(self, machine_id: str, owner_id: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def touch_last_seen(self, machine_id: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def update_allowed_paths(self, machine_id: str, allowed_paths: list[str]) -> MachineEntity | None:
        raise NotImplementedError()
