# Enhancement Plan: Vessel and Cargo Search Tools

## Overview
This document outlines planned improvements to the `search_vessel` and `search_cargo` tools to provide more comprehensive and flexible search capabilities.

## Part 1: Vessel Search Enhancements

### 1. New Search Criteria

### 1.1 Email Time Filter
**Description:** Filter vessels based on when their listing emails were received.  
**Use Cases:**
- Find vessels advertised in a specific timeframe (e.g., "second half of January")
- Filter by recency of listing
- Identify seasonal availability patterns

**Implementation:**
- Add `email_date_range` parameter with start/end dates
- Filter using `time_of_email` from the emails table

### 1.2 Sender Email Filter
**Description:** Filter vessels by the email address of the sender.  
**Use Cases:**
- Find vessels from specific brokers or companies
- Filter out or focus on particular sources
- Track offerings from known contacts
- Search exclusively by sender without requiring other parameters

**Implementation:**
- Add `sender_email` parameter (can be used as standalone parameter)
- Use case-insensitive partial matching (ILIKE) for flexibility
- Allow searching by just sender email without requiring other parameters

### 1.3 Port City and Shipping Zone Filter with Vector Similarity
**Description:** Filter vessels by either port city or shipping zone using vector similarity matching.  
**Use Cases:**
- Find vessels at specific ports without requiring exact text matching
- Find vessels in specific shipping zones/regions
- Handle typos and variations in location names
- Fallback to regional search when no vessels found at specific ports

**Implementation:**
- Add `port_city` OR `shipping_zone` parameter to search schema (mutually exclusive)
- Use vector similarity to find matches:
  * For ports: Find top 2 matching ports and require is_port=true
  * For zones: Find single best matching shipping zone
- Implement fallback: If no vessels at matched ports, try finding vessels in the matching shipping zone

### 2. Improved Opening Date Logic

### 2.1 Current Logic
Currently, we only return vessels whose availability period fully encompasses the search range:
```sql
(vo.start_date <= $1::date AND vo.end_date >= $2::date)
```

### 2.2 Enhanced Logic
The enhanced logic will also include vessels that are fully encompassed by the search range:
```sql
(
    -- Case 1: Vessel dates encompass search range (current logic)
    (vo.start_date <= $1::date AND vo.end_date >= $2::date)
    OR
    -- Case 2: Search range encompasses vessel dates
    ($1::date <= vo.start_date AND $2::date >= vo.end_date)
)
```

### 2.3 Examples

| Scenario | Vessel Period | Search Period | Current Result | New Result |
|----------|---------------|---------------|----------------|------------|
| 1 | Jan 10-20 | Jan 12-15 | MATCH | MATCH |
| 2 | Jan 15-17 | Jan 10-20 | NO MATCH | MATCH |
| 3 | Jan 5-15 | Jan 10-20 | NO MATCH | NO MATCH* |

*Note: Scenario 3 shows a partial overlap case which we are deferring for future consideration.

### 3. Schema Updates

### 3.1 Updated Request Schema
```
VesselSearchRequest
├── date_range (Optional)
│   ├── start_date: date
│   └── end_date: date
├── dwt_range (Optional)
│   ├── min_dwt: int
│   └── max_dwt: int
├── email_date_range (Optional) [NEW]
│   ├── start_date: date
│   └── end_date: date
├── sender_email (Optional) [NEW]
├── port_city (Optional) [NEW]
├── shipping_zone (Optional) [NEW]
└── only_count: bool = False
```

### 4. SQL Query Changes

### 4.1 Opening Date Logic
```sql
AND (
    $1::date IS NULL OR
    (
        -- Case 1: Vessel dates encompass search range
        (vo.start_date <= $1::date AND vo.end_date >= $2::date)
        OR
        -- Case 2: Search range encompasses vessel dates
        ($1::date <= vo.start_date AND $2::date >= vo.end_date)
    )
)
```

### 4.2 Email Date Filter
```sql
AND (
    $5::date IS NULL OR
    (e.time_of_email::date BETWEEN $5::date AND $6::date)
)
```

### 4.3 Sender Email Filter
```sql
AND (
    $7::text IS NULL OR
    e.email_from ILIKE $7
)
```

### 4.4 Port City and Shipping Zone Filters
```sql
-- For port cities
AND (
    vo.is_port = true
    AND vo.city = ANY($8::text[])  -- Array of top 2 matched port names
)

-- For shipping zones
AND vo.shipping_zone = $9  -- Single matched zone name

-- Note: Only one of these conditions will be used per search
```

### 5. Performance Considerations

### 5.1 Required Indexes
- `listings.email_id`
- `emails.time_of_email`
- `emails.email_from`
- `vessel_openings.city`
- `vessel_openings.shipping_zone`

