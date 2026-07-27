# AUDITOR-demo

This is a mini tutorial on how to install an AUDITOR accounting pipeline from scratch using rpms.
The pipeline consists of an Slurm collector, an AUDITOR instance with a PostgreSQL database and an APEL plugin. 
All components can be installed together on a small VM. The demo here was set up on a VM with 1 vCore, 4GB RAM and 20 GB disc space on an Alma 9.8 OS (Olive Jaguar).
Please use 4GB or above RAM for testing purposes.

```
+-----------------------+           +---------------------+           +-------------------+
|   Slurm Collector     | --------> |      Auditor        | <-------- |   APEL Plugin     |
+-----------------------+           +---------------------+           +-------------------+
                                             |
                                             v
                                    +------------------+
                                    |   PostgreSQL     |
                                    +------------------+

````

## Prerequisits

### General Software 


Since the backend database of AUDITOR is postgresql, we need to have a current version installed and running.
Therefore we follow the documentation in [www.postgresql.org](https://www.postgresql.org/download/linux/redhat/)

For our setup alma9 on x86_64 we can use:
 
### Install DB
 
**Install the repository RPM:**
```
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm
```

 
**Disable the built-in PostgreSQL module:**
```
sudo dnf -qy module disable postgresql
```

 
**Install PostgreSQL:**
```
sudo dnf install -y postgresql17-server
```

 
**Initialize the database and enable automatic start:**
```
sudo /usr/pgsql-17/bin/postgresql-17-setup initdb
sudo systemctl enable postgresql-17
sudo systemctl start postgresql-17
```
 

 
Now we need to setup the password for the postgres user (here we set it to "password"):
 
```
sudo -u postgres psql
 
psql (17.4)
 
Type "help" for help.
 

 
postgres=# \password postgres
 
Enter new password for user "postgres": 
 
Enter it again: 
 
postgres=# 
 
```
## Prepare the DataBase

The AUDITOR repository contains the required db schema. There are two valid options to inject the db schema to the postgresql db.
Either with the psql command line interface as postgres user or by using sqlx, which ist a RUST based library (the second option is described in the documentation).

### Prepare the Data Base with psql cli

Create the auditor database in postgresql:

```
psql -h localhost -U postgres
Password for user postgres: 
psql (17.4)
Type "help" for help.

postgres=# CREATE DATABASE auditor;
CREATE DATABASE
postgres=# 

```
## Install AUDITOR Components from WLCG repo

Enable the WLCG repo and install the required components:
```
curl https://linuxsoft.cern.ch/wlcg/RPM-GPG-KEY-wlcg > /etc/pki/rpm-gpg/RPM-GPG-KEY-wlcg
yum-config-manager --add-repo https://linuxsoft.cern.ch/wlcg/wlcg-el9.repo
yum-config-manager --enable wlcg
```
```
### Install specific version for AUDITOR components
export AUDITOR_VERSION=0.10.1-1
dnf -y install auditor-${AUDITOR_VERSION} auditor_apel_plugin-${AUDITOR_VERSION} auditor-slurm-collector-${AUDITOR_VERSION} 
```

Now execute the two migration scripts. Note, that the location of these two scripts have changed between
versions, before v0.10, they were located in ```/opt/auditor```. Change below, if needed:

```

psql -h localhost -U postgres -d auditor -f /usr/share/auditor/migrations/20220322080444_create_accounting_table.sql
psql -h localhost -U postgres -d auditor -f /usr/share/auditor/migrations/20240503141800_convert_meta_component_to_jsonb.sql 
```

Afterwards the psql auditor db should look as follows:

```
psql -h localhost -U postgres -d auditor 
psql (17.4)
Type "help" for help.

auditor=# \d
                    List of relations
 Schema |           Name            |   Type   |  Owner   
--------+---------------------------+----------+----------
 public | auditor_accounting        | table    | postgres
 public | auditor_accounting_id_seq | sequence | postgres
