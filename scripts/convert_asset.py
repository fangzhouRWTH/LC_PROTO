# Copyright (c) 2022-2025, The UrbanSim Project Developers.
# Author: Honglin He
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Utility to convert a OBJ/STL/FBX into USD format.

The OBJ file format is a simple data-format that represents 3D geometry alone — namely, the position
of each vertex, the UV position of each texture coordinate vertex, vertex normals, and the faces that
make each polygon defined as a list of vertices, and texture vertices.

An STL file describes a raw, unstructured triangulated surface by the unit normal and vertices (ordered
by the right-hand rule) of the triangles using a three-dimensional Cartesian coordinate system.

FBX files are a type of 3D model file created using the Autodesk FBX software. They can be designed and
modified in various modeling applications, such as Maya, 3ds Max, and Blender. Moreover, FBX files typically
contain mesh, material, texture, and skeletal animation data.
Link: https://www.autodesk.com/products/fbx/overview


This script uses the asset converter extension from Isaac Sim (``omni.kit.asset_converter``) to convert a
OBJ/STL/FBX asset into USD format. It is designed as a convenience script for command-line use.


positional arguments:
  input               The path to the input mesh (.OBJ/.STL/.FBX) file.
  output              The path to store the USD file.

optional arguments:
  -h, --help                    Show this help message and exit
  --make-instanceable,          Make the asset instanceable for efficient cloning. (default: False)
  --collision-approximation     The method used for approximating collision mesh. Defaults to convexDecomposition.
                                Set to \"none\" to not add a collision mesh to the converted mesh. (default: convexDecomposition)
  --mass                        The mass (in kg) to assign to the converted asset. (default: None)

