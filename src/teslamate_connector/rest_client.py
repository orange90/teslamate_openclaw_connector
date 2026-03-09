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

    async def get_all_drives(self, max_pages: int = 20) -> list[dict]:
        """Fetch all drives across pages up to max_pages."""
        all_drives = []
        for page in range(1, max_pages + 1):
            data = await self.get_drives(page=page)
            drives = data.get("data", [])
            if not drives:
                break
            all_drives.extend(drives)
        return all_drives

    async def get_stats(self) -> dict:
        url = f"{self.base_url}/api/v1/cars/{self.car_id}/stats"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._client.aclose()
