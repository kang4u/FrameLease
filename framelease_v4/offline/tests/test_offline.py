"""Tests of the v4 offline lease ablation (CPU, seconds).

    cd /home/kang/Desktop/DAC
    .conda-unidrive-linux/bin/python -I -B -m pytest -q framelease_v4/offline/tests
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framelease_v2.lease import EgoShape, LeaseParams, compute_lease, lease_geometry  # noqa: E402
from framelease_v4.offline import analyze as A  # noqa: E402
from framelease_v4.offline import common as C  # noqa: E402
from framelease_v4.offline import stage_frames as S  # noqa: E402

EGO = EgoShape(2.4462, 0.9184, (0.0, 0.3837))


def fake_clip(V, censored, v0=None, speed=None, status=None):
    n = len(V)
    return {'V': np.asarray(V, dtype=float), 'censored': np.asarray(censored, dtype=bool),
            'v0': np.zeros(n, dtype=bool) if v0 is None else np.asarray(v0, dtype=bool),
            'speed': np.ones(n) if speed is None else np.asarray(speed, dtype=float),
            'bind_status': np.zeros(n, dtype=np.int16) if status is None else np.asarray(status, dtype=np.int16)}


def test_metric_definitions_by_hand():
    # plans: V = 3 (censored, V_suf 2.5), V = 1.2 (V_suf 0.7), V = 0.3 (V_suf 0), V = 2.6 (V_suf 2.1)
    d = fake_clip([3.0, 1.2, 0.3, 2.6], [True, False, False, False], status=[0, 1, 3, 1])
    H = np.array([[2.5, 1.0], [0.5, 1.0], [0.0, 1.0], [2.2, 1.0]])     # two candidates
    s = A.clip_sums(H, d, np.ones(4, dtype=bool))
    # candidate 0: violations only at plan 3 (2.2 > 2.1); candidate 1 (H = 1): plans 1 (1 > 0.7), 2 (1 > 0)
    assert s['over'].tolist() == [1, 2]
    assert s['overc'].tolist() == [1, 2]
    assert s['conf'].tolist() == [3, 3]
    assert s['miss_undetected'].tolist() == [0, 1] and s['miss_confident'].tolist() == [1, 1]
    # utilization: plans with V_suf > 0 are 0, 1, 3: cand 0 -> 2.5/2.5, 0.5/0.7, 2.1/2.1 ; cand 1 -> 1/2.5, 0.7/0.7, 1/2.1
    assert s['npos'][0] == 3
    assert s['sum_u'][0] == pytest.approx(1 + 0.5 / 0.7 + 1)
    assert s['sum_u'][1] == pytest.approx(1 / 2.5 + 1 + 1 / 2.1)
    # need 0.964: oracle = V_suf >= need -> plans 0, 3; continuity cand 0 -> plans 0, 3; cand 1 -> all 4
    assert s[('oracle', 'fast')].tolist() == [2, 2]
    assert s[('cont', 'fast')].tolist() == [2, 4]
    assert s[('prem', 'fast')].tolist() == [0, 0]
    # need 1.842: oracle plans 0 (2.5), 3 (2.1); cand 1 (H = 1) refreshes both prematurely
    assert s[('prem', 'meas')].tolist() == [0, 2]
    assert s[('unsafe_cont', 'meas')].tolist() == [0, 0]


def test_choose_rule_and_fallback():
    cont = np.array([0.0, 0.5, 0.5, 0.9])
    est = np.array([0.0, 0.04, 0.03, 0.2])
    assert A.choose(cont, est, 0.05) == 2          # max continuity, tie -> lower risk
    assert A.choose(cont, est, 0.01) == 0
    assert A.choose(cont, np.array([0.1, 0.2, 0.3, 0.4]), 0.05) is None


def test_chosen_sums_fallback_is_zero_lease():
    d = fake_clip([3.0, 0.4], [True, False])
    H = np.array([[0.0, 2.0], [0.0, 2.0]])
    s = A.clip_sums(H, d, np.ones(2, dtype=bool))
    S1 = A.chosen_sums({k: v[None, :] for k, v in s.items()}, [0], [None])
    assert S1['over'][0, 0] == 0 and S1[('cont', 'fast')][0, 0] == 0 and S1['sum_u'][0, 0] == 0


def test_nested_choice_ignores_held_out_clip():
    rng = np.random.default_rng(0)
    K, Cn = 6, 5
    Sv = {k: rng.integers(1, 30, size=(Cn, K)).astype(float) for k in A.KEYS0}
    for k in A.KEYS1:
        for nk in A.NEED_KEYS:
            Sv[(k, nk)] = rng.integers(1, 30, size=(Cn, K)).astype(float)

    def fold_choice(Sv_, i):
        tot = {key: arr.sum(0) for key, arr in Sv_.items()}
        loo = {key: (tot[key] - Sv_[key][i])[None, :] for key in Sv_}
        c_ = A.metric_values(loo, 'continuity', 'fast', np.ones((1, 1)))[0]
        e_ = A.metric_values(loo, 'R_cond', 'fast', np.ones((1, 1)))[0]
        return A.choose(c_, e_, 0.5)

    base = fold_choice(Sv, 2)
    Sv2 = {k: v.copy() for k, v in Sv.items()}
    for k in Sv2:
        Sv2[k][2] = Sv2[k][2] * 7 + 3                  # change only the held-out clip
    assert fold_choice(Sv2, 2) == base


def _scene():
    plan = np.stack([np.zeros(6), 2.0 * np.arange(1, 7)], axis=1)          # straight ahead, 4 m/s (y forward)
    dets = np.array([[3.2, 8.0, 4.5, 1.9, np.pi / 2, 0.0, 0.0],            # parked car to the right, ahead
                     [-6.0, 14.0, 4.5, 1.9, 0.0, 2.0, 0.0],                # crossing car from the left
                     [2.5, 3.0, 0.6, 0.6, 0.0, 0.0, 0.0]])                 # pedestrian near the path
    return plan, dets, np.array([0.9, 0.5, 0.2]), np.array([0, 0, 7])


@pytest.mark.parametrize('lam', [0.0, 0.3, 1.0])
def test_global_kernel_matches_v2_compute_lease(lam):
    env = {'sigma_m': {'vehicle': 1.16 * lam, 'pedestrian': 1.46 * lam},
           'vbar_mps': {'vehicle': 1.84 * lam, 'pedestrian': 0.97 * lam},
           'abar_mps2': {'vehicle': 1.72 * lam, 'pedestrian': 0.0}}
    prm = C.sle.iso_params(env)
    plan, dets, sc, lab = _scene()
    geom = lease_geometry(plan, dets, sc, lab, EGO, C.sle.base_params())
    mine = min(S.global_H(geom, prm), 2.0)
    d = prm.to_dict()
    d.update(margin_mode='global', h_max_s=2.0)
    ref = compute_lease(plan, dets, sc, lab, EGO, LeaseParams.from_dict(d))['lease_s']
    assert mine == pytest.approx(ref, abs=1e-12)


def test_suffix_lease_semantics():
    env = {'sigma_m': {'vehicle': 0.5, 'pedestrian': 0.5}, 'vbar_mps': {'vehicle': 1.0, 'pedestrian': 1.0},
           'abar_mps2': {'vehicle': 0.5, 'pedestrian': 0.5}}
    prm = C.sle.iso_params(env)
    plan, dets, sc, lab = _scene()
    geom = lease_geometry(plan, dets, sc, lab, EGO, C.sle.base_params())
    ts = S.suffix_tau(geom, prm)
    # literal Eq. (1)-(2) on the 0.05 s grid from the per-agent conservative margins
    tau = geom.tau
    sig = np.array([prm.sigma_m[g] for g in geom.group])
    vb = np.array([prm.vbar_mps[g] for g in geom.group])
    ab = np.array([prm.abar_mps2[g] for g in geom.group])
    cm = (geom.clearance - (vb[:, None] * tau + 0.5 * ab[:, None] * tau ** 2 + sig[:, None])).min(axis=0)
    i_lit = C.sle.literal_H(cm, C.DT, C.T_C)
    H = float(np.clip(ts - C.T_C, 0.0, C.HBAR))
    assert abs(H - i_lit * C.DT) <= C.DT + 1e-9        # exact crossing lies within one grid step of the grid answer
    # the whole-horizon control certifies only if no crossing within T_pred
    assert (ts >= C.T_PRED - 1e-9) == bool((cm > C.DELTA).all())


def test_designs_share_frames_and_caps():
    lists = C.load_lists()
    d = S.load_clip(lists['val'][0])
    for des in ('GLOBAL', 'SUFFIX', 'GLOBAL_TAU', 'GLOBAL_c2'):
        names, _, H = A.candidates(des, d)
        assert H.shape == (len(d['V']), len(names)) and names[0] == 'ZERO'
        assert np.all(H[:, 0] == 0) and H.max() <= C.HBAR + 1e-12
    _, _, Hc2 = A.candidates('GLOBAL_c2', d)
    assert Hc2.max() <= 2.0 + 1e-12
    names, knobs, H = A.candidates('AGE', d)
    assert np.allclose(H[0], C.T_AGE_GRID) and knobs[0] == 0.0
