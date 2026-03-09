import logging
import asyncpg

logger = logging.getLogger(__name__)


class TeslaMateDB:
    def __init__(self, host: str, port: int, user: str, password: str, database: str, car_id: int):
        self.dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self.car_id = car_id
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=3)
        logger.info("PostgreSQL connected")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def drives_summary(self, days: int) -> dict:
        """Total trips, km, and duration over the past N days."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                        AS trip_count,
                    COALESCE(SUM(distance), 0)      AS total_km,
                    COALESCE(SUM(duration_min), 0)  AS total_min
                FROM drives
                WHERE car_id = $1
                  AND start_date >= NOW() - ($2 || ' days')::INTERVAL
                  AND end_date IS NOT NULL
                """,
                self.car_id,
                str(days),
            )
        return dict(row)

    async def longest_drive(self) -> dict | None:
        """The single longest drive ever recorded."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    d.distance,
                    d.duration_min,
                    d.start_date,
                    sa.display_name AS start_address,
                    ea.display_name AS end_address
                FROM drives d
                LEFT JOIN addresses sa ON d.start_address_id = sa.id
                LEFT JOIN addresses ea ON d.end_address_id = ea.id
                WHERE d.car_id = $1
                  AND d.end_date IS NOT NULL
                ORDER BY d.distance DESC
                LIMIT 1
                """,
                self.car_id,
            )
        return dict(row) if row else None
