from __future__ import annotations

from typing import Sequence

import numpy as np


def as_vec3(value: Sequence[float], name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    if arr.shape != (3,):
        raise ValueError(f"{name} must be a 3D vector.")
    return arr


def normalize(value: Sequence[float], name: str, fallback=None) -> np.ndarray:
    arr = as_vec3(value, name)
    length = float(np.linalg.norm(arr))
    if length > 1e-6:
        return arr / length
    if fallback is None:
        raise ValueError(f"{name} cannot be a zero vector.")
    return as_vec3(fallback, name)


def camera_basis(position, forward, up):
    """Return orthonormal basis rows: right, corrected up, forward."""

    del position
    fwd = normalize(forward, "camera_forward")
    up_hint = normalize(up, "camera_up", fallback=(0.0, 0.0, 1.0))
    right = np.cross(up_hint, fwd)

    if float(np.linalg.norm(right)) <= 1e-6:
        fallback_up = np.array((0.0, 1.0, 0.0), dtype=np.float32)
        if abs(float(np.dot(fallback_up, fwd))) > 0.95:
            fallback_up = np.array((1.0, 0.0, 0.0), dtype=np.float32)
        right = np.cross(fallback_up, fwd)

    right = right / float(np.linalg.norm(right))
    corrected_up = np.cross(fwd, right)
    corrected_up = corrected_up / float(np.linalg.norm(corrected_up))
    return np.stack((right, corrected_up, fwd), axis=0).astype(np.float32)


def local_to_world(local_positions, camera_position, basis):
    origin = as_vec3(camera_position, "camera_position")
    return origin[None, :] + local_positions @ basis


def world_vectors_to_local(world_vectors, basis):
    return world_vectors @ basis.T

