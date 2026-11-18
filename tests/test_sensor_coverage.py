"""Regression for sensors with incomplete sampling metadata."""

import asyncio
import re
import sqlite3
from unittest.mock import AsyncMock

from openaq_api.v3.models.responses import SensorsResponse
from openaq_api.v3.routers.sensors import LocationSensorQuery, fetch_sensors


def test_sensor_coverage_requires_sampling_intervals():
    db = AsyncMock()
    asyncio.run(fetch_sensors(LocationSensorQuery(locations_id=1), db))
    sql = db.fetchPage.await_args.args[0]
    coverage = sql.split("END as summary", 1)[1].split("END as coverage", 1)[0]
    condition = re.search(r"WHEN\s+(.*?)\s+THEN", coverage, re.DOTALL).group(1)

    statement = (
        f"SELECT CASE WHEN {condition} THEN 1 ELSE 0 END "
        "FROM (SELECT ? value_latest) r "
        "CROSS JOIN (SELECT ? data_averaging_period_seconds, "
        "? data_logging_period_seconds) s"
    )
    cases = (
        ((3.2, 60, 60), 1),
        ((3.2, None, 60), 0),
        ((3.2, 60, None), 0),
        ((3.2, 0, 60), 0),
        ((3.2, -60, 60), 0),
        ((None, 60, 60), 0),
    )
    with sqlite3.connect(":memory:") as connection:
        for values, expected in cases:
            assert connection.execute(statement, values).fetchone()[0] == expected


def test_sensor_response_accepts_missing_coverage():
    sensor = {
        "id": 1,
        "name": "pm25 ug/m3",
        "parameter": {"id": 1, "name": "pm25", "units": "ug/m3"},
        "summary": {"avg": 3.2},
        "coverage": None,
        "latest": {
            "datetime": {
                "utc": "2026-01-01T00:00:00Z",
                "local": "2026-01-01T00:00:00Z",
            },
            "value": 3.2,
            "coordinates": {"latitude": 1.0, "longitude": 2.0},
        },
    }
    response = SensorsResponse.model_validate({"results": [sensor]})
    assert response.results[0].coverage is None
    assert response.results[0].summary.avg == 3.2
    assert response.results[0].latest.value == 3.2