(2 rows)

auditor=# 
```

## Configuration


### Configure AUDITOR main component
Adjust the auditor config file as follows, again, the location has changed with v0.10, adjust as necessary:
```
vi /etc/auditor/auditor.yml
```
with the following content:
```
application:
  addr:
    - 0.0.0.0
  port: 8000
database:
  host: "localhost"
  port: 5432
  username: "postgres"
  password: "password"
  database_name: "auditor"
  require_ssl: false
metrics:
  database:
    frequency: 30
    metrics:
      - RecordCount
      - RecordCountPerSite
      - RecordCountPerGroup
      - RecordCountPerUser
log_level: info
tls_config:
  use_tls: false
```
Now you can start the service with the following commands:
```
systemctl enable auditor.service
systemctl start auditor.service
```
You should see that the service is active and running:
```
systemctl status auditor.service
● auditor.service - AUDITOR
     Loaded: loaded (/etc/systemd/system/auditor.service; static)
     Active: active (running) since Tue 2025-03-11 15:09:32 UTC; 33s ago
       Docs: https://alu-schumacher.github.io/AUDITOR/
   Main PID: 91232 (auditor)
      Tasks: 4 (limit: 12148)
     Memory: 3.3M
        CPU: 35ms
systemctl status auditor.service
systemctl status auditor.service
     CGroup: /system.slice/auditor.service
             └─91232 /usr/bin/auditor /etc/auditor/config.yml

