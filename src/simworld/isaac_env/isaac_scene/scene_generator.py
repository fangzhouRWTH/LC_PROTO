from . import scene_parser
import engine.placement as placement


def generate_plane_polygon_layout(polygon: scene_parser.PlaceholderArea):
    ply3d: placement.Polygon3D = list()
    for v in polygon.vertices:
        v3: placement.Vec3 = (v[0], v[1], v[2])
        ply3d.append(v3)

    return placement.generate_public_space_footprints_3d(ply3d)
