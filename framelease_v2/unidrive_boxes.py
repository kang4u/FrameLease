"""Semantics of UniDriveVLA detection boxes (Interface 1 of framelease_v2).

The pinned UniDriveVLA source (third_party/UniDriveVLA-linux, commit a93c175) defines

* ``projects/mmdet3d_plugin/core/box3d.py``::

      X, Y, Z, W, L, H, SIN_YAW, COS_YAW, VX, VY, VZ = range(11)   # undecoded regression state
      YAW = 6                                                     # decoded

* ``projects/mmdet3d_plugin/models/detection3d/decoder.py`` ``decode_box``::

      [X, Y, Z, exp(W), exp(L), exp(H), atan2(SIN_YAW, COS_YAW), VX, VY, VZ]   -> 10 columns

  ``SparseBox3DDecoder.decode`` (num_output=300, sorted) returns these as ``boxes_3d`` together with
  ``scores_3d`` (sigmoid class score times sigmoid centerness) and ``labels_3d``.

* What the columns mean is fixed by the training targets, not by the column names.  The converter
  ``tools/data_converter/bench2drive_converter.py`` stores ``gt_boxes = [x, y, z, w, l, h, -yaw - pi/2, vx, vy]``
  in the capture LiDAR frame (w = 2*extent_y, l = 2*extent_x of the CARLA actor; ``yaw`` = heading of the actor
  x-axis in the LiDAR frame, ``atan2(vehicle2lidar[1,0], vehicle2lidar[0,0])``; ``(vx, vy) = speed*(cos yaw, sin yaw)``).
  ``Bench2DriveDataset.get_ann_info`` (remap_box=True, align_static_yaw=False, the training config) then swaps
  columns 3 and 4 and maps the angle back with ``-(a + pi/2)``.  The regression target is therefore
  ``[x, y, z, length, width, height, yaw, vx, vy]``: the column the source calls ``W`` (index 3) holds the extent
  ALONG the heading (length) and ``L`` (index 4) the lateral extent (width).  This is consistent with
  ``SparseBox3DKeyPointsGenerator``, which scales the local x key points (rotated by yaw) with ``W``.

Hence, for a decoded row ``b`` of ``boxes_3d`` (capture LiDAR frame of stage02, right-handed, x = right, y = forward,
z = up; metres, radians, m/s):

    b[0], b[1], b[2]  box centre x, y, z
    b[3]              full length along the heading      (source name W)
    b[4]              full width perpendicular to it      (source name L)
    b[5]              full height                         (source name H)
    b[6]              yaw: heading angle of the box x-axis, counter-clockwise from LiDAR +x, in (-pi, pi]
    b[7], b[8]        ground-frame velocity of the actor expressed in LiDAR axes (not ego-relative)
    b[9]              vz (not supervised; ignored)

These semantics were validated empirically against CARLA ground truth by ``c1_depth_sweep.py``
(see ``SWEEP_SCHEMA.md`` and the run's ``validation.json``).
"""
from __future__ import annotations

import numpy as np

# Detection label index -> class name; projects/configs/unidrivevla_b2d_stage2_unified_2b.py det_class_names.
CLASS_NAMES = ("car", "van", "truck", "bicycle", "traffic_sign", "traffic_cone", "traffic_light",
               "pedestrian", "others")

# Label index -> lease group.  Bicycles are CARLA 'vehicle' actors (class 'vehicle' in anno/*.json.gz), so they are
# grouped with vehicles; signs, lights, cones and debris are static 'other' objects.
CLASS_GROUP = {0: "vehicle", 1: "vehicle", 2: "vehicle", 3: "vehicle", 4: "other", 5: "other", 6: "other",
               7: "pedestrian", 8: "other"}

# Lease group -> ground-truth actor class used in gt/<clip>.jsonl (offline evaluation only).
GT_CLASS_FOR_GROUP = {"vehicle": "vehicle", "pedestrian": "walker"}

# Column order of decode_boxes() output.
DECODED_COLUMNS = ("cx", "cy", "length", "width", "yaw", "vx", "vy")
RAW_COLUMNS = ("x", "y", "z", "length(W)", "width(L)", "height(H)", "yaw", "vx", "vy", "vz")
_RAW_INDEX = (0, 1, 3, 4, 6, 7, 8)


def wrap_angle(a):
    """Wrap angles to [-pi, pi)."""
    return (np.asarray(a, dtype=np.float64) + np.pi) % (2.0 * np.pi) - np.pi


def decode_boxes(boxes_3d) -> np.ndarray:
    """UniDriveVLA ``boxes_3d`` [N,10] -> [N,7] = [cx, cy, length, width, yaw, vx, vy] in the capture LiDAR frame.

    Accepts [N,9] (no vz) as well.  Float input keeps its dtype; anything else becomes float64.
    """
    b = np.asarray(boxes_3d)
    if b.ndim != 2 or b.shape[1] not in (9, 10):
        raise ValueError(f"boxes_3d must be [N,10] (or [N,9]); got shape {b.shape}")
    if not np.issubdtype(b.dtype, np.floating):
        b = b.astype(np.float64)
    out = b[:, _RAW_INDEX].copy()
    if out.shape[0]:
        out[:, 4] = wrap_angle(out[:, 4]).astype(out.dtype)
    return out


def group_of(labels) -> np.ndarray:
    """Vector of group names ('vehicle' | 'pedestrian' | 'other') for label indices."""
    labels = np.asarray(labels).astype(int).reshape(-1)
    return np.array([CLASS_GROUP.get(int(x), "other") for x in labels], dtype=object)


def transform_boxes(dets, T) -> np.ndarray:
    """Rigidly move decoded boxes [N,7] with a 4x4 (or 3x3 planar) homogeneous transform.

    Centre is transformed as a point; yaw is offset by the planar rotation angle; velocity is rotated (no
    translation).  E.g. ``transform_boxes(dets, lidar2global)`` gives right-handed world boxes.
    """
    d = np.asarray(dets, dtype=np.float64).reshape(-1, 7)
    T = np.asarray(T, dtype=np.float64)
    if T.shape == (4, 4):
        R, t = T[:2, :2], T[:2, 3]
    elif T.shape == (3, 3):
        R, t = T[:2, :2], T[:2, 2]
    else:
        raise ValueError(f"transform must be 4x4 or 3x3, got {T.shape}")
    out = d.copy()
    out[:, 0:2] = d[:, 0:2] @ R.T + t
    out[:, 4] = wrap_angle(d[:, 4] + np.arctan2(R[1, 0], R[0, 0]))
    out[:, 5:7] = d[:, 5:7] @ R.T
    return out


def box_corners_xy(dets) -> np.ndarray:
    """Footprint corners [N,4,2] (front-left, front-right, rear-right, rear-left) of decoded boxes [N,7]."""
    d = np.asarray(dets, dtype=np.float64).reshape(-1, 7)
    c, s = np.cos(d[:, 4]), np.sin(d[:, 4])
    fwd = np.stack([c, s], -1) * (d[:, 2:3] / 2.0)
    left = np.stack([-s, c], -1) * (d[:, 3:4] / 2.0)
    ctr = d[:, 0:2]
    return np.stack([ctr + fwd + left, ctr + fwd - left, ctr - fwd - left, ctr - fwd + left], axis=1)