### 5.2 Query Optimization
- Use parameterized queries consistently
- Consider adding `EXPLAIN ANALYZE` for debugging
- Monitor query performance with complex combinations

### 5.3 Vector Similarity Performance
- Implement efficient vector similarity search (using PostgreSQL pgvector extension)
- Create and maintain embeddings for all port cities and shipping zones
- Consider caching common search results

### 6. Validation Requirements

### 6.1 Date Range Validation
- Ensure start_date <= end_date for both date ranges
- Provide clear error messages for invalid ranges

### 6.2 Email Validation
- Validate that at least one search parameter is provided (including sender_email as a valid standalone parameter)
- Handle case sensitivity appropriately using ILIKE for partial matching
- Allow searching by sender_email without requiring other parameters

### 6.3 Vector Similarity Validation
- Set appropriate similarity thresholds to avoid false matches
- Include matched terms in the response for transparency
- Provide fallback behavior when no good matches are found

## Part 2: Cargo Search Enhancements

### 1. New Cargo Search Criteria

### 1.1 Email Time and Sender Filter
**Description:** Filter cargo listings based on email receipt time and sender.
**Implementation:**
- Add `email_date_range` parameter for filtering by email receipt time
- Add `sender_email` parameter that can be used as a standalone search parameter
- Use case-insensitive partial matching for sender email
- Allow searching by sender email without requiring other parameters

### 1.2 Location-Based Search with Vector Similarity
**Description:** Filter cargo listings by loading and/or discharging locations using vector similarity.  
**Use Cases:**
- Find cargo from specific ports (loading) to specific ports (discharging)
- Find cargo from specific regions (loading zones) to specific regions (discharging zones)
- Find cargo using combinations (port to zone or zone to port)
- Handle typos and variations in location names

**Implementation:**
- Add four new parameters to schema:
  * `loading_port_city`: Search by loading port city
  * `discharging_port_city`: Search by discharging port city
  * `loading_zone`: Search by loading shipping zone
  * `discharging_zone`: Search by discharging shipping zone
- Allow combinations of these parameters (loading + discharging)

### 1.3 Parameter Combinations
The following parameter combinations will be valid:
1. loading_port_city only
2. discharging_port_city only
3. loading_zone only
4. discharging_zone only
5. loading_port_city + discharging_port_city
6. loading_port_city + discharging_zone
7. loading_zone + discharging_port_city
8. loading_zone + discharging_zone

For each location type (loading/discharging), port_city and zone are mutually exclusive.

### 2. Schema Updates

### 2.1 Updated Cargo Search Request Schema
```
CargoSearchRequest
├── date_range (Optional)
│   ├── start_date: date
│   └── end_date: date
├── quantity_range (Optional)
│   ├── min_quantity: int
│   └── max_quantity: int
├── email_date_range (Optional)
│   ├── start_date: date
│   └── end_date: date
├── sender_email (Optional)  # Can be used as standalone parameter
├── loading_port_city (Optional)
├── loading_zone (Optional)
├── discharging_port_city (Optional)
├── discharging_zone (Optional)
└── only_count: bool = False
```

### 3. SQL Query Changes

### 3.1 Loading Location Filters
```sql
-- Loading port city filter
AND (
    $loading_port_city_null OR
    (
        lp.is_port = true
        AND lp.city = ANY($loading_ports)
    )
)

-- Loading zone filter
AND (
    $loading_zone_null OR
    lp.shipping_zone = $loading_zone
)
```

### 3.2 Discharging Location Filters
```sql
-- Discharging port city filter
AND (
    $discharging_port_city_null OR
    (
        dp.is_port = true
        AND dp.city = ANY($discharging_ports)
    )
)

-- Discharging zone filter
AND (
    $discharging_zone_null OR
    dp.shipping_zone = $discharging_zone
)
```

### 3.3 Combined Query Structure
```sql
SELECT ... FROM listings l
LEFT JOIN loading_ports lp ON l.id = lp.listing_id
LEFT JOIN discharging_ports dp ON l.id = dp.listing_id
LEFT JOIN quantity q ON l.id = q.listing_id
LEFT JOIN emails e ON l.email_id = e.id
WHERE l.deleted_at IS NULL
AND l.listing_type = 'Cargo Listing'
AND ... (quantity, date filters)

-- Loading location condition (if specified)
AND (
    $loading_params_null OR
    (
        -- If searching by loading port
        ($using_loading_port AND lp.is_port = true AND lp.city = ANY($loading_ports))
        OR
        -- If searching by loading zone
        ($using_loading_zone AND lp.shipping_zone = $loading_zone)
    )
)

-- Discharging location condition (if specified)
AND (
    $discharging_params_null OR
    (
        -- If searching by discharging port
        ($using_discharging_port AND dp.is_port = true AND dp.city = ANY($discharging_ports))
        OR
        -- If searching by discharging zone
        ($using_discharging_zone AND dp.shipping_zone = $discharging_zone)
    )
)
```

