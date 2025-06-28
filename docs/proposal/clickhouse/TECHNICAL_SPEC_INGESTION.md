# Technical Specification: Tor Descriptor Data Ingestion

## Overview

This document specifies the technical implementation for ingesting 18+ years of Tor network descriptor data from collector.torproject.org into ClickHouse for historical analytics.

## Data Sources and Formats

### 1. Consensus Documents
**URL Pattern**: `http://collector.torproject.org/archive/relay-descriptors/consensuses/`
**Format**: Directory structure by year-month with compressed tarballs
**Content Structure**:
```
network-status-version 3
vote-status consensus
consensus-method 28
valid-after 2025-01-27 07:00:00
fresh-until 2025-01-27 08:00:00
valid-until 2025-01-27 10:00:00
voting-delay 300 300
client-versions 0.3.5.17,0.4.5.16,0.4.6.13,0.4.7.13,0.4.8.12
server-versions 0.3.5.17,0.4.5.16,0.4.6.13,0.4.7.13,0.4.8.12
known-flags Authority Exit Fast Guard HSDir NoEdConsensus Running Stable V2Dir Valid
params CircuitPriorityHalflifeMsec=30000 DoSCircuitCreationEnabled=1
dir-source moria1 9695DFC35FFEB861329B9F1AB04C46397020CE31
r seele AAoQ1DAR6kkoo19hBAX5K0QztNw 2025-01-27 06:15:48 1.2.3.4 9001 0
s Running Stable V2Dir Valid
v Tor 0.4.8.12
pr Conflux=1 Cons=1-2 Desc=1-2 DirCache=1-2
w Bandwidth=20 Measured=30
p reject 1-65535
```

### 2. Server Descriptors
**URL Pattern**: `http://collector.torproject.org/archive/relay-descriptors/server-descriptors/`
**Content Structure**:
```
@type server-descriptor 1.0
router seele 1.2.3.4 9001 0 0
platform Tor 0.4.8.12 on Linux
protocols Link 1-5 Circuit 1
published 2025-01-27 06:15:48
fingerprint 000A 10D4 3011 EA49 28A3 5F61 0405 F92B 443B B4DC
uptime 86400
bandwidth 20971520 20971520 20971520
extra-info-digest 1234567890ABCDEF
contact tor-operator@example.com
```

### 3. Extra Info Descriptors
**URL Pattern**: `http://collector.torproject.org/archive/relay-descriptors/extra-infos/`
**Content Structure**:
```
@type extra-info 1.0
extra-info seele 000A10D43011EA4928A35F610405F92B443BB4DC
published 2025-01-27 06:15:48
geoip-db-digest 1234567890ABCDEF
geoip6-db-digest FEDCBA0987654321
transport obfs4 1.2.3.4:1234
dirreq-stats-end 2025-01-27 06:00:00 (86400 s)
dirreq-v3-ips us=1024,de=512,fr=256
dirreq-v3-reqs us=2048,de=1024,fr=512
```

### 4. Bandwidth Files
**URL Pattern**: `http://collector.torproject.org/recent/relay-descriptors/bandwidths/`
**Content Structure**:
```
1706346000
node_id=$000A10D43011EA4928A35F610405F92B443BB4DC bw=25600 nick=seele
node_id=$111B20D43011EA4928A35F610405F92B443BB4DC bw=51200 nick=relay2
```

## ETL Pipeline Architecture

### Phase 1: Historical Data Backfill

```python
# Main ingestion orchestrator
class TorDataIngester:
    def __init__(self, clickhouse_client, start_date, end_date):
        self.ch = clickhouse_client
        self.collector_base = "http://collector.torproject.org/archive"
        self.start_date = start_date
        self.end_date = end_date
    
    def ingest_historical_data(self):
        """Main entry point for historical ingestion"""
        # 1. Download monthly archives
        for year_month in self.get_year_months():
            self.download_monthly_archive(year_month)
            self.process_monthly_data(year_month)
            self.cleanup_temporary_files(year_month)
    
    def parse_consensus_entry(self, entry_lines):
        """Parse a single relay entry from consensus"""
        data = {
            'nickname': '',
            'fingerprint': '',
            'published': None,
            'ip': '',
            'or_port': 0,
            'dir_port': 0,
            'flags': [],
            'version': '',
            'bandwidth': 0,
            'measured': 0
        }
        
        for line in entry_lines:
            if line.startswith('r '):
                parts = line.split()
                data['nickname'] = parts[1]
                data['fingerprint'] = self.decode_fingerprint(parts[2])
                data['published'] = parts[3] + ' ' + parts[4]
                data['ip'] = parts[5]
                data['or_port'] = int(parts[6])
                data['dir_port'] = int(parts[7])
            elif line.startswith('s '):
                data['flags'] = line[2:].split()
            elif line.startswith('v '):
                data['version'] = line[2:].strip()
            elif line.startswith('w '):
                weights = self.parse_weights(line[2:])
                data['bandwidth'] = weights.get('Bandwidth', 0)
                data['measured'] = weights.get('Measured', 0)
        
        return data
```

### Phase 2: Real-time Ingestion

