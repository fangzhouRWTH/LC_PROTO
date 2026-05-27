"""Reference Warp kernel source for graph-backed particle updates."""

WARP_VIEWPORT_PARTICLE_KERNEL = r'''
import warp as wp


@wp.func
def _wrap(value: float, lower: float, span: float):
    return wp.mod(value - lower, span) + lower


@wp.kernel
def update_viewport_particles(
    positions: wp.array(dtype=wp.vec3),
    speed_scale: wp.array(dtype=float),
    camera_position: wp.vec3,
    camera_right: wp.vec3,
    camera_up: wp.vec3,
    camera_forward: wp.vec3,
    volume_min: wp.vec3,
    volume_span: wp.vec3,
    direction_world: wp.vec3,
    wind_world: wp.vec3,
    speed: float,
    dt: float,
):
    tid = wp.tid()
    pos = positions[tid]
    velocity = direction_world * speed * speed_scale[tid] + wind_world
    pos = pos + velocity * dt

    rel = pos - camera_position
    local = wp.vec3(
        wp.dot(rel, camera_right),
        wp.dot(rel, camera_up),
        wp.dot(rel, camera_forward),
    )

    local = wp.vec3(
        _wrap(local[0], volume_min[0], volume_span[0]),
        _wrap(local[1], volume_min[1], volume_span[1]),
        _wrap(local[2], volume_min[2], volume_span[2]),
    )

    positions[tid] = (
        camera_position
        + camera_right * local[0]
        + camera_up * local[1]
        + camera_forward * local[2]
    )
'''

