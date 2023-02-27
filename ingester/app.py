"""
Ingester module that converts Apple Health export zip file
into influx db datapoints
"""
import os
import re
import time
import xml.etree.ElementTree as etree
from shutil import unpack_archive

from dateutil.parser import parse
from influxdb import InfluxDBClient

client = InfluxDBClient('influx', 8086, database='health')
PREFIX_RE = re.compile('HK.*Identifier(.+)$')
export_path = "/export.xml"


def try_to_float(v):
    """convert v to float or 0"""
    try:
        return float(v)
    except ValueError:
        try:
            return int(v)
        except:
            return 0


def format_record(record):
    """format a export health xml record for influx"""
    m = re.match(PREFIX_RE, record.get("type"))
    measurement = m.group(1) if m else record.get("type")
    value = try_to_float(record.get("value", 1))
    unit = record.get("unit", "unit")
    date = int(parse(record.get("startDate")).timestamp())

    return {
        "measurement": measurement,
        "tags": {
            "unit": unit
        },
        "time": date,
        "fields": {
            "value": value
        }
    }


def process_health_data():
    formatted_records = []
    total_count = 0
    for _, elem in etree.iterparse(export_path):
        if elem.tag == "Record":
            f = format_record(elem)
            formatted_records.append(f)
            del elem

            # batch push every 10000
            if len(formatted_records) == 10000:
                total_count += 10000
                client.write_points(formatted_records, time_precision="s")
                del formatted_records
                formatted_records = []
                print("inserted", total_count, "records")

    # push the rest
    client.write_points(formatted_records, time_precision="s")
    print("Total number of records:", total_count+len(formatted_records))


if __name__ == "__main__":
    while True:
        try:
            client.ping()
            client.drop_database("health")
            client.create_database("health")
            print('influx is ready')
            break
        except:
            print("waiting on influx to be ready..")
            time.sleep(1)

    process_health_data()
    print('All done ! You can now check grafana.')
