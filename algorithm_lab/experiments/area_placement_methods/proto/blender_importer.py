"""
Blender importer for asset_configuration JSON files.

Usage (run inside Blender):
blender --background --python blender_importer.py -- path/to/file1.json path/to/dir_with_jsons

The script creates a collection per JSON file, adds a curve for
`public_space_geometry`, and curves for each `public_space_segments`.
Collection and objects receive custom properties for attributes.
"""
import bpy
import sys
import os
import json
import hashlib
import colorsys
from mathutils import Vector


def create_rectangle_mesh(name, p0, p1, width, collection, material=None, perp=None, inside=True):
    # p0, p1 are Vector
    dir_vec = (p1 - p0)
    if dir_vec.length == 0:
        return None
    dir_n = dir_vec.normalized()
    if perp is None:
        perp = Vector((-dir_n.y, dir_n.x, 0.0))
    else:
        # ensure perp is 2D-aligned
        perp = Vector((perp.x, perp.y, 0.0)).normalized()

    mesh = bpy.data.meshes.new(name + '_mesh')
    if inside:
        # one edge sits on the segment (p0->p1), other edge offset toward perp by width
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


def create_material(name, color):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.diffuse_color = (*color, 1.0)
        mat.use_nodes = False
    return mat


def color_from_name(name):
    # deterministic color from name using HLS
    h = int(hashlib.md5(name.encode('utf-8')).hexdigest()[:8], 16) % 360
    hue = h / 360.0
    lightness = 0.5
    saturation = 0.65
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    return (r, g, b)


# global materials registry for boundary types
BOUNDARY_MATERIALS = {}


def ensure_materials_for_types(types):
    for t in types:
        name = f"seg_{t}"
        if name in bpy.data.materials:
            BOUNDARY_MATERIALS[t] = bpy.data.materials[name]
        else:
            color = color_from_name(t)
            BOUNDARY_MATERIALS[t] = create_material(name, color)


def get_material_for_boundary(boundary_type):
    if boundary_type in BOUNDARY_MATERIALS:
        return BOUNDARY_MATERIALS[boundary_type]
    # create on demand
    name = f"seg_{boundary_type}"
    color = color_from_name(boundary_type)
    mat = create_material(name, color)
    BOUNDARY_MATERIALS[boundary_type] = mat
    return mat


def coords_to_vector_list(coords):
    return [Vector((c[0], c[1], c[2] if len(c) > 2 else 0.0)) for c in coords]


def create_polyline_object(name, points, collection, material=None, bevel=0.0):
    curve_data = bpy.data.curves.new(name=name + "_curve", type='CURVE')
    curve_data.dimensions = '3D'
    spline = curve_data.splines.new(type='POLY')
    spline.points.add(len(points) - 1)
    for i, p in enumerate(points):
        spline.points[i].co = (p.x, p.y, p.z, 1.0)
    curve_data.bevel_depth = bevel
    obj = bpy.data.objects.new(name, curve_data)
    collection.objects.link(obj)
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    return obj


def import_json_to_blender(filepath):
    with open(filepath, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    col_name = f"{base_name}"
    if col_name in bpy.data.collections:
        collection = bpy.data.collections[col_name]
    else:
        collection = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(collection)

    # Attach attributes to collection
    if 'public_space_type' in data:
        collection['public_space_type'] = data['public_space_type']
    if 'ratio_dynamic_static' in data:
        collection['ratio_dynamic_static'] = data['ratio_dynamic_static']

    # Materials
    main_mat = create_material('ps_geometry', (0.8, 0.8, 0.2))

    # Main public_space_geometry
    geom = data.get('public_space_geometry')
    polygon_centroid = None
    if geom and geom.get('coordinates'):
        pts = coords_to_vector_list(geom['coordinates'])
        main_obj = create_polyline_object(f"{base_name}_geometry", pts, collection, main_mat, bevel=0.01)
        main_obj['kind'] = 'public_space_geometry'
        # compute simple centroid (average of vertices)
        if pts:
            s = Vector((0.0, 0.0, 0.0))
            for p in pts:
                s += p
            polygon_centroid = s / len(pts)

    # Segments
    # width in meters for segment rectangles
    SEGMENT_WIDTH = 1.0
    for seg in data.get('public_space_segments', []):
        seg_id = seg.get('segment_id')
        seg_geom = seg.get('geometry') or {}
        seg_coords = seg_geom.get('coordinates') or []
        if not seg_coords:
            continue
        pts = coords_to_vector_list(seg_coords)
        seg_name = f"{base_name}_segment_{seg_id}"
        boundary_type = seg.get('boundary_type', 'unknown')
        mat = get_material_for_boundary(boundary_type)
        # create polyline for reference
        seg_obj = create_polyline_object(seg_name, pts, collection, mat, bevel=0.005)
        seg_obj['segment_id'] = seg_id
        seg_obj['boundary_type'] = boundary_type

        # create rectangle mesh (offset toward polygon interior when possible)
        try:
            if len(pts) >= 2:
                p0 = pts[0]
                p1 = pts[-1]
                mid = (p0 + p1) * 0.5
                # compute perpendicular
                dir_vec = (p1 - p0)
                if dir_vec.length > 0:
                    perp = Vector((-dir_vec.normalized().y, dir_vec.normalized().x, 0.0))
                    # determine sign: point toward centroid if available
                    if polygon_centroid is not None:
                        to_cent = (polygon_centroid - mid)
                        if perp.dot(to_cent) < 0:
                            perp = -perp
                    rname = seg_name + '_rect'
                    # build rectangle inside polygon: pass perp and inside=True
                    rect_obj = create_rectangle_mesh(rname, p0, p1, SEGMENT_WIDTH, collection, mat, perp=perp, inside=True)
                    if rect_obj:
                        rect_obj['segment_rect'] = True
                        rect_obj['segment_id'] = seg_id
                        rect_obj['boundary_type'] = boundary_type
        except Exception as e:
            print(f"Failed to create rectangle for segment {seg_id}: {e}")

    print(f"Imported {filepath} -> collection '{col_name}'")


def gather_files_from_args(args):
    files = []
    for a in args:
        if os.path.isdir(a):
            for fname in os.listdir(a):
                if fname.lower().endswith('.json'):
                    files.append(os.path.join(a, fname))
        elif os.path.isfile(a) and a.lower().endswith('.json'):
            files.append(a)
        else:
            # allow glob-like patterns
            import glob
            for path in glob.glob(a):
                if os.path.isfile(path) and path.lower().endswith('.json'):
                    files.append(path)
    return files


def scan_boundary_types(filepaths):
    types = set()
    for fp in filepaths:
        try:
            with open(fp, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            for seg in data.get('public_space_segments', []):
                bt = seg.get('boundary_type')
                if bt:
                    types.add(bt)
        except Exception:
            continue
    return types


def main():
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    else:
        argv = []

    if not argv:
        # No files provided: try the current script folder (workspace root)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print("No files provided; scanning script directory for .json files:", script_dir)
        argv = [script_dir]

    files = gather_files_from_args(argv)
    if not files:
        print('No JSON files found to import.')
        return

    # pre-scan all files to create materials for all boundary types
    types = scan_boundary_types(files)
    ensure_materials_for_types(types)

    for f in files:
        try:
            import_json_to_blender(f)
        except Exception as e:
            print(f"Failed to import {f}: {e}")


if __name__ == '__main__':
    main()
