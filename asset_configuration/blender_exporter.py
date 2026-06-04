"""
Blender exporter for augmented asset configuration output (steps 1, 2, 3, 4, 5).

Reads augmented JSON with:
- public_space_segments (with priority, walkable)
- people_points (with location, segment_id, priority)
- walking_lines (with line_role, pattern, geometry)
- dynamic_zones (with geometry, area, width)
- static_zones (with geometry, area)
- asset_list (with geometry, asset_location, asset_candidates_name)

Creates visualization:
- Segments as rectangle meshes (1m width, colored by priority)
- People points as sphere primitives (0.5m radius, colored by priority)
- Walking lines as beveled curves, styled by line role
- Dynamic zones as translucent meshes
- Static zones as translucent meshes
- Assets as flat rectangle meshes

Usage:
  blender --python blender_exporter.py -- path/to/augmented.json
"""
import bpy
import sys
import os
import json
from mathutils import Vector


def create_material(name, color):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.diffuse_color = (*color, 1.0)
        mat.use_nodes = False
    return mat


def priority_to_color(priority):
    """Map priority level to RGB color.
    
    Lower priority number (higher importance) = warmer colors
    """
    priority_colors = {
        0: (1.0, 0.0, 0.0),      # red (highest)
        2: (1.0, 0.5, 0.0),      # orange
        4: (1.0, 1.0, 0.0),      # yellow
        6: (0.0, 1.0, 0.0),      # green
        8: (0.0, 0.5, 1.0),      # blue
        15: (0.5, 0.0, 1.0),     # purple
    }
    return priority_colors.get(priority, (0.7, 0.7, 0.7))


def create_material_for_priority(priority):
    name = f"priority_{priority}"
    color = priority_to_color(priority)
    return create_material(name, color)


def walking_line_style(line_role):
    styles = {
        'main': {'color': (1.0, 1.0, 1.0), 'bevel_depth': 0.18},
        'secondary': {'color': (0.0, 1.0, 1.0), 'bevel_depth': 0.10},
        'cross': {'color': (1.0, 0.2, 1.0), 'bevel_depth': 0.14},
    }
    return styles.get(line_role, {'color': (0.85, 0.85, 0.85), 'bevel_depth': 0.10})


def zone_style(zone_type):
    styles = {
        'dynamic': {'color': (1.0, 0.45, 0.1, 0.35)},
        'static': {'color': (0.2, 0.45, 1.0, 0.18)},
    }
    return styles.get(zone_type, {'color': (0.7, 0.7, 0.7, 0.2)})


def asset_style(zone_type):
    styles = {
        'dynamic': {'color': (1.0, 0.1, 0.1, 0.95)},
        'static': {'color': (0.1, 0.9, 0.1, 0.95)},
        'fallback': {'color': (0.9, 0.9, 0.9, 0.95)},
    }
    return styles.get(zone_type, {'color': (0.9, 0.9, 0.9, 0.95)})


