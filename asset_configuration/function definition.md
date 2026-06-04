public_space_asset_configuration

## Input parameter list

- `public_space_type`: enum
  - `block_entrance`
  - `city_yard_roof`
  - `city_yard_roofless`
  - `city_street_roof`
  - `city_street_roofless`
  - `building_entrance`

- `public_space_geometry`: `LineString3D`
  - closed outer boundary of the public space

- `public_space_segments`
  - `segment_id`: integer
  - `geometry`: `LineString3D`
  - `boundary_type`: enum
    - `block_entrance`
    - `street_boundary_primary`
    - `street_boundary_secondary`
    - `block_boundary_primary`
    - `block_boundary_secondary`
    - `block_boundary_other`
    - `building_entrance_main`
    - `building_wall`
    - `building_other_type`
    - `yard_boundary`
    - `block_other_type`

- `ratio_dynamic_static`: double

- `(Optional) cover_geometry`: `LineString3D`

- `(Optional) asset_has_set`
  - `asset_has_set_id`: integer
  - `asset_has_set_type`: enum
  - `geometry`: `LineString3D`

## Asset candidate list

`asset_candidates_list` has been moved out of the input parameter list.

Current implementation:
- asset candidates are embedded directly inside `ps_asset_config.py`
- the generator uses that embedded list in step 5
- input JSON does not need to provide `asset_candidates_list`

Embedded asset candidate entries contain fields such as:
- `asset_candidates_name`
- `asset_geometry_size`
- `geometry`
- `applicable_types`
- `preferred_zone`
- `probability`
- `probability_by_type` when needed
- `max_count`

## Output parameter list

- `asset_list` (from step 5)
  - `asset_id`: integer
  - `asset_candidates_name`: string
  - `asset_URL`: string
  - `geometry`: `LineString3D`
  - `asset_location`: point
  - `asset_orientation`: point

- `walking_main_line`: `LineString3D` (from step 3)

## Workflow

### Step 1. Segment priority and walkability

- Priority rule:
  - `0`: `block_entrance`, `building_entrance_main`
  - `2`: `street_boundary_primary`
  - `4`: `yard_boundary`, `block_boundary_secondary`
  - `6`: `block_boundary_primary`, `street_boundary_secondary`
  - `8`: `building_other_type`, `block_boundary_other`
  - `15`: `building_wall`
- Walkability rule:
  - `building_wall` is not walkable
  - all others are walkable

### Step 2. Generate people points

- First check whether there is an `arcade_column` within `1m` of the segment
- If yes:
  - project the column center to the segment
  - split the segment by all such projections
  - for each sub-segment with length `> 3m`, use the midpoint as a people point
- Otherwise use length-based generation:
  - if `segment.length < 25m`: one midpoint
  - if `25m < segment.length < 75m`: two points at `1/3` and `2/3`
  - if `segment.length > 75m`: three points at `1/4`, `2/4`, `3/4`

### Step 3. Generate walking flow

- `block_entrance`: cross flow
- `city_street_*`: fishbone flow
- other types: choose from fishbone / ring / orthogonal

#### Fishbone

- connect the highest-priority opposite pair as the main line
- other points connect perpendicularly to the main line or nearest secondary line

#### Ring

- if there is central `asset_has_set`, offset around it
- otherwise create a centered inner ring
- other people points connect to the ring

#### Orthogonal

- highest-priority two people points define the main line
- the main line must be horizontal / vertical polyline or straight line, never diagonal

Two cases:

1. **Opposite directions**
   - main line is straight or two-bend orthogonal
   - if main line is straight:
     - the other two directions connect to the main line by perpendiculars
   - if main line is bent:
     - the other two directions connect to the nearer middle bend point
   - after that:
     - remaining points on the main-line directions connect to the nearest bend point
     - if there is no bend, they connect perpendicularly to secondary lines
   - extra restriction:
     - perpendicular direction must be perpendicular to the source point's segment direction

2. **Adjacent directions**
   - main line is always one-bend orthogonal
   - first process the two still-unconnected directions
   - then process the remaining points in priority order
   - for each point:
     - first try perpendicular connection to all already-generated flows
     - if any valid perpendicular succeeds, use that
     - otherwise connect to the bend point with an orthogonal broken line
   - extra restriction:
     - perpendicular direction must be perpendicular to the source point's segment direction

### Step 4. Generate dynamic and static zones

- Assume main line width is `1.5x` of other flow widths
- solve width `w` from dynamic area target
- generate dynamic zones around walking lines
- remaining areas become static zones

### Step 5. Asset selection and placement

#### 1. `city_street_roof`

- no assets

#### 2. `city_street_roofless`

- `guangzhou_bus_stop`: `20%`, at most one, static zone
- `shared_bike_parking`: `50%`, at most one, static zone
- greenery + guard rail:
  - `50%`: `tree_pool` or `flower_box`, along `block_boundary`, every `5m`, with `guard_rail`
  - `50%`: `tree_pool`, set back inside, every `5m`, with `guard_rail`
- `street_light`: `100%`, along `block_boundary`
- `trash_bin`: `100%`, one, near greenery / tree pool
- `fire_hydrant`: `100%`, one, near greenery / tree pool

#### 3. `block_entrance`

- assets go to static zones, not on the block boundary itself
- bollard / stone sphere / stone post: `100%`
- vehicle traffic light: `100%`
- pedestrian traffic light: `100%`
- metro sign: `50%`

#### 4. `building_entrance`

- `vending_machine`: `50%`, static zone, wall-offset placement
- `smart_locker`: `100%`, static zone, wall-offset placement
- `entrance_canopy`: `100%`, entrance segment related

#### 5. `city_yard_roof`

- static-zone fill:
  - `25%` long bench
  - `75%` seat group
- `vending_machine`: `50%`, near building side, static zone, wall-offset placement
- `food_cart`: `50%`, dynamic zone

#### 6. `city_yard_roofless`

- static-zone fill, exclusive per selected static zone:
  - if there is a central static zone at the center and area > `15%`, place one `sculpture`
  - `25%` long bench
  - `50%` grass
  - `25%` seat group
- boundary static zones:
  - `75%`: `tree_pool` or `flower_box` + `guard_rail`
  - `25%`: `tree_pool` set back inside + `guard_rail`
- `street_light`: `100%`, along `block_boundary`
- `food_cart`: `50%`, dynamic zone
- `trash_bin`: `100%`, one
- `fire_hydrant`: `100%`, one
