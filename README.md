# AUDITOR-demo

This is a mini tutorial on how to install an AUDITOR accounting pipeline from scratch using rpms.
The pipeline consists of an HTCondor collector, an AUDITOR instance with a PostgreSQL database and an APEL plugin. 
All components can be installed together on a small VM. The demo here was set up on a VM with 1 vCore, 2GB RAM and 20 GB disc space on an Alma 9.5 OS.  

```
+-----------------------+           +---------------------+           +-------------------+
|   HTCondor Collector  | --------> |      Auditor        | <-------- |   APEL Plugin     |
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
dnf -y install auditor-${AUDITOR_VERSION} auditor_apel_plugin-${AUDITOR_VERSION} auditor_htcondor_collector-${AUDITOR_VERSION}
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
     CGroup: /system.slice/auditor.service
             └─91232 /usr/bin/auditor /etc/auditor/config.yml

auditor[<pid>]: {"v":0,"name":"AUDITOR","msg":"starting service: \"actix-web-service-0.0.0.0:8000\", workers: 4, listed
...
```

### Configure AUDITOR HTCondor collector
An example config file and a unit file are shipped with the rpm installation adjust the config yaml file,
with /opt/auditor_htcondor_collector as its path for pre-0.10 versions:
Attention! replace: <REPLACE_WITH_HOSTHAME> with your fully qualified hostname!
```
vim /etc/auditor/auditor_htcondor_collector.yml 
```
here I have used the example from the AUDITOR documentation
```
addr: localhost
port: 8000
timeout: 10
state_db: htcondor_history_state.db
record_prefix: htcondor
interval: 900 # 15 minutes
pool: <REPLACE_WITH_HOSTHAME>
log_level: INFO
schedd_names:
  - <REPLACE_WITH_HOSTHAME>
job_status: # See https://htcondor-wiki.cs.wisc.edu/index.cgi/wiki?p=MagicNumbers
  - 3 # Removed
  - 4 # Completed

meta:
  user:
    key: Owner
    matches: ^(.+)$
  group:
    key: "x509UserProxyVOName"
    matches: ^(.+)$
  submithost:
    key: "GlobalJobId"
    matches: ^(.*?)#  # As this regex contains a group, the value for 'submithost' is set to the matching group.

  # For `site` the first match is used.
  site:
    - name: "site_id_1"  # This entry
      key: "LastRemoteHost"
      matches: ^slot.+@site_id_1.+$
    - name: "site_id_2"  # This entry
      key: "LastRemoteHost"
      matches: ^slot.+@site_id_2.+$
    - name: "site_id_3"  # This entry
      key: "LastRemoteHost"
      matches: ^slot.+@site_id_3.+$
    - name: "UNDEF"  # If no match is found, site is set to "UNDEF"


components:
  - name: "Cores"
    key: "CpusProvisioned"
    scores:
      - name: "hepscore23"
        key: "MachineAttrHEPscore230"
  - name: "RequestedMemory"
    key: "RequestMemory"
  - name: "UsedMemory"
    key: "ResidentSetSize_RAW"
  - name: "CPUTime"
    key: "TotalCpuTime"
  - name: "DiskUsage"
    key: "DiskUsage_RAW"

tls_config:
  use_tls: False

```
Fix permissions on where the database will be created:
```
chmod 777 /opt/auditor_htcondor_collector
```
Start the htcondor collector service:
```
systemctl enable auditor_htcondor_collector.service 
systemctl start auditor_htcondor_collector.service 
```
Checking the status you should see:
```
 systemctl status auditor_htcondor_collector.service 
● auditor_htcondor_collector.service - HTCondor collector for AUDITOR
     Loaded: loaded (/etc/systemd/system/auditor_htcondor_collector.service; disabled; preset: disabled)
     Active: active (running) since Tue 2025-03-11 15:16:34 UTC; 2s ago
       Docs: https://alu-schumacher.github.io/AUDITOR/
   Main PID: 91396 (auditor-htcondo)
      Tasks: 1 (limit: 12148)
     Memory: 7.7M
        CPU: 85ms
     CGroup: /system.slice/auditor_htcondor_collector.service
             └─91396 //opt/auditor_htcondor_collector/venv/bin/python /opt/auditor_htcondor_collector/venv/bin/auditor-htcondor-collector --config /opt/auditor_htcondor_collector/auditor_htcondor_collector.yml

Mar 11 15:16:34 auditor-demo.novalocal systemd[1]: Started HTCondor collector for AUDITOR.
```
later on you will find the following errors:
```
auditor.collectors.htcondor - WARNING  - Could not find last job id for schedd 'schedd1.example.com' and recor>
auditor.collectors.htcondor - ERROR    - Error querying HTCondor history:
b'Unable to locate remote schedd (name=schedd1.example.com, pool=htcondor.example.com).\n'
auditor.collectors.htcondor - INFO     - Added 0 records.
```
This is expected: We have no HTCondor installed and running and therefore we cannot collect data atm. We see that in a later step.


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
  log_level: INFO
  time_json_path: /opt/auditor_apel_plugin/time.json
  report_interval: 86400
  message_type: summaries