### 4. Fallback Mechanisms

### 4.1 Independent Fallbacks
Each location type gets its own independent fallback:

1. If loading_port_city yields no results:
   - Try finding a matching loading_zone for the same query
   - Update SQL to use this zone instead

2. If discharging_port_city yields no results:
   - Try finding a matching discharging_zone for the same query
   - Update SQL to use this zone instead

### 4.2 Combined Fallback Logic
When both loading and discharging locations are specified:
1. If both have matches: Use both in search
2. If one has matches, one needs fallback: Use the match + fallback
3. If both need fallback: Try both fallbacks
4. If either or both fail completely: Return appropriate error message

### 5. Response Format

```python
# Success Response - Single location search
{
    "listings": [...],
    "total_count": int,
    "message": "Found {count} cargoes loading at {loading_ports}"
    # or
    "message": "Found {count} cargoes discharging at {discharging_ports}"
}

# Success Response - Combined search
{
    "listings": [...],
    "total_count": int,
    "message": "Found {count} cargoes from {loading_ports} to {discharging_ports}"
    # or with fallback
    "message": "No cargoes from {original_port}, showing cargoes from {fallback_zone} region to {discharging_ports} instead"
}

# Error Response
{
    "error": "no_results",
    "message": "No cargoes found matching your criteria.",
    "listings": [],
    "total_count": 0
}
```

### 6. Performance Considerations

### 6.1 Required Indexes
- `listings.email_id`
- `emails.time_of_email`
- `emails.email_from`
- `loading_ports.city`
- `loading_ports.shipping_zone`
- `discharging_ports.city`
- `discharging_ports.shipping_zone`

### 6.2 Query Optimization
- Use parameterized queries consistently
- Consider separate queries for different search combinations
- Use appropriate JOINs for each search type

### 7. Implementation Phases

### 7.1 Phase 1: Schema and Validation Updates
**Files Modified:**
- `app/services/agents/tools/schema.py`
  * Updated docstrings to include sender_email as valid standalone parameter
  * Updated validation requirements

### 7.2 Phase 2: Search Function Updates
**Files Modified:**
- `app/services/agents/tools/search_vessel.py`
  * Updated validation to include sender_email as valid standalone parameter
  * Modified SQL query building to handle sender_email-only searches
- `app/services/agents/tools/search_cargo.py`
  * Updated validation to include sender_email as valid standalone parameter
  * Modified SQL query building to handle sender_email-only searches

### 7.3 Phase 3: Documentation and Prompt Updates
**Files Modified:**
- `app/services/agents/prompts/chat_prompt.py`
  * Updated system prompt to reflect sender_email as standalone parameter
  * Added examples for sender_email-only searches
- `docs/search_listing.md`
  * Updated documentation to reflect new capabilities

### 8. Testing Requirements

Test both vessel and cargo search with:
- Standalone sender_email searches
- Combined searches with sender_email and other parameters
- Partial matching of sender email addresses
- Case-insensitive email matching
- Edge cases and validation
- Performance with large result sets

## Part 3: Common Implementation Details

### 1. Vector Similarity Service

The VectorSimilarityService will handle both vessel and cargo search needs:

```python
class VectorSimilarityService:
    """Service for performing vector similarity searches on ports and shipping zones."""
    
    # Vessel search methods
    async def find_matching_ports(self, query: str, limit: int = 2) -> List[str]
    async def find_matching_zone(self, query: str) -> Optional[str]
    async def find_zone_for_port_query(self, query: str) -> Optional[str]
    
    # Cargo search methods
    async def find_matching_loading_ports(self, query: str, limit: int = 2) -> List[str]
    async def find_matching_discharging_ports(self, query: str, limit: int = 2) -> List[str]
    async def find_matching_loading_zone(self, query: str) -> Optional[str]
    async def find_matching_discharging_zone(self, query: str) -> Optional[str]
    async def find_zone_for_loading_port_query(self, query: str) -> Optional[str]
    async def find_zone_for_discharging_port_query(self, query: str) -> Optional[str]
```

### 2. Response Structure for Both Tools

```python
# Success Response
{
    "listings": [...],
    "total_count": int,
    "message": str  # Clear message about search results and fallback if used
}

# Error Response
{
    "error": "no_results",
    "message": str,  # Clear error message
    "listings": [],
    "total_count": 0
}
```

### 3. Testing Strategy

Test both vessel and cargo search enhancements:
- Test individual parameters
- Test parameter combinations
- Test fallback mechanisms
- Test edge cases and error handling
- Test performance with complex queries
