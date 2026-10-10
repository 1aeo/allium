# Onionoo: family_id Field Implementation Analysis

## Overview

This document analyzes the Onionoo codebase to determine which files need to be modified to add support for the new `family_id` field that will be coming from directory authorities.

**Reference:** [GitLab Issue #40051](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/issues/40051#note_3336944)

**Example format:**
```json
"family_id": ["YupI/ZI1z/u27VJADaCMftUsx51zT6atLD0Y2O9+XW8"]
```

## Architecture Overview

The Onionoo data flow is:

1. **Descriptor Parsing** → `metrics-lib` parses consensus/descriptors
2. **Status Update** → `NodeDetailsStatusUpdater` processes data into `NodeStatus` and `DetailsStatus`
3. **Document Writing** → `DetailsDocumentWriter` creates `DetailsDocument` for API output
4. **API Serving** → `ResponseBuilder` serves JSON to clients

## Files That Need Modification

### 1. DetailsDocument.java (API Output Document)

**File:** `src/main/java/org/torproject/metrics/onionoo/docs/DetailsDocument.java`

**Location:** After line ~430 (after `indirectFamily` field)

**Changes needed:**
- Add new field for `familyId` (will serialize as `family_id` in JSON via Jackson naming convention)
- Add getter and setter methods

**Example code to add:**
```java
private List<String> familyId;

public void setFamilyId(List<String> familyId) {
  this.familyId = (familyId != null && !familyId.isEmpty()) ? familyId : null;
}

public List<String> getFamilyId() {
  return this.familyId;
}
```

---

### 2. DetailsStatus.java (Internal Status Document)

**File:** `src/main/java/org/torproject/metrics/onionoo/docs/DetailsStatus.java`

**Location:** After line ~163 (after `indirectFamily` field)

**Changes needed:**
- Add new field to store family_id
- Add getter and setter methods

**Example code to add:**
```java
private List<String> familyId;

public void setFamilyId(List<String> familyId) {
  this.familyId = familyId;
}

public List<String> getFamilyId() {
  return this.familyId;
}
```

---

### 3. NodeStatus.java (In-Memory Status)

**File:** `src/main/java/org/torproject/metrics/onionoo/docs/NodeStatus.java`

**Location:** After line ~522 (after `extendedFamily` field)

**Changes needed:**
- Add new field for family_id
- Add getter and setter methods
- Update `fromString()` method (around line 571) to deserialize family_id
- Update `toString()` method (around line 729) to serialize family_id

**Example code to add:**
```java
private List<String> familyId;

public void setFamilyId(List<String> familyId) {
  this.familyId = familyId;
}

public List<String> getFamilyId() {
  return this.familyId;
}
```

**Serialization format notes:**
The `NodeStatus` class uses tab-separated values for serialization. A new field position (e.g., position 28) would need to be allocated. The format could be:
- Empty string if null/empty
- Semicolon-separated values if multiple family IDs: `id1;id2;id3`

---

### 4. NodeDetailsStatusUpdater.java (Status Updater)

**File:** `src/main/java/org/torproject/metrics/onionoo/updater/NodeDetailsStatusUpdater.java`

**Changes needed at two locations:**

#### A. processRelayNetworkStatusConsensus() - Lines 259-330

Extract family_id from consensus entries:

```java
// Around line 303, after setting version
List<String> familyId = entry.getFamilyId(); // Requires metrics-lib update
if (familyId != null && !familyId.isEmpty()) {
  nodeStatus.setFamilyId(familyId);
}
```

#### B. updateNodeDetailsStatuses() - Lines 869-1068

Copy family_id from nodeStatus to detailsStatus:

```java
// Around line 971, after setting indirect family
detailsStatus.setFamilyId(nodeStatus.getFamilyId());
```

---

### 5. DetailsDocumentWriter.java (Document Writer)

**File:** `src/main/java/org/torproject/metrics/onionoo/writer/DetailsDocumentWriter.java`

#### A. updateRelayDetailsFile() - Lines 68-177

Add around line 155 (after indirectFamily):

```java
if (detailsStatus.getFamilyId() != null
    && !detailsStatus.getFamilyId().isEmpty()) {
  detailsDocument.setFamilyId(detailsStatus.getFamilyId());
}
```

#### B. updateBridgeDetailsFile() - Lines 186-227

If family_id should also be supported for bridges, add similar code around line 220.

---

### 6. Test Files

#### DummyStatusEntry.java
**File:** `src/test/java/org/torproject/metrics/onionoo/updater/DummyStatusEntry.java`

Add mock implementation:

```java
private List<String> familyId;

public void setFamilyId(List<String> familyId) {
  this.familyId = familyId;
}

@Override
public List<String> getFamilyId() {
  return this.familyId;
}
```

#### DetailsDocumentTest.java
**File:** `src/test/java/org/torproject/metrics/onionoo/docs/DetailsDocumentTest.java`

Add test for family_id serialization:

```java
@Test()
public void testFamilyIdExists() throws JsonProcessingException {
  DetailsDocument relay = this.createDetailsDocumentRelay();
  relay.setFingerprint("BE45FFE2F55E29DA327346E9D44A5203086E25B0");
  relay.setRunning(true);
  relay.setFamilyId(Arrays.asList("YupI/ZI1z/u27VJADaCMftUsx51zT6atLD0Y2O9+XW8"));
  assertEquals(
      "{\"fingerprint\":\"BE45FFE2F55E29DA327346E9D44A5203086E25B0\","
      + "\"running\":true,\"family_id\":[\"YupI/ZI1z/u27VJADaCMftUsx51zT6atLD0Y2O9+XW8\"]}",
      objectMapper.writeValueAsString(relay));
}
```

---

## External Dependency: metrics-lib

**Critical:** The `metrics-lib` library must be updated FIRST before Onionoo can consume the data.

**Repository:** https://gitlab.torproject.org/tpo/network-health/metrics/metrics-lib

**Interface to update:** `org.torproject.descriptor.NetworkStatusEntry`

**Method to add:**
```java
/**
 * Returns the family_id value(s) from the consensus, or null if not present.
 */
List<String> getFamilyId();
```

The metrics-lib library is responsible for parsing the raw consensus documents. The `family_id` field will be part of the "r" line or a new line type in the consensus format.

---

## Optional: Search/Filter Support

If you want to enable searching/filtering by `family_id`, additional files need modification:

### SummaryDocument.java
**File:** `src/main/java/org/torproject/metrics/onionoo/docs/SummaryDocument.java`

Add field for indexing purposes:

```java
@JsonProperty("fi")
private List<String> familyId;

public void setFamilyId(List<String> familyId) {
  this.familyId = familyId;
}

public List<String> getFamilyId() {
  return this.familyId;
}
```

### NodeIndex.java
**File:** `src/main/java/org/torproject/metrics/onionoo/server/NodeIndex.java`

Add index map:

```java
private Map<String, Set<String>> relaysByFamilyId = null;

public void setRelaysByFamilyId(Map<String, Set<String>> relaysByFamilyId) {
  this.relaysByFamilyId = relaysByFamilyId;
}

public Map<String, Set<String>> getRelaysByFamilyId() {
  return relaysByFamilyId;
}
```

### NodeIndexer.java
**File:** `src/main/java/org/torproject/metrics/onionoo/server/NodeIndexer.java`

Build the family_id index during indexing.

### RequestHandler.java
**File:** `src/main/java/org/torproject/metrics/onionoo/server/RequestHandler.java`

Handle `family_id` query parameter.

---

## Summary Table

| File | Type | Required | Purpose |
|------|------|----------|---------|
| `DetailsDocument.java` | API Output | **Yes** | Expose field in API response |
| `DetailsStatus.java` | Status | **Yes** | Store field in status documents |
| `NodeStatus.java` | In-Memory | **Yes** | Hold field during processing |
| `NodeDetailsStatusUpdater.java` | Updater | **Yes** | Extract from consensus, copy to status |
| `DetailsDocumentWriter.java` | Writer | **Yes** | Copy to output document |
| `DummyStatusEntry.java` | Test | **Yes** | Mock implementation for tests |
| `DetailsDocumentTest.java` | Test | **Yes** | Verify JSON serialization |
| `SummaryDocument.java` | Index | Optional | Enable searching |
| `NodeIndex.java` | Index | Optional | Enable filtering |
| `NodeIndexer.java` | Index | Optional | Build search index |
| `RequestHandler.java` | Server | Optional | Handle query parameter |
| **metrics-lib** | External | **Yes** | Parse consensus data |

---

## Implementation Order

1. **metrics-lib update** (prerequisite)
   - Add `getFamilyId()` to `NetworkStatusEntry` interface
   - Implement parsing in consensus parser

2. **Onionoo core changes**
   - `DetailsDocument.java`
   - `DetailsStatus.java`
   - `NodeStatus.java`
   - `NodeDetailsStatusUpdater.java`
   - `DetailsDocumentWriter.java`

3. **Tests**
   - `DummyStatusEntry.java`
   - `DetailsDocumentTest.java`
   - `NodeDetailsStatusUpdaterTest.java`

4. **Optional: Search support**
   - `SummaryDocument.java`
   - `NodeIndex.java`
   - `NodeIndexer.java`
   - `RequestHandler.java`

5. **Documentation**
   - Update API documentation
   - Update CHANGELOG.md