site:
  publish_since: 2024-01-01 06:00:00+00:00
  sites_to_report:
    SITE_A: ["site_id_1", "site_id_2"]
    SITE_B: ["site_id_3"]

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
  site_meta_field: site
  use_tls: False

summary_fields:
  mandatory:
    NormalisedWallDuration: !NormalisedField
      score:
        name: hepscore23
        component_name: Cores
    CpuDuration: !ComponentField
      name: CPUTime
    NormalisedCpuDuration: !NormalisedField
      base_value: !ComponentField
        name: CPUTime
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
             └─91729 //opt/auditor_apel_plugin/venv/bin/python /opt/auditor_apel_plugin/venv/bin/auditor-apel-publish --config /opt/auditor/auditor_apel_plugin.yml

Started APEL plugin for AUDITOR.
INFO     Enough time since last report, create new report (//opt/auditor_apel_plugin/venv/lib/python3.9/site-packages/au>
INFO     Getting records for site SITE_A with site_ids: ['site_id_1', 'site_id_2'] (//opt/auditor_apel_plugin/venv/lib/p>
INFO     No new records for SITE_A (//opt/auditor_apel_plugin/venv/lib/python3.9/site-packages/auditor_apel_plugin/publi>
INFO     Getting records for site SITE_B with site_ids: ['site_id_3'] (//opt/auditor_apel_plugin/venv/lib/python3.9/site>
INFO     No new records for SITE_B (//opt/auditor_apel_plugin/venv/lib/python3.9/site-packages/auditor_apel_plugin/publi>
INFO     Next report scheduled for 2025-03-12 15:30:22.034452 (//opt/auditor_apel_plugin/venv/lib/python3.9/site-package>
```
This is again expected, because we do not have any data and the sites `['site_id_1', 'site_id_2']` do not exist.


## Adding some data to our sandbox

First we fill the condor_history withg some toy data. Therefore we need to install htcondor

### Install htcondor

```
sudo dnf config-manager --set-enabled crb
yum install https://research.cs.wisc.edu/htcondor/repo/24.x/htcondor-release-current.el9.noarch.rpm
yum install condor
```

#### minimal configuration

add all daemons to the config file:
/etc/condor/condor_config.local
```
DAEMON_LIST = MASTER, SCHEDD, COLLECTOR, STARTD

ALLOW_READ = *
ALLOW_WRITE = *

NETWORK_INTERFACE = 0.0.0.0
```
add the IP-Address of you test VM and the proper port to the common config file

/etc/condor/config.d/00-common.conf 
```
CONDOR_HOST = <replace with your IP adress>
COLLECTOR_PORT = 9618
```
start condor with:
```
 sudo systemctl start condor
 sudo systemctl enable condor 
```
check if condor is running:
```
 condor_status
```
if not, restart with `condor_restart` and check again.


### Install pyauditor and other modules - required to create the mock data

Now we can download this git repo with the mock_history_insertion.py script.
You might need to install git via dnf.
```
git clone https://github.com/ALU-Schumacher/auditor-demo.git
```

Create a python venv e.g. in the user home dir (python might be called python3):
```
cd 
python -m venv .venv
source .venv/bin/activate
```
Then you can install the requirements from the requirements.txt of this repo
```
pip install -r requirements.txt
```
Now we can create the pseudo-condor data:
```
python auditor-demo\mock_history_insertion.py
```
afterwards we can deactivate the env again:
```
deactivate
```

We can check if that was successfull with the `condor_history` command:
```
condor_history 
 ID     OWNER          SUBMITTED   RUN_TIME     ST COMPLETED   CMD            
999.0   user-ilc-005    3/10 03:48   0+03:00:00 C   5/1  19:38 /ce_home/arc/sessiondir/testJob_000000999/condorjob.sh 
998.0   user-cms-001    3/10 03:48   0+18:00:00 C   5/2  10:37 /ce_home/arc/sessiondir/testJob_000000998/condorjob.sh 
997.0   user-ilc-002    3/10 03:48   0+08:00:00 C   5/2  00:36 /ce_home/arc/sessiondir/testJob_000000997/condorjob.sh 
996.0   user-atlas-006  3/10 03:48   0+08:00:00 C   5/2  00:35 /ce_home/arc/sessiondir/testJob_000000996/condorjob.sh 
995.0   user-cms-005    3/10 03:48   0+10:00:00 C   5/2  02:34 /ce_home/arc/sessiondir/testJob_000000995/condorjob.sh 
994.0   user-cms-008    3/10 03:48   0+07:00:00 C   5/1  23:33 /ce_home/arc/sessiondir/testJob_000000994/condorjob.sh 
993.0   user-ilc-006    3/10 03:48   0+16:00:00 C   5/2  08:32 /ce_home/arc/sessiondir/testJob_000000993/condorjob.sh 
...
```
Nice! Data is in condor. Now we can run the condor-collector (or wait until the service comes around).

### Run AUDITOR-HTCondor collector 

Here we are impatient, we  want to execute the collector manually.
Therefore we can call:
```
/opt/auditor_htcondor_collector/venv/bin/python /opt/auditor_htcondor_collector/venv/bin/auditor-htcondor-collector --config /etc/auditor/auditor_htcondor_collector.yml --job-id  0.0
```
you should see something like:
```
/opt/auditor_htcondor_collector/venv/bin/python /opt/auditor_htcondor_collector/venv/bin/auditor-htcondor-collector --config /etc/auditor/auditor_htcondor_collector.yml --job-id  0.0


2025-07-07 13:39:42,890 - auditor.collectors.htcondor - INFO     - Using AUDITOR client at localhost:8000.
2025-07-07 13:39:42,890 - auditor.collectors.htcondor - INFO     - Using timeout of 10 seconds for AUDITOR client.
2025-07-07 13:39:42,892 - auditor.collectors.htcondor - INFO     - Starting collector run.
2025-07-07 13:39:42,892 - auditor.collectors.htcondor - INFO     - Collecting jobs for schedd 'auditor-demo.novalocal'.
2025-07-07 13:39:49,813 - auditor.collectors.htcondor - INFO     - Added 999 records.
2025-07-07 13:39:49,816 - auditor.collectors.htcondor - INFO     - Collector run finished.

```
Just interrupt the command with `Strg+c`.

In order to test the entire pipeline, you can run the APEL-plugin in dry-run mode:

```
 /opt/auditor_apel_plugin/venv/bin/python /opt/auditor_apel_plugin/venv/bin/auditor-apel-publish --config /etc/auditor/auditor_apel_plugin.yml --dry-run
```
#### Wipe the DB and re-un the AUDITOR-HTCondor collector 

If we want to wipe the database for another run of the collector, we need to execute the following commands

```
psql -h localhost -U postgres -d auditor

auditor=# DELETE FROM auditor_accounting;
```
and remove the check point of the collector:
```
rm /opt/auditor_htcondor_collector/htcondor_history_state.db 
```
The we can execute the collector command again.


### Fill AUDITOR with toy data

If we want to skip the part of installing HTCondor and we just want to mock the APEL plugin step, we can use the other mocking skript: `mock_records_insertion.py`
Wipe the DB as described above and execute the `mock_records_insertion.py ` in our venv:

Now you can execute the mock_records_insertion.py script, which adds 1k records with random data into your AUDITOR db.
The script is available in this repo. execute the following command in the directory where you have downloaded this repo:
```
 python mock_records_insertion.py
```
If you now run the auditor-apel-publish command with the --dry-run option:
```
/opt/auditor_apel_plugin/venv/bin/python /opt/auditor_apel_plugin/venv/bin/auditor-apel-publish --config /opt/auditor_apel_plugin/auditor_apel_plugin.yml  --dry-run 
```

You should get a summary output as follows:
```
[2025-04-30 15:31:21] INFO     Starting one-shot dry-run, nothing will be sent to APEL! (/opt/auditor_apel_plugin/venv/lib/python3.9/site-packages/auditor_apel_plugin/publish.py at line 47)
[2025-04-30 15:31:21] INFO     Getting records for site SITE_A with site_ids: ['site_id_1', 'site_id_2'] (/opt/auditor_apel_plugin/venv/lib/python3.9/site-packages/auditor_apel_plugin/core.py at line 45)
[2025-04-30 15:31:22] INFO     Total numbers reported by the plugin:
Site: SITE_A
Month: 5
Year: 2025
NumberOfJobs: 6731
WallDuration: 276951600
NormalisedWallDuration: 5013237600
CpuDuration: 274186957
NormalisedCpuDuration: 4963289834

 (/opt/auditor_apel_plugin/venv/lib/python3.9/site-packages/auditor_apel_plugin/publish.py at line 134)
[2025-04-30 15:31:22] INFO     Getting records for site SITE_B with site_ids: ['site_id_3'] (/opt/auditor_apel_plugin/venv/lib/python3.9/site-packages/auditor_apel_plugin/core.py at line 45)
[2025-04-30 15:31:22] INFO     Total numbers reported by the plugin:
Site: SITE_B
Month: 5
Year: 2025
NumberOfJobs: 3269
WallDuration: 134074800
NormalisedWallDuration: 2406434400
CpuDuration: 132726130
NormalisedCpuDuration: 2382405970

```

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
Out[5]: 
[Record { record_id: "record-13", meta: Some(Meta({"group_id": ["group_1"], "site_id": ["site_3"], "user_id": ["user-13"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(16), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(3072), scores: [] }]), start_time: Some(2025-05-01T00:13:00Z), stop_time: Some(2025-05-01T01:13:00Z), runtime: Some(3600) },
 Record { record_id: "record-49", meta: Some(Meta({"group_id": ["group_3"], "user_id": ["user-49"], "site_id": ["site_2"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(4), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(4096), scores: [] }]), start_time: Some(2025-05-01T00:49:00Z), stop_time: Some(2025-05-01T01:49:00Z), runtime: Some(3600) },
 Record { record_id: "record-60", meta: Some(Meta({"group_id": ["group_3"], "site_id": ["site_2"], "user_id": ["user-60"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(5), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(2048), scores: [] }]), start_time: Some(2025-05-01T01:00:00Z), stop_time: Some(2025-05-01T02:00:00Z), runtime: Some(3600) },
 Record { record_id: "record-20", meta: Some(Meta({"group_id": ["group_1"], "user_id": ["user-20"], "site_id": ["site_1"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(7), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(6144), scores: [] }]), start_time: Some(2025-05-01T00:20:00Z), stop_time: Some(2025-05-01T02:20:00Z), runtime: Some(7200) },
 Record { record_id: "record-48", meta: Some(Meta({"site_id": ["site_1"], "group_id": ["group_1"], "user_id": ["user-48"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(10), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(4096), scores: [] }]), start_time: Some(2025-05-01T00:48:00Z), stop_time: Some(2025-05-01T02:48:00Z), runtime: Some(7200) },
 Record { record_id: "record-3", meta: Some(Meta({"group_id": ["group_3"], "site_id": ["site_3"], "user_id": ["user-3"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(15), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(6144), scores: [] }]), start_time: Some(2025-05-01T00:03:00Z), stop_time: Some(2025-05-01T03:03:00Z), runtime: Some(10800) },
 Record { record_id: "record-9", meta: Some(Meta({"user_id": ["user-9"], "group_id": ["group_3"], "site_id": ["site_2"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(8), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(4096), scores: [] }]), start_time: Some(2025-05-01T00:09:00Z), stop_time: Some(2025-05-01T03:09:00Z), runtime: Some(10800) },
 Record { record_id: "record-74", meta: Some(Meta({"group_id": ["group_1"], "site_id": ["site_3"], "user_id": ["user-74"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(6), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(2048), scores: [] }]), start_time: Some(2025-05-01T01:14:00Z), stop_time: Some(2025-05-01T03:14:00Z), runtime: Some(7200) },
 Record { record_id: "record-39", meta: Some(Meta({"user_id": ["user-39"], "site_id": ["site_3"], "group_id": ["group_1"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(9), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(3072), scores: [] }]), start_time: Some(2025-05-01T00:39:00Z), stop_time: Some(2025-05-01T03:39:00Z), runtime: Some(10800) },
 Record { record_id: "record-162", meta: Some(Meta({"site_id": ["site_1"], "user_id": ["user-162"], "group_id": ["group_3"]})), components: Some([Component { name: ValidName("cpu"), amount: ValidAmount(14), scores: [Score { name: ValidName("hepspec23"), value: ValidValue(10.0) }] }, Component { name: ValidName("mem"), amount: ValidAmount(7168), scores: [] }]), start_time: Some(2025-05-01T02:42:00Z), stop_time: Some(2025-05-01T03:42:00Z), runtime: Some(3600) }]
```
If you want to use the data for further analysis, you can transform the records it a json-object
```
# transform record into json
json.loads(records[0].to_json())
```
```
Out[6]: 
{'components': [{'amount': 16,
   'name': 'cpu',
   'scores': [{'name': 'hepspec23', 'value': 10.0}]},
  {'amount': 3072, 'name': 'mem', 'scores': []}],
 'meta': {'group_id': ['group_1'],
  'site_id': ['site_3'],
  'user_id': ['user-13']},
 'record_id': 'record-13',
 'runtime': 3600,
 'start_time': '2025-05-01T00:13:00Z',
 'stop_time': '2025-05-01T01:13:00Z'}
```
```
print(json.dumps(json.loads(records[13].to_json()),indent=3))
```
```
{
   "components": [
      {
         "amount": 14,
         "name": "cpu",
         "scores": [
            {
               "name": "hepspec23",
               "value": 10.0
            }
         ]
      },
      {
         "amount": 2048,
         "name": "mem",
         "scores": []
      }
   ],
   "meta": {
      "group_id": [
         "group_2"
      ],
      "site_id": [
         "site_3"
      ],
      "user_id": [
         "user-68"
      ]
   },
   "record_id": "record-68",
   "runtime": 10800,
   "start_time": "2025-05-01T01:08:00Z",
   "stop_time": "2025-05-01T04:08:00Z"
}
```
