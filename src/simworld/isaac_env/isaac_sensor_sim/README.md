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

`MountedViewportCameraSensor` is the first concrete sensor. It creates a USD
camera under a robot body prim and switches the active viewport to that camera.
It does not require external labels or renderer overrides.

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
