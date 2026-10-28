#!/usr/bin/env python3

import psycopg2
import json
import random
from datetime import datetime, timedelta, timezone
import asyncio
from pyauditor import AuditorClientBuilder, Record, Meta, Component, Score
from scipy.stats import truncnorm


CHUNK_SIZE = 100
start_id = 1
num_records = 1000
now = datetime.now()
start_time = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
mean = 8
std_dev = 15
min_val = 1
max_val = 23

a, b = (min_val - mean) / std_dev, (max_val - mean) / std_dev
normal = truncnorm(a, b, loc=mean, scale=std_dev)


def generate_stop_time_duration(normal_dist):
    return int(round(normal_dist.rvs()))


async def generate_mock_data(num_records, start_time):
    client = AuditorClientBuilder().address("127.0.0.1", 8000).timeout(10).build()

    print("Testing /health_check endpoint")
    health_check = await client.health_check()
    assert health_check

    print(f"Adding a {num_records} records to Auditor")

    mock_data = []
    for i in range(start_id,start_id+num_records):
        record_id = f"record-{i}"

        # Generate stop time
        hours_to_add = generate_stop_time_duration(normal)
        stop_time = start_time + timedelta(hours=hours_to_add)

        # Create the record
        record = Record(record_id, start_time)

        # --- Component 1: CPU ---
        cpu_amount = random.randint(1, 8)

        hepscore = [10, 12, 22, 28]

        cpu_score = Score("HEPscore23", random.choice(hepscore))
        
        cpu_component = Component("Cores", cpu_amount).with_score(cpu_score)

        wallclock_time = int((stop_time - start_time).total_seconds())
        
        # --- Component 2: MEM ---
        cpu_time =  (wallclock_time - random.randint(10, wallclock_time//50 )) if wallclock_time > 10 else wallclock_time - 5
        cpu_time_component = Component("TotalCPU", int(cpu_time))  # no scores
        
        wallclock_time_component = Component("WallclockTime", int(wallclock_time))

        # Add components to the record
        record = record.with_component(cpu_component)
        record = record.with_component(cpu_time_component)
        record = record.with_component(wallclock_time_component)


        # --- Meta ---
        group_id = random.choice(["lhcb", "cms", "ilc", "atlas"])
        site_id = random.choice(["site_id_1", "site_id_2", "site_id_3"])
        user_id = f"user-{i}"

        meta = Meta()
        meta = meta.insert("voms", ["/"+group_id])
        meta = meta.insert("group", [group_id])
        meta = meta.insert("site", [site_id])
        meta = meta.insert("user", [user_id])
        meta = meta.insert("headnode", ["GlobalJobId"])
        meta = meta.insert("infrastructure", ["grid"])

        # Attach meta
        record = record.with_meta(meta)

        # Set stop time
        record = record.with_stop_time(stop_time)

        mock_data.append(record)

        if len(mock_data) >= CHUNK_SIZE:
            await client.bulk_insert(mock_data)
            mock_data.clear()

        start_time = start_time + timedelta(seconds=60)
    return mock_data


async def main():
    await generate_mock_data(num_records,start_time)


if __name__ == "__main__":
    import time

    s = time.perf_counter()
    asyncio.run(main())
    elapsed = time.perf_counter() - s
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
