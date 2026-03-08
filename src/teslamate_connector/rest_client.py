import logging
import httpx

logger = logging.getLogger(__name__)


class TeslaMateApiClient:
    def __init__(self, base_url: str, car_id: int):
        self.base_url = base_url.rstrip("/")
        self.car_id = car_id
        self._client = httpx.AsyncClient(timeout=10.0, trust_env=False)

    async def get_cars(self) -> list[dict]:
        url = f"{self.base_url}/api/v1/cars"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json().get("data", resp.json())

    async def get_charges(self, page: int = 1) -> dict:
        url = f"{self.base_url}/api/v1/cars/{self.car_id}/charges"
        resp = await self._client.get(url, params={"page": page})
        resp.raise_for_status()
        return resp.json()

    async def get_drives(self, page: int = 1) -> dict:
        url = f"{self.base_url}/api/v1/cars/{self.car_id}/drives"
        resp = await self._client.get(url, params={"page": page})
        resp.raise_for_status()
        return resp.json()

    async def get_stats(self) -> dict:
        url = f"{self.base_url}/api/v1/cars/{self.car_id}/stats"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._client.aclose()
