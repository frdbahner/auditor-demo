#!/usr/bin/env python3

import json
import time
import numpy as np
from datetime import datetime, timedelta, timezone
from scipy.stats import truncnorm
    
filename = '/var/lib/condor/spool/history'
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

def generate_mock_data(num_records, start_time, filename):
    # read hsitory template
    with open("history_job_tpl.txt", "r") as f:
        job_tlp=f.read()

    f = open(filename, "w")
    for i in range(1,num_records):
        hepscore23 = np.random.choice([18.4, 10.1, 26.5, 12.4 ])
        group_id = np.random.choice(["lhcb", "cms", "ilc", "atlas"])
        site_id = np.random.choice(["site_id_1", "site_id_2", "site_id_3"])
        user_nr = np.random.randint(1,10)
        node_nr = np.random.randint(1,8)
        user = f"user-{group_id}-{user_nr:03d}"
        record_id = f"htcondor-{i}"
        hours_to_add = generate_stop_time_duration(normal)
        stop_time = start_time + timedelta(hours=hours_to_add)
        runtime = hours_to_add * 3600
        hashname= 'testJob'+"_{:09d}".format(i)
        cluster_id = i 
        cpu_eff = np.random.uniform(0.7,1)
        f.write(job_tlp.format(int((stop_time-start_time).total_seconds()),
                               hashname,
                               user,
                               int(start_time.timestamp()),
                               int(stop_time.timestamp()),
                               cluster_id,
                               cpu_eff,
                               cpu_eff*int((stop_time-start_time).total_seconds()),
                               site_id,
                               hepscore23,
                               i,
                               group_id,
                               node_nr
                            )
                 )
        start_time = start_time + timedelta(seconds=60)
    f.close()
    
def main():
    generate_mock_data(num_records,start_time, filename)


if __name__ == "__main__":
    s = time.perf_counter()
    main()
    elapsed = time.perf_counter() - s
    print(f"{__file__} executed in {elapsed:0.2f} seconds.")
