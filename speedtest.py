"""
MIT License

Copyright (c) 2021 dbrennand

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from loguru import logger
import os
import influxdb
import subprocess
import json
import time

__version__ = "0.0.2"

logger.debug(f"Starting speedtest-grafana version: {__version__}.")

# Retrieve environment variables
# If not found, use defaults

INFLUXDB_HOST = os.environ.get("INFLUXDB_HOST", "influxdb")
INFLUXDB_PORT = int(os.environ.get("INFLUXDB_PORT", 8086))
INFLUXDB_USER = os.environ.get("INFLUXDB_USER", "root")
INFLUXDB_USER_PASSWORD = os.environ.get("INFLUXDB_USER_PASSWORD", "root")
INFLUXDB_DB = os.environ.get("INFLUXDB_DB", "internet_speed")

# Default interval is 30 minutes (30 x 60s)
SPEEDTEST_INTERVAL = int(os.environ.get("SPEEDTEST_INTERVAL", 1800))

# Connect to InfluxDB
logger.debug(
    f"Connecting to InfluxDB using host: {INFLUXDB_HOST}, port: {INFLUXDB_PORT}, username: {INFLUXDB_USER}, database name: {INFLUXDB_DB}."
)
influx = influxdb.InfluxDBClient(
    host=INFLUXDB_HOST,
    port=INFLUXDB_PORT,
    username=INFLUXDB_USER,
    password=INFLUXDB_USER_PASSWORD,
    database=INFLUXDB_DB,
    retries=0,
)

# Run the speedtest using the librespeed/speedtest-cli on an interval
# remove --server parameter, since server selection automated by ping based    
while True:
    logger.debug(
        f"Running speedtest with auto server selection based on ping and telemetry disabled."
    )
        
    result = subprocess.run(
        [
            "/librespeed",
            "--telemetry-level",
            "disabled",
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    # Check if speedtest failed
    if result.returncode != 0:
        # Speedtest failed
        # CLI errors go to stdout
        logger.debug(
            f"Speedtest failed with exit code: {result.returncode}.\nError: {result.stdout}"
        )
    else:
        # Speedtest succeeded
        logger.debug(f"Speedtest succeeded. Parsing JSON results.")
        # Parse JSON results
        try:
            json_result = json.loads(result.stdout)
        except json.decoder.JSONDecodeError as err:
            logger.debug(f"Failed to parse JSON results.\nError: {err}")
            logger.debug(f"Sleeping for {SPEEDTEST_INTERVAL} seconds.")
            # Sleep on the specified interval
            time.sleep(SPEEDTEST_INTERVAL)
            continue
        # Create InfluxDB JSON body
        json_body = [
            {
                "measurement": "internet_speed",
                "tags": {
                    "server_name": json_result[0]["server"]["name"],
                    "server_url": json_result[0]["server"]["url"],
                    "ip": json_result[0]["client"]["ip"],
                    "hostname": json_result[0]["client"]["hostname"],
                    "region": json_result[0]["client"]["region"],
                    "city": json_result[0]["client"]["city"],
                    "country": json_result[0]["client"]["country"],
                    "org": json_result[0]["client"]["org"],
                    "timezone": json_result[0]["client"]["timezone"],
                },
                "time": json_result[0]["timestamp"],
                "fields": {
                    "bytes_sent": json_result[0]["bytes_sent"],
                    "bytes_received": json_result[0]["bytes_received"],
                    "ping": float(json_result[0]["ping"]),
                    "jitter": float(json_result[0]["jitter"]),
                    "upload": float(json_result[0]["upload"]),
                    "download": float(json_result[0]["download"]),
                },
            }
        ]
        # Write results to InfluxDB
        logger.debug(
            f"Writing results to InfluxDB database: {INFLUXDB_DB}.\nResults: {json_body}"
        )
        influx.write_points(json_body)
    logger.debug(f"Sleeping for {SPEEDTEST_INTERVAL} seconds.")
    # Sleep on the specified interval
    time.sleep(SPEEDTEST_INTERVAL)