auditor[<pid>]: {"v":0,"name":"AUDITOR","msg":"starting service: \"actix-web-service-0.0.0.0:8000\", workers: 4, listed
...
```


### Configure AUDITOR APEL plugin
An example config file and a unit file are shipped with the rpm installation adjust the config yaml file, you might need to
adjust paths if you run an older version:
```
vim /etc/auditor/auditor_apel_plugin.yml
```
here I have used the example from the AUDITOR documentation
```
!Config
plugin:
  log_level: TRACE
  time_json_path: /opt/auditor_apel_plugin/time.json
  report_interval: 86400
  message_type: summaries

site:
  publish_since: 2024-01-01 06:00:00+00:00
  sites_to_report:
    SITE_A: ["site_id_1"]

messaging:
  host: msg.argo.grnet.gr
  port: 8443
  client_cert: /opt/auditor_apel_plugin/cert.crt
  client_key: /opt/auditor_apel_plugin/cert.key
  project: accounting
  topic: gLite-APEL
  timeout: 10
  retry: 3

auditor:
  ip: 127.0.0.1
  port: 8000
  timeout: 60
  site_meta_field: site_id
  use_tls: False

summary_fields:
  mandatory:
    NormalisedWallDuration: !NormalisedField
      score:
        name: hepscore23
        component_name: Cores
    CpuDuration: !ComponentField
      name: TotalCPU
    NormalisedCpuDuration: !NormalisedField
      base_value: !ComponentField
        name: TotalCPU
      score:
        name: hepscore23
        component_name: Cores
    VO: !MetaField
      name: group
    SubmitHost: !MetaField
      name: submithost
    Infrastructure: !ConstantField
      value: grid
    Processors: !ComponentField
      name: Cores
```
Normally you need to use a proper host certificate and key. For testing purposes here, we need to generate a key and certificate and place them where the APEL plugin is configured to look for them.
Change dir to `/opt/auditor_apel_plugin/` and execute the following commands:

Create a key:
```
openssl genrsa -out cert.key 2048
```
Create a certificate request:
```
openssl req -new -key cert.key -out cert.csr
```
Create a certificate:
```
openssl x509 -req -days 3650 -in cert.csr -signkey cert.key -out cert.crt
```


Start the APEL plugin service:
```
systemctl enable auditor_apel_plugin
systemctl start auditor_apel_plugin
```
Checking the status you should see:
```
systemctl status auditor_apel_plugin.service
● auditor_apel_plugin.service - APEL plugin for AUDITOR
     Loaded: loaded (/etc/systemd/system/auditor_apel_plugin.service; disabled; preset: disabled)
     Active: active (running) since Tue 2025-03-11 15:30:21 UTC; 3s ago
       Docs: https://alu-schumacher.github.io/AUDITOR/
   Main PID: 91729 (auditor-apel-pu)
      Tasks: 2 (limit: 12148)
     Memory: 27.0M
        CPU: 455ms
     CGroup: /system.slice/auditor_apel_plugin.service
             └─91729 //opt/auditor_apel_plugin/venv/bin/python /opt/auditor_apel_plugin/venv/bin/auditor-apel-publish --config /etc/auditor/auditor_apel_plugin.yml

```

### Install slurm as service in alma 9

1. Install Prerequisites
First, update the system and install the EPEL repository, which contains the Slurm packages.
```
sudo dnf update -y
sudo dnf install epel-release -y
```

2. Create slurm system user

```
sudo useradd -r -s /sbin/nologin slurm
```

2. Install Slurm Packages 
Install the core Slurm daemon, the control daemon, and the client utilities.

```
sudo dnf install slurm slurm-slurmctld slurm-slurmd slurm-slurmdbd -y
```

3. Creating file paths and permissions
```
sudo mkdir -p /var/spool/slurmctld /var/spool/slurmd
sudo mkdir -p /var/run/slurm /var/log/slurm
sudo mkdir -p /etc/slurm

sudo chown slurm:slurm /var/spool/slurmctld
sudo chown root:root   /var/spool/slurmd
sudo chown slurm:slurm /var/run/slurm /var/log/slurm
sudo chmod 755 /var/run/slurm /var/log/slurm
```


4. Replace the contents in /etc/slurm/slurm.conf with the following contents (replace your-hostname with the output of the hostname command)

```
sudo vim /etc/slurm/slurm.conf
```

Delete all the contents and replace with the config below

```
ClusterName=linux
SlurmctldHost=localhost

SlurmUser=slurm
SlurmdUser=root

StateSaveLocation=/var/spool/slurmctld
SlurmdSpoolDir=/var/spool/slurmd

SlurmctldPidFile=/var/run/slurm/slurmctld.pid
SlurmdPidFile=/var/run/slurm/slurmd.pid

SlurmctldPort=6817
SlurmdPort=6818

SlurmctldLogFile=/var/log/slurm/slurmctld.log
SlurmdLogFile=/var/log/slurm/slurmd.log

SlurmctldDebug=info
SlurmdDebug=info

SelectType=select/cons_tres
SelectTypeParameters=CR_CPU_Memory

SchedulerType=sched/backfill
ProctrackType=proctrack/linuxproc
SwitchType=switch/none

MpiDefault=none
ReturnToService=1


NodeName=localhost NodeHostname=localhost.localdomain \
    NodeAddr=127.0.0.1 CPUs=2 RealMemory=2000 State=UNKNOWN



PartitionName=normal Nodes=localhost Default=YES MaxTime=INFINITE State=UP
PartitionName=debug  Nodes=localhost MaxTime=01:00:00 State=UP
PartitionName=part1  Nodes=localhost State=UP
PartitionName=part2  Nodes=localhost State=UP
PartitionName=part3  Nodes=localhost State=UP
PartitionName=part4  Nodes=localhost State=UP


AccountingStorageType=accounting_storage/slurmdbd
AccountingStorageHost=localhost
AccountingStoragePort=6819
JobAcctGatherType=jobacct_gather/linux
JobAcctGatherFrequency=30
```

4. Important: confirm hostname -f on your machine actually match what you put in SlurmctldHost / NodeName / NodeHostname / Nodes / AccountingStorageHost

```
hostname
hostname -f
```

5. Installing munge

```
sudo dnf install munge munge-libs -y
```

```
sudo sh -c 'dd if=/dev/urandom bs=1 count=1024 > /etc/munge/munge.key'
sudo chmod 400 /etc/munge/munge.key
sudo chown munge:munge /etc/munge/munge.key
```

```
systemctl enable munge
systemctl restart munge
systemctl status munge
```

7. Installing mariadb for saact

```
sudo dnf install -y mariadb-server
sudo systemctl enable --now mariadb
```

```
sudo mysql -e "CREATE DATABASE slurm_acct_db;"
sudo mysql -e "CREATE USER 'slurm'@'localhost' IDENTIFIED BY 'slurm';"
sudo mysql -e "GRANT ALL PRIVILEGES ON slurm_acct_db.* TO 'slurm'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
```

Create a file at `/etc/slurm/slurmdbd.conf`

```
sudo vim /etc/slurm/slurmdbd.conf
```

```
AuthType=auth/munge
DbdHost=localhost

SlurmUser=slurm

StorageType=accounting_storage/mysql
StorageHost=localhost
StorageUser=slurm
StoragePass=slurm
StorageLoc=slurm_acct_db

PidFile=/run/slurm/slurmdbd.pid
LogFile=/var/log/slurm/slurmdbd.log
```

Create required directories for slurm

```
sudo chown slurm:slurm /etc/slurm/slurmdbd.conf
sudo chmod 600 /etc/slurm/slurmdbd.conf
```

Start services in the correct order
```
sudo systemctl enable --now slurmdbd
sudo systemctl status slurmdbd

sudo systemctl enable --now slurmctld
sudo systemctl status slurmctld

sudo systemctl enable --now slurmd
sudo systemctl status slurmd
```

Register cluster with accounting

```
sudo sacctmgr add cluster linux
sudo systemctl restart slurmctld
```

Check if everything works

```
sinfo
scontrol ping
```


Let's set the configuration for the slurm collector

```
sudo vim /etc/auditor/auditor-slurm-collector.yml
```

### Configure slurm collector
An example config file and a unit file are shipped with the rpm installation adjust the config yaml file, you might need to
adjust paths if you run an older version:

Use this configuration which is provided below for the demo


```
addr: "localhost"
port: 8000
record_prefix: "slurm"
job_filter:
  status:  # A list of acceptable job statuses
    - "completed"
sacct_frequency: 2 # in seconds
sender_frequency: 1 # in seconds
database_path: "/var/lib/auditor-slurm-collector/db.db"
earliest_datetime: "2023-09-15T12:00:00+00:00"
sites:
  - name: "site_id_1"
    only_if:
      key: "Partition"
      matches: "^part1$"
  - name: "site_id_2"
    only_if:
      key: "Partition"
      matches: "^part2$"
meta:
  - name: Comment
    key: "Comment"
    key_type: Json
    key_allow_empty: true
components:
  - name: "Cores"
    key: "NCPUS"
    scores:
      - name: "hepscore23"
        value: 10
        only_if:
          key: "Partition"
          matches: "^part1$"
      - name: "hepscore23"
        value: 12
        only_if:
          key: "Partition"
          matches: "^part2$"
  - name: "TotalCPU"
    key: "TotalCPU"
    key_type: Time
    only_if:
      key: "Partition"
      matches: "^part1$"
  - name: "UserCPU"
    key: "UserCPU"
    key_type: Time
    only_if:
      key: "Partition"
      matches: "^part1$"
  - name: "Memory"
    key: "ReqMem"
    key_type: IntegerMega
tls_config:
  use_tls: false
```

For versions 0.10.1 and 0.10.2 please do the following changes to the unit file of the slurm collector as well.

Put this config at `/usr/lib/systemd/system/auditor-slurm-collector.service`

```
[Unit]
Description=Slurm collector for AUDITOR
Documentation=https://alu-schumacher.github.io/AUDITOR/

[Install]
RequiredBy=multi-user.target

[Service]
Type=simple
User=auditor-slurm-collector
Group=auditor
StateDirectory=auditor-slurm-collector
StateDirectoryMode=0750
WorkingDirectory=/var/lib/auditor-slurm-collector
ExecStart=/usr/bin/auditor-slurm-collector /etc/auditor/auditor-slurm-collector.yml
Restart=on-failure
RestartSec=60
```

Now you can enable and start the slurm collector

```
systemctl daemon-reload
systemctl enable auditor-slurm-collector.service
systemctl start auditor-slurm-collector.service
```


We can submit some test jobs to slurm container using the `insert_mock_jobs.sh`. You can find this in the slurm-demo folder. This script will submit 20 test jobs to slurm.

you can clone the repository

```
git clone https://github.com/ALU-Schumacher/auditor-demo.git
```

```
cd auditor-demo/slurm-demo
```

Here, you can find the script for inserting mock jobs to slurm. Execute the script to insert the jobs/

```
./insert_mock_jobs.sh
```


You can see in the logs that the records are processed and sent to auditor.

```
journalctl -u auditor-slurm-collector -n 50 --no-pager
```


You can execute dry run of apel plugin to see the summary message of how the apel plugin 

Please change the month according to the current month

```
/opt/auditor_apel_plugin/venv/bin/python /opt/auditor_apel_plugin/venv/bin/auditor-apel-republish --config /etc/auditor/auditor_apel_plugin.yml -y 2026 -m 07 -s SITE_A  --dry-run
```

```
[2026-07-02 00:32:45] INFO     Total numbers reported by the plugin:
Site: SITE_A
Month: 7
Year: 2026
WallDuration: 20
CpuDuration: 153
NormalisedWallDuration: 200
NormalisedCpuDuration: 1530
NumberOfJobs: 20

```

The above is just a sample APEL summary generated out of mock jobs submitted to slurm.

## Accessing Data with python-auditor
### Access Data in ipython Session

Start ipython - you might need to install it with dnf:
```
ipython
```
Import required modules
```
import numpy as np
import datetime
import json
from pyauditor import AuditorClientBuilder, Value, Operator, QueryBuilder
```
Connect to AUDITOR

```
builder = AuditorClientBuilder()
builder = builder.address("127.0.0.1", 8000)
client = builder.build()
```
Create a proper query using the pyauditor QueryBuilder:
```
now = datetime.datetime.now()
start = datetime.datetime(now.year,now.month , 1, tzinfo=datetime.timezone.utc)
# Set the datetime value in Utc using Value object
value = Value.set_datetime(start)
query_string = QueryBuilder().with_stop_time(Operator().gte(value)).build()
query_string
```
```
Out[3]: 'stop_time[gte]=2025-05-01T00%3A00%3A00%2B00%3A00'
```
Execute the query:
```
records = await client.advanced_query(query_string)
```
Now you can have a look at the data (first 10 records):
```
records[:10]
```

```

Out[7]: 
[Record { record_id: "slurm-2", meta: Some(Meta({"site_id": ["site_id_1"], "user_id": ["root"], "group_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(6), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(5), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:04:59Z), stop_time: Some(2026-07-01T21:05:00Z), runtime: Some(1) },
 Record { record_id: "slurm-1", meta: Some(Meta({"user_id": ["root"], "site_id": ["site_id_1"], "group_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(9), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(4), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:04:59Z), stop_time: Some(2026-07-01T21:05:00Z), runtime: Some(1) },
 Record { record_id: "slurm-3", meta: Some(Meta({"site_id": ["site_id_1"], "group_id": ["root"], "user_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(7), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(3), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:05:00Z), stop_time: Some(2026-07-01T21:05:01Z), runtime: Some(1) },
 Record { record_id: "slurm-4", meta: Some(Meta({"site_id": ["site_id_1"], "group_id": ["root"], "user_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(5), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(4), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:05:00Z), stop_time: Some(2026-07-01T21:05:01Z), runtime: Some(1) },
 Record { record_id: "slurm-5", meta: Some(Meta({"site_id": ["site_id_1"], "user_id": ["root"], "group_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(6), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(4), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:05:03Z), stop_time: Some(2026-07-01T21:05:04Z), runtime: Some(1) },
 Record { record_id: "slurm-6", meta: Some(Meta({"group_id": ["root"], "site_id": ["site_id_1"], "user_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(7), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(3), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:05:03Z), stop_time: Some(2026-07-01T21:05:04Z), runtime: Some(1) },
 Record { record_id: "slurm-7", meta: Some(Meta({"user_id": ["root"], "site_id": ["site_id_1"], "group_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(7), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(2), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:05:06Z), stop_time: Some(2026-07-01T21:05:07Z), runtime: Some(1) },
 Record { record_id: "slurm-8", meta: Some(Meta({"user_id": ["root"], "group_id": ["root"], "site_id": ["site_id_1"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(8), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(2), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:05:06Z), stop_time: Some(2026-07-01T21:05:07Z), runtime: Some(1) },
 Record { record_id: "slurm-10", meta: Some(Meta({"site_id": ["site_id_1"], "user_id": ["root"], "group_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(7), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(2), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:05:09Z), stop_time: Some(2026-07-01T21:05:10Z), runtime: Some(1) },
 Record { record_id: "slurm-9", meta: Some(Meta({"user_id": ["root"], "site_id": ["site_id_1"], "group_id": ["root"]})), components: Some([Component { name: ValidName("Cores"), amount: ValidAmount(1), scores: [Score { name: ValidName("hepscore23"), value: ValidValue(10.0) }] }, Component { name: ValidName("TotalCPU"), amount: ValidAmount(7), scores: [] }, Component { name: ValidName("UserCPU"), amount: ValidAmount(2), scores: [] }, Component { name: ValidName("Memory"), amount: ValidAmount(10), scores: [] }]), start_time: Some(2026-07-01T21:05:09Z), stop_time: Some(2026-07-01T21:05:10Z), runtime: Some(1) }]
```
If you want to use the data for further analysis, you can transform the records it a json-object
```
# transform record into json
json.loads(records[0].to_json())
```
```
Out[8]: 
{'components': [{'amount': 1,
   'name': 'Cores',
   'scores': [{'name': 'hepscore23', 'value': 10.0}]},
  {'amount': 6, 'name': 'TotalCPU', 'scores': []},
  {'amount': 5, 'name': 'UserCPU', 'scores': []},
  {'amount': 10, 'name': 'Memory', 'scores': []}],
 'meta': {'group_id': ['root'], 'site_id': ['site_id_1'], 'user_id': ['root']},
 'record_id': 'slurm-2',
 'runtime': 1,
 'start_time': '2026-07-01T21:04:59Z',
 'stop_time': '2026-07-01T21:05:00Z'}
```
```
print(json.dumps(json.loads(records[13].to_json()),indent=3))
```
```
{
   "components": [
      {
         "amount": 1,
         "name": "Cores",
         "scores": [
            {
               "name": "hepscore23",
               "value": 10.0
            }
         ]
      },
      {
         "amount": 9,
         "name": "TotalCPU",
         "scores": []
      },
      {
         "amount": 0,
         "name": "UserCPU",
         "scores": []
      },
      {
         "amount": 10,
         "name": "Memory",
         "scores": []
      }
   ],
   "meta": {
      "group_id": [
         "root"
      ],
      "site_id": [
         "site_id_1"
      ],
      "user_id": [
         "root"
      ]
   },
   "record_id": "slurm-13",
   "runtime": 1,
   "start_time": "2026-07-01T21:05:15Z",
   "stop_time": "2026-07-01T21:05:16Z"
}
```