def create_rectangle_mesh(name, p0, p1, width, collection, material=None, perp=None, inside=True):
    """Create a rectangular mesh between two points."""
    dir_vec = (p1 - p0)
    if dir_vec.length == 0:
        return None
    dir_n = dir_vec.normalized()
    if perp is None:
        perp = Vector((-dir_n.y, dir_n.x, 0.0))
    else:
        perp = Vector((perp.x, perp.y, 0.0)).normalized()

    mesh = bpy.data.meshes.new(name + '_mesh')
    if inside:
        offset = perp * width
        v0 = p0
        v1 = p1
        v2 = p1 + offset
        v3 = p0 + offset
    else:
        half = width * 0.5
        v0 = p0 + perp * half
        v1 = p0 - perp * half
        v2 = p1 - perp * half
        v3 = p1 + perp * half

    verts = [v0.to_tuple(), v1.to_tuple(), v2.to_tuple(), v3.to_tuple()]
    faces = [(0, 1, 2, 3)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    return obj


def create_sphere(name, location, radius, collection, material=None):
    """Create a UV sphere at location."""
    mesh = bpy.data.meshes.new(name + '_mesh')
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius,
        location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    # Move to collection
    for coll in obj.users_collection:
        coll.objects.unlink(obj)
    collection.objects.link(obj)
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    return obj


def create_polygon_mesh(name, coords, collection, material=None):
    """Create a flat polygon mesh from closed coordinates."""
    if len(coords) < 3:
        return None

    points = []
    for coord in coords:
        x = coord[0]
        y = coord[1]
        z = coord[2] if len(coord) > 2 else 0.0
        points.append((x, y, z))

    if len(points) >= 2 and (Vector(points[0]) - Vector(points[-1])).length <= 1e-6:
        points = points[:-1]
    if len(points) < 3:
        return None

    mesh = bpy.data.meshes.new(name + '_mesh')
    faces = [tuple(range(len(points)))]
    mesh.from_pydata(points, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    return obj


def ensure_child_collection(parent, name):
    child = parent.children.get(name)
    if child is None:
        child = bpy.data.collections.new(name)
        parent.children.link(child)
    return child


def create_curve_line(name, coords, bevel_depth, collection, material=None):
    """Create a polyline curve object from coordinates."""
    if len(coords) < 2:
        return None

    curve_data = bpy.data.curves.new(name=name + '_curve', type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = bevel_depth
    curve_data.bevel_resolution = 4
    curve_data.fill_mode = 'FULL'

    spline = curve_data.splines.new('POLY')
    spline.points.add(len(coords) - 1)

    for index, coord in enumerate(coords):
        x = coord[0]
        y = coord[1]
        z = coord[2] if len(coord) > 2 else 0.0
        spline.points[index].co = (x, y, z, 1.0)

    obj = bpy.data.objects.new(name, curve_data)
    collection.objects.link(obj)
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    return obj


def export_augmented_json_to_blender(filepath):
    """Load augmented JSON and create Blender objects."""
    with open(filepath, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    col_name = f"{base_name}_export"
    if col_name in bpy.data.collections:
        collection = bpy.data.collections[col_name]
    else:
        collection = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(collection)

    segments_collection = ensure_child_collection(collection, "segments")
    people_collection = ensure_child_collection(collection, "people_points")
    flows_collection = ensure_child_collection(collection, "walking_lines")
    dynamic_collection = ensure_child_collection(collection, "dynamic_zones")
    static_collection = ensure_child_collection(collection, "static_zones")
    assets_collection = ensure_child_collection(collection, "assets")

    # Create materials for each priority level
    priority_materials = {}
    for p in [0, 2, 4, 6, 8, 15]:
        priority_materials[p] = create_material_for_priority(p)
    walking_line_materials = {
        role: create_material(f"walking_line_{role}", walking_line_style(role)['color'])
        for role in ['main', 'secondary', 'cross']
    }
    dynamic_zone_material = create_material("zone_dynamic", zone_style('dynamic')['color'][:3])
    dynamic_zone_material.diffuse_color = zone_style('dynamic')['color']
    static_zone_material = create_material("zone_static", zone_style('static')['color'][:3])
    static_zone_material.diffuse_color = zone_style('static')['color']
    asset_materials = {
        zone_type: create_material(f"asset_{zone_type}", asset_style(zone_type)['color'][:3])
        for zone_type in ['dynamic', 'static', 'fallback']
    }
    for zone_type, material in asset_materials.items():
        material.diffuse_color = asset_style(zone_type)['color']

    # Create segment rectangles (1m width)
    segments = data.get('public_space_segments', [])
    SEGMENT_WIDTH = 1.0

    # Compute polygon centroid for inward offset
    geom = data.get('public_space_geometry', {})
    polygon_centroid = None
    if geom and geom.get('coordinates'):
        coords = geom['coordinates']
        if coords:
            cx = sum(c[0] for c in coords) / len(coords)
            cy = sum(c[1] for c in coords) / len(coords)
            polygon_centroid = Vector((cx, cy, 0.0))

    for seg in segments:
        seg_id = seg.get('segment_id')
        priority = seg.get('priority', 10)
        seg_geom = seg.get('geometry', {})
        coords = seg_geom.get('coordinates', [])

        if len(coords) < 2:
            continue

        p0 = Vector((coords[0][0], coords[0][1], coords[0][2] if len(coords[0]) > 2 else 0.0))
        p1 = Vector((coords[-1][0], coords[-1][1], coords[-1][2] if len(coords[-1]) > 2 else 0.0))

        # Compute inward perpendicular
        dir_vec = (p1 - p0)
        if dir_vec.length > 0:
            perp = Vector((-dir_vec.normalized().y, dir_vec.normalized().x, 0.0))
            # Orient toward centroid
            if polygon_centroid:
                mid = (p0 + p1) * 0.5
                to_cent = (polygon_centroid - mid)
                if perp.dot(to_cent) < 0:
                    perp = -perp

            mat = priority_materials.get(priority, create_material_for_priority(10))
            rect_name = f"seg_{seg_id}_priority_{priority}"
            rect_obj = create_rectangle_mesh(rect_name, p0, p1, SEGMENT_WIDTH, segments_collection, mat, perp=perp, inside=True)
            if rect_obj:
                rect_obj['segment_id'] = seg_id
                rect_obj['priority'] = priority
                rect_obj['boundary_type'] = seg.get('boundary_type', '')

    # Create people point spheres (0.5m radius)
    POINT_RADIUS = 0.5
    people_points = data.get('people_points', [])

    for i, pt in enumerate(people_points):
        loc = pt.get('location', [0, 0, 0])
        seg_id = pt.get('segment_id')
        priority = pt.get('priority', 10)

        location = (loc[0], loc[1], loc[2] if len(loc) > 2 else 0.0)
        mat = priority_materials.get(priority, create_material_for_priority(10))
        pt_name = f"people_{i}_seg_{seg_id}_priority_{priority}"

        # Use primitive sphere
        bpy.ops.mesh.primitive_uv_sphere_add(radius=POINT_RADIUS, location=location)
        sphere_obj = bpy.context.active_object
        sphere_obj.name = pt_name
        # Move to collection
        for coll in sphere_obj.users_collection:
            coll.objects.unlink(sphere_obj)
        people_collection.objects.link(sphere_obj)
        if mat:
            if sphere_obj.data.materials:
                sphere_obj.data.materials[0] = mat
            else:
                sphere_obj.data.materials.append(mat)

        sphere_obj['segment_id'] = seg_id
        sphere_obj['priority'] = priority

    # Create walking flow line curves
    walking_lines = data.get('walking_lines', [])

    for line in walking_lines:
        line_id = line.get('line_id', 0)
        line_role = line.get('line_role', 'secondary')
        pattern = line.get('pattern', 'unknown')
        coords = line.get('geometry', {}).get('coordinates', [])

        style = walking_line_style(line_role)
        mat = walking_line_materials.get(
            line_role,
            create_material(f"walking_line_{line_role}", style['color'])
        )
        line_name = f"flow_{line_id}_{line_role}_{pattern}"
        line_obj = create_curve_line(
            line_name,
            coords,
            style['bevel_depth'],
            flows_collection,
            material=mat,
        )
        if line_obj:
            line_obj['line_id'] = line_id
            line_obj['line_role'] = line_role
            line_obj['pattern'] = pattern

    dynamic_zones = data.get('dynamic_zones', [])
    for zone in dynamic_zones:
        zone_id = zone.get('zone_id', 0)
        coords = zone.get('geometry', {}).get('coordinates', [])
        zone_obj = create_polygon_mesh(
            f"dynamic_zone_{zone_id}",
            coords,
            dynamic_collection,
            material=dynamic_zone_material,
        )
        if zone_obj:
            zone_obj['zone_id'] = zone_id
            zone_obj['zone_type'] = 'dynamic'
            zone_obj['area'] = zone.get('area', 0.0)
            zone_obj['width'] = zone.get('width', 0.0)

    static_zones = data.get('static_zones', [])
    for zone in static_zones:
        zone_id = zone.get('zone_id', 0)
        coords = zone.get('geometry', {}).get('coordinates', [])
        zone_obj = create_polygon_mesh(
            f"static_zone_{zone_id}",
            coords,
            static_collection,
            material=static_zone_material,
        )
        if zone_obj:
            zone_obj['zone_id'] = zone_id
            zone_obj['zone_type'] = 'static'
            zone_obj['area'] = zone.get('area', 0.0)

    asset_list = data.get('asset_list', [])
    for asset in asset_list:
        asset_id = asset.get('asset_id', 0)
        asset_name = asset.get('asset_candidates_name', 'asset')
        zone_type = asset.get('zone_type', 'fallback')
        coords = asset.get('geometry', {}).get('coordinates', [])
        asset_obj = create_polygon_mesh(
            f"asset_{asset_id}_{asset_name}",
            coords,
            assets_collection,
            material=asset_materials.get(zone_type, asset_materials['fallback']),
        )
        if asset_obj:
            asset_obj.location.z += 0.02
            asset_obj['asset_id'] = asset_id
            asset_obj['asset_name'] = asset_name
            asset_obj['asset_url'] = asset.get('asset_URL', '')
            asset_obj['zone_type'] = zone_type
            asset_obj['zone_id'] = asset.get('zone_id')

    print(f"Exported augmented JSON to collection '{col_name}'")
    print(f"  - {len(segments)} segment rectangles (1m width)")
    print(f"  - {len(people_points)} people points (0.5m radius)")
    print(f"  - {len(walking_lines)} walking lines (beveled curves)")
    print(f"  - {len(dynamic_zones)} dynamic zones")
    print(f"  - {len(static_zones)} static zones")
    print(f"  - {len(asset_list)} assets")


def gather_files_from_args(args):
    files = []
    for a in args:
        if os.path.isdir(a):
            for fname in os.listdir(a):
                if fname.lower().endswith('_augmented.json'):
                    files.append(os.path.join(a, fname))
        elif os.path.isfile(a) and a.lower().endswith('.json'):
            files.append(a)
        else:
            import glob
            for path in glob.glob(a):
                if os.path.isfile(path) and path.lower().endswith('.json'):
                    files.append(path)
    return files


def main():
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    else:
        argv = []

    if not argv:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print("No files provided; scanning script directory for *_augmented.json files:", script_dir)
        argv = [script_dir]

    files = gather_files_from_args(argv)
    if not files:
        print('No augmented JSON files found to export.')
        return

    for f in files:
        try:
            export_augmented_json_to_blender(f)
        except Exception as e:
            print(f"Failed to export {f}: {e}")


if __name__ == '__main__':
    main()