```python
class RealTimeConsensusIngester:
    def __init__(self, clickhouse_client):
        self.ch = clickhouse_client
        self.last_consensus = None
    
    async def monitor_consensus(self):
        """Monitor for new consensus documents"""
        while True:
            current_consensus = await self.fetch_latest_consensus()
            if current_consensus != self.last_consensus:
                await self.ingest_consensus(current_consensus)
                self.last_consensus = current_consensus
            await asyncio.sleep(300)  # Check every 5 minutes
    
    async def fetch_latest_consensus(self):
        """Fetch the most recent consensus"""
        url = "http://collector.torproject.org/recent/relay-descriptors/consensuses/"
        # Get directory listing and find newest file
        response = await self.http_client.get(url)
        newest_file = self.parse_newest_consensus(response.text)
        return newest_file
```

## Data Processing Pipeline

### 1. Consensus Processing
```sql
-- Temporary staging table
CREATE TABLE consensus_staging
(
    consensus_time DateTime,
    fingerprint String,
    nickname String,
    ip String,
    or_port UInt16,
    dir_port UInt16,
    flags Array(String),
    version String,
    bandwidth UInt32,
    measured UInt32
) ENGINE = Memory;

-- Insert parsed data
INSERT INTO consensus_staging FORMAT JSONEachRow;

-- Transform and insert into main table
INSERT INTO consensus_history
SELECT 
    consensus_time,
    fingerprint,
    nickname,
    toIPv4(ip) as ip,
    or_port,
    dir_port,
    flags,
    bandwidth as consensus_weight,
    measured as bandwidth_measured,
    extractVersion(version) as version,
    extractOS(version) as os,
    '' as contact,  -- Will be joined from server descriptors
    0 as as_number,  -- Will be enriched via GeoIP
    '' as as_name,
    '' as country_code,
    '' as region,
    '' as city,
    0 as latitude,
    0 as longitude
FROM consensus_staging;
```

### 2. Descriptor Enrichment
```python
def enrich_with_descriptors(consensus_time):
    """Enrich consensus data with server descriptors"""
    # Fetch corresponding server descriptors
    descriptors = fetch_server_descriptors(consensus_time)
    
    # Parse and match by fingerprint
    for desc in descriptors:
        parsed = parse_server_descriptor(desc)
        
        # Update consensus records with additional info
        ch.execute("""
            ALTER TABLE consensus_history
            UPDATE 
                contact = %(contact)s,
                platform = %(platform)s
            WHERE fingerprint = %(fingerprint)s
                AND consensus_time = %(consensus_time)s
        """, parsed)
```

### 3. GeoIP Enrichment
```python
def enrich_with_geoip(batch_size=10000):
    """Enrich IP addresses with geographic data"""
    # Use MaxMind GeoIP2 database
    reader = geoip2.database.Reader('GeoLite2-City.mmdb')
    
    # Process in batches
    while True:
        batch = ch.execute("""
            SELECT DISTINCT ip
            FROM consensus_history
            WHERE country_code = ''
            LIMIT %(limit)s
        """, {'limit': batch_size})
        
        if not batch:
            break
        
        updates = []
        for (ip,) in batch:
            try:
                response = reader.city(ip)
                updates.append({
                    'ip': ip,
                    'country_code': response.country.iso_code,
                    'as_number': response.traits.autonomous_system_number,
                    'as_name': response.traits.autonomous_system_organization,
                    'city': response.city.name or '',
                    'latitude': response.location.latitude,
                    'longitude': response.location.longitude
                })
            except:
                pass
        
        # Bulk update
        ch.execute("""
            INSERT INTO geoip_cache FORMAT JSONEachRow
        """, updates)
```

## Optimization Strategies

### 1. Parallel Processing
```python
async def parallel_ingestion(year_month):
    """Process multiple files in parallel"""
    files = await list_archive_files(year_month)
    
    # Create worker pool
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent
    
    async def process_file(file_path):
        async with semaphore:
            data = await download_and_parse(file_path)
            await insert_to_clickhouse(data)
    
    # Process all files concurrently
    tasks = [process_file(f) for f in files]
    await asyncio.gather(*tasks)
```

### 2. Batch Insertions
```python
class BatchInserter:
    def __init__(self, table_name, batch_size=100000):
        self.table = table_name
        self.batch_size = batch_size
        self.buffer = []
    
    def add(self, record):
        self.buffer.append(record)
        if len(self.buffer) >= self.batch_size:
            self.flush()
    
    def flush(self):
        if self.buffer:
            ch.execute(f"""
                INSERT INTO {self.table} FORMAT JSONEachRow
            """, self.buffer)
            self.buffer = []
```

### 3. Data Deduplication
```sql
-- Remove duplicates during ingestion
OPTIMIZE TABLE consensus_history 
FINAL DEDUPLICATE BY fingerprint, consensus_time;

-- Create materialized view for unique relays
CREATE MATERIALIZED VIEW unique_relays_mv
ENGINE = AggregatingMergeTree()
ORDER BY (date, fingerprint)
AS SELECT
    toDate(consensus_time) as date,
    fingerprint,
    argMax(nickname, consensus_time) as nickname,
    argMax(contact, consensus_time) as contact,
    max(consensus_weight) as max_weight,
    avg(consensus_weight) as avg_weight,
    countDistinct(ip) as ip_changes,
    groupUniqArray(country_code) as countries
FROM consensus_history
GROUP BY date, fingerprint;
```