"""

"""Launch Isaac Sim Simulator first."""


import argparse

from isaaclab.app import AppLauncher

# add argparse arguments
parser = argparse.ArgumentParser(description="Utility to convert a mesh file into USD format.")
parser.add_argument("--input_file_list", type=str, default=None, help="The path to the input mesh file.")
parser.add_argument(
    "--make-instanceable",
    action="store_true",
    default=False,
    help="Make the asset instanceable for efficient cloning.",
)
parser.add_argument(
    "--collision-approximation",
    type=str,
    default="convexDecomposition",
    choices=["convexDecomposition", "convexHull", "boundingCube", "boundingSphere", "meshSimplification", "none"],
    help=(
        'The method used for approximating collision mesh. Set to "none" '
        "to not add a collision mesh to the converted mesh."
    ),
)
parser.add_argument(
    "--mass",
    type=float,
    default=None,
    help="The mass (in kg) to assign to the converted asset. If not provided, then no mass is added.",
)
parser.add_argument(
    "--id",
    type=int,
    default=None,
)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# parse the arguments
args_cli = parser.parse_args()

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import contextlib
import os
import pickle
import tqdm
import json

import carb
import isaacsim.core.utils.stage as stage_utils
import omni.kit.app

from isaaclab.sim.converters import MeshConverter, MeshConverterCfg
from isaaclab.sim.schemas import schemas_cfg
from isaaclab.utils.assets import check_file_path
from isaaclab.utils.dict import print_dict
from pathlib import Path

ROOT_DIR = Path(__file__).parent
print(f"ROOT_DIR: {ROOT_DIR}")


def load_asset_parameter_map(param_dir: str) -> dict[str, list[str]]:
    """Index parameter json files by the trailing asset id used in object filenames."""
    parameter_map: dict[str, list[str]] = {}
    for json_name in os.listdir(param_dir):
        if not json_name.endswith(".json"):
            continue
        asset_id = Path(json_name).stem.split("-")[-1]
        parameter_map.setdefault(asset_id, []).append(json_name)
    return parameter_map


def resolve_asset_parameters(mesh_path: str, param_dir: str, parameter_map: dict[str, list[str]]) -> tuple[dict, str | None]:
    """Resolve the calibration json for a mesh, falling back to default parameters when missing."""
    asset_id = Path(mesh_path).stem.split("_")[-1]
    matches = parameter_map.get(asset_id, [])
    if not matches:
        print(f"[WARNING] No parameter json found for {Path(mesh_path).name}. Falling back to default scale=1.0.")
        return {}, None

    if len(matches) > 1:
        print(f"[INFO] Multiple parameter json matches found for {Path(mesh_path).name}: {matches}. Using {matches[0]}.")

    json_name = matches[0]
    with open(os.path.join(param_dir, json_name), "r") as f:
        return json.load(f), json_name

def main():
    root_dir = os.path.join(ROOT_DIR, 'assets', 'objects')
    valid_files = os.listdir(root_dir)
    valid_files.sort()
    file_names_parent = [f for f in valid_files]
    file_names = file_names_parent
    for asset in file_names:
        if '-' not in asset and " " not in asset:
            continue
        else:
            replaced_name = asset.replace('-', '_').replace(" ", "")
            if ' ' in asset:
                os.system(f'mv {root_dir}/\'{asset}\' {root_dir}/{replaced_name}')
            else:
                os.system(f'mv {root_dir}/{asset} {root_dir}/{replaced_name}')   

    valid_files = os.listdir(root_dir)
    valid_files.sort()
    file_names_parent = [os.path.join(root_dir, f) for f in valid_files]

    file_names = [f for f in file_names_parent if '.glb' in f] 
    file_goes = [f.replace('glb', 'usd').replace('assets/objects', 'assets/usds') for f in file_names]
    param_dir = os.path.join(ROOT_DIR, 'assets', 'adj_parameter_folder')
    parameter_map = load_asset_parameter_map(param_dir)
    
    if args_cli.mass is not None:
        mass_props = schemas_cfg.MassPropertiesCfg(mass=args_cli.mass)
        rigid_props = schemas_cfg.RigidBodyPropertiesCfg()
    else:
        mass_props = None
        rigid_props = None
    mass_props = schemas_cfg.MassPropertiesCfg(mass=args_cli.mass)
    rigid_props = schemas_cfg.RigidBodyPropertiesCfg(rigid_body_enabled=True,kinematic_enabled=True)
    # Collision properties
    collision_props = schemas_cfg.CollisionPropertiesCfg(collision_enabled=args_cli.collision_approximation != "none")
    
    mesh_converters_cfgs = []
    for mesh_path, mesh_go in zip(file_names, file_goes):
        json_data, json_name = resolve_asset_parameters(mesh_path, param_dir, parameter_map)
        # Create Mesh converter config
        mesh_converter_cfg = MeshConverterCfg(
            mass_props=mass_props,
            rigid_props=rigid_props,
            collision_props=collision_props,
            asset_path=mesh_path,
            force_usd_conversion=True,
            usd_dir=os.path.dirname(mesh_go),
            usd_file_name=os.path.basename(mesh_go),
            make_instanceable=args_cli.make_instanceable,
            # Keep raw geometry scale in the converted USD.
            # Per-asset scene calibration is applied later when loading the USD in UrbanScene.
            scale=(1.0, 1.0, 1.0),
            # mesh_collision_props=args_cli.collision_approximation,
        )
        mesh_converters_cfgs.append(mesh_converter_cfg)

    # Print info
    for mesh_converter_cfg in tqdm.tqdm(mesh_converters_cfgs):
        # break
        print('|' + "-" * 100 + '|')
        print('|' + "-" * 100 + '|')
        print("Mesh importer config:")
        print(type(mesh_converter_cfg))
        print_dict(mesh_converter_cfg.to_dict(), nesting=0)
        print('|' + "-" * 100 + '|')
        print('|' + "-" * 100 + '|')

        # print(mesh_converter_cfg.to_dict()['mesh_path'])
        # break

        # Create Mesh converter and import the file
        mesh_converter = MeshConverter(mesh_converter_cfg)

        # stage = mesh_converter.stage
        # prim = stage.GetPrimAtPath(mesh_converter.prim_path)

        # scale_val = 0.5
        # xform = UsdGeom.Xformable(prim)
        # scale_ops = [op for op in xform.GetOrderedXformOps() if op.GetOpName() == "xformOp:scale"]
        # if scale_ops:
        #     scale_ops[0].Set((scale_val, scale_val, scale_val))
        # else:
        #     xform.AddScaleOp().Set((scale_val, scale_val, scale_val))

        # stage.GetRootLayer().Export(mesh_converter.usd_path)
                
        # print output
        print("Mesh importer output:")
        print(f"Generated USD file: {mesh_converter.usd_path}")
        print('|' + "-" * 100 + '|')
        print('|' + "-" * 100 + '|')
        


if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()
