# Isaac Sensor Sim

`isaac_sensor_sim` is a pseudo-sensor runtime. It is intentionally separate
from robot policy code and from real Isaac RTX sensor simulation. A sensor reads
host prim poses and optional scene labels, then emits structured frames that
algorithm code can consume.

## Runtime Contract

Every sensor returns a `SensorFrame`:

```text
sensor_id
sensor_type
timestamp
frame_id
parent_frame_id
world_pose
data
meta
```

Viewport cameras are also sensors. The default Spot rig contains:

```text
follow_view
  A chase camera sensor that owns its own USD camera prim under
  /World/SimWorldSensors. It follows the robot body and is the default active
  viewport input.

spot_front_view
  A mounted preview camera under the Spot body. It approximates a forward-facing
  body camera and can be activated through the same rig switching path.

spot_depth_view
  A mounted pseudo depth camera under the Spot body. It owns a USD camera for
  viewport framing and emits a `float32` depth image in meters in
  `SensorFrame.data["depth_m"]`. When activated, it switches the active viewport
  display to `DistanceToCameraSDDisplay`.
```

The framework intentionally avoids using `/OmniverseKit_Persp` for the default
follow view. That scene camera remains only as a fallback when sensor profiles
are disabled.

Use `SensorRig.activate(sensor_id)` or `SensorRig.activate_next_viewport_camera()`
to switch the viewport source. Activation and deactivation are responsible for
applying and restoring viewport, renderer, material, or render-product state.

Depth camera frame output is currently pseudo data, not RTX/Replicator depth.
The active viewport visualization uses Isaac SyntheticData's depth display
render var plus its post-combine path so sensor switching has an immediate
visual effect. The frame data contract is:

```text
depth_m: float32 array shaped [height, width], meters
depth_resolution: [width, height]
depth_encoding: float32_meters
near_m / far_m: valid clipping range in meters
statistics: min_m / max_m / mean_m
```

Use `--sensor-profile spot_depth_camera` for a depth-only rig, or keep the
default rig and start from it with `--active-sensor spot_depth_view`.

## External Label Inputs

Some pseudo sensors cannot infer meaningful data from pose alone. Semantic
segmentation, image recognition, affordance maps, and object detections should
declare their label input contract explicitly. The Python dataclasses live in
`labels.py`.

Recommended object-label JSON:

```json
{
  "schema": "simworld.object_labels.v1",
  "objects": [
    {
      "prim_path": "/World/GeneratedAssets/car_001",
      "class_id": 12,
      "class_name": "car",
      "instance_id": 1001,
      "bbox3d_world": {
        "center": [1.0, 2.0, 0.8],
        "size": [4.0, 1.8, 1.6],
        "rotation_wxyz": [1.0, 0.0, 0.0, 0.0]
      },
      "attributes": {
        "dynamic": false
      }
    }
  ]
}
```

Recommended raster-label bundle:

```text
schema: simworld.raster_labels.v1
resolution: [width, height]
class_map: uint16 array or PNG path
instance_map: uint32 array or PNG path
palette: {class_id: [r, g, b]}
camera_frame_id: string
timestamp: float
```

## Renderer Control Policy

Pseudo sensors should state whether they need renderer control:

```text
requires_renderer_control: true | false
requires_external_labels: true | false
visualization_mode: data_only | viewport_camera | material_override | render_product
```

For semantic segmentation there are three viable modes:

```text
data_only
  Uses external label JSON/raster inputs and emits arrays. No viewport change.

material_override
  Temporarily applies class-color materials to labeled prims. This gives an
  immediate viewport-visible segmentation look, but must restore original
  material bindings when the sensor is deactivated.

render_product
  Uses Isaac/Replicator render products and semantic annotators. This is closer
  to real rendering, but it couples the sensor to renderer configuration.
```

Sensor switching should call `activate()` and `deactivate()` so any viewport
camera, material override, render mode, or render product state is applied and
restored in one place.