## Monitoring and Quality Assurance

### 1. Data Quality Checks
```python
def validate_ingestion(date):
    """Validate data quality for a given date"""
    checks = []
    
    # Check 1: Record count matches expected
    consensus_count = ch.execute("""
        SELECT count() 
        FROM consensus_history 
        WHERE toDate(consensus_time) = %(date)s
    """, {'date': date})[0][0]
    
    expected = 24 * 7000  # ~24 consensuses * ~7000 relays
    checks.append({
        'check': 'record_count',
        'pass': 0.8 * expected < consensus_count < 1.2 * expected,
        'actual': consensus_count,
        'expected': expected
    })
    
    # Check 2: No missing hours
    hours = ch.execute("""
        SELECT count(DISTINCT toHour(consensus_time))
        FROM consensus_history
        WHERE toDate(consensus_time) = %(date)s
    """, {'date': date})[0][0]
    
    checks.append({
        'check': 'complete_hours',
        'pass': hours == 24,
        'actual': hours,
        'expected': 24
    })
    
    return checks
```

### 2. Performance Monitoring
```sql
-- Track ingestion performance
CREATE TABLE ingestion_metrics
(
    timestamp DateTime,
    phase String,
    records_processed UInt64,
    duration_seconds Float32,
    records_per_second Float32,
    errors UInt32
) ENGINE = MergeTree()
ORDER BY timestamp;

-- Query ingestion stats
SELECT 
    phase,
    sum(records_processed) as total_records,
    avg(records_per_second) as avg_throughput,
    max(records_per_second) as peak_throughput,
    sum(errors) as total_errors
FROM ingestion_metrics
WHERE timestamp > now() - INTERVAL 1 DAY
GROUP BY phase;
```

## Error Handling and Recovery

### 1. Checkpoint Management
```python
class IngestionCheckpoint:
    def __init__(self):
        self.checkpoint_table = 'ingestion_checkpoints'
    
    def save_checkpoint(self, year_month, status):
        ch.execute("""
            INSERT INTO ingestion_checkpoints 
            (year_month, status, timestamp, records_processed)
            VALUES (%(year_month)s, %(status)s, now(), %(records)s)
        """, {
            'year_month': year_month,
            'status': status,
            'records': self.get_record_count(year_month)
        })
    
    def get_resume_point(self):
        """Find where to resume after failure"""
        return ch.execute("""
            SELECT year_month
            FROM ingestion_checkpoints
            WHERE status != 'completed'
            ORDER BY year_month
            LIMIT 1
        """)[0][0]
```

### 2. Data Reconciliation
```python
def reconcile_missing_data():
    """Identify and fill gaps in data"""
    gaps = ch.execute("""
        WITH time_series AS (
            SELECT toDateTime(toDate(min(consensus_time)) + number * 3600) as expected_time
            FROM consensus_history
            CROSS JOIN numbers(dateDiff('hour', min(consensus_time), max(consensus_time)))
        )
        SELECT expected_time
        FROM time_series
        LEFT JOIN (
            SELECT DISTINCT toStartOfHour(consensus_time) as actual_time
            FROM consensus_history
        ) ON expected_time = actual_time
        WHERE actual_time IS NULL
        ORDER BY expected_time
    """)
    
    for (missing_hour,) in gaps:
        reingest_consensus(missing_hour)
```

## Storage Optimization

### 1. Partitioning Strategy
```sql
-- Optimize partition size for query performance
ALTER TABLE consensus_history 
MODIFY SETTING partition_by = 'toYYYYMM(consensus_time)';

-- Add TTL for old detailed data
ALTER TABLE consensus_history 
MODIFY TTL consensus_time + INTERVAL 2 YEAR 
DELETE WHERE consensus_time < now() - INTERVAL 2 YEAR;

-- Keep aggregated data forever
CREATE TABLE relay_history_aggregated
ENGINE = MergeTree()
ORDER BY (date, fingerprint)
AS SELECT
    toDate(consensus_time) as date,
    fingerprint,
    avg(consensus_weight) as avg_weight,
    max(consensus_weight) as max_weight,
    count() as measurements,
    groupArray(flags) as all_flags
FROM consensus_history
GROUP BY date, fingerprint;
```

### 2. Compression Settings
```sql
-- Optimize compression for time-series data
ALTER TABLE consensus_history
MODIFY COLUMN fingerprint CODEC(ZSTD(3)),
MODIFY COLUMN consensus_time CODEC(Delta, ZSTD(1)),
MODIFY COLUMN consensus_weight CODEC(T64, ZSTD(1));
```

## Conclusion

This technical specification provides a robust framework for ingesting and processing 18+ years of Tor network data into ClickHouse. The pipeline handles both historical backfill and real-time updates while ensuring data quality, performance, and reliability. The resulting database will power the advanced analytics features proposed in the main ClickHouse integration proposal.