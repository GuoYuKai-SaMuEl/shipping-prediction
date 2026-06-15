import os
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


def get_client():
    return InfluxDBClient(
        url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
        token=os.getenv("INFLUXDB_TOKEN", "shipping-super-secret-token"),
        org=os.getenv("INFLUXDB_ORG", "shipping-org"),
    )


def write_metric(measurement: str, tags: dict, fields: dict, timestamp: datetime = None):
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    bucket = os.getenv("INFLUXDB_BUCKET", "shipping-metrics")

    point = Point(measurement)
    for k, v in tags.items():
        point = point.tag(k, v)
    for k, v in fields.items():
        point = point.field(k, v)

    ts = timestamp or datetime.now(timezone.utc)
    point = point.time(ts, WritePrecision.SECONDS)

    write_api.write(bucket=bucket, record=point)
    client.close()


def query_latest(measurement: str, field: str, window: str = "-1h") -> list:
    client = get_client()
    query_api = client.query_api()
    bucket = os.getenv("INFLUXDB_BUCKET", "shipping-metrics")

    flux = f'''
    from(bucket: "{bucket}")
      |> range(start: {window})
      |> filter(fn: (r) => r._measurement == "{measurement}")
      |> filter(fn: (r) => r._field == "{field}")
      |> last()
    '''
    tables = query_api.query(flux)
    client.close()
    return [record.get_value() for table in tables for record in table.records]
