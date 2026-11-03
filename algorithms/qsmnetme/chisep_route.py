"""The χ-separation toolbox v1.1.3's `chi_sepnet_general` route (SNU-LIST), in NumPy + ONNX Runtime.

Shared by the `chisepnet` and `qsmnetme` entries (this file is identical in both folders;
tests/test_chisep_route.py checks that).

The toolbox (Kim et al., χ-sepnet, Hum Brain Mapp 2025, doi:10.1002/hbm.70136; Jongho Lee's lab)
ships `chi_sepnet_general` as protected P-code and runs its networks through MATLAB's ONNX importer,
which no container here can hold. With the authors' permission (the EMTP parity initiative) the
route was recovered by black-box probing in licensed MATLAB R2023b on Bunya (astewartau/QSM.rs#377,
2026-11-03): spies on `interp3` and on the networks (a real DAGNetwork whose spy layer saved its input
and returned the real graph's output from ONNX Runtime), each saving its caller's whole workspace, on
64x60x48 volumes at 0.8x0.9x1.1 and 1 mm, B0 tilted and along z, R2' and R2* inputs; the frame sizes
on twelve more grids, and CalculateRotMat on eleven directions. This file reproduces those runs to
1.4e-5 to 2.1e-5 % NRMSE on chi+ and chi- (max |d| 6e-8 ppm), the rounding of ONNX Runtime's thread
count. The route:

1. Rotation: CalculateRotMat(B0_dir) rotates by acos(b.z) about z x b (R z = b); b is unit here.
2. Grids: acquired coordinates -fov_h : vs : fov_h per array axis, fov_h = (N-1) vs / 2; the frame
   has M = 16 ceil(n / 16) nodes at -(M-1)/2 .. (M-1)/2 mm, n = floor((N-1) vs) + 1.
3. Frame node p reads the acquired volume at R p: interp3 'spline' (extrapolating) for the field
   and R2'/R2*, 'linear' > 0.5 for the mask.
4. QSMnetME (240904_QSMnet.onnx): input (field_Hz/(CF 1e-6) - field_mean)/field_std, 0 outside the
   frame mask, the whole frame in one pass; QSM = cosmos_sus_std y + cosmos_sus_mean, masked.
5. R2' channel: (R2'/Dr - r2prime_mean)/r2prime_std for a measured R2', or for R2* R2PRIMEnet's raw
   z-scored output on (R2*/Dr - r2star_mean)/r2star_std (R2* not clipped, R2PRIMEnet's output not
   clipped before chi-sepnet), masked.
6. chi-sepnet (240904_xsepnet.onnx) on [ (QSM - cosmos_sus_mean)/cosmos_sus_std, field channel,
   R2' channel ]; chi+- = max(std y + mean, 0) masked.
7. Back: acquired voxel x reads each map at inv(R) x, interp3 'spline'; max(., 0), times the mask.
   chi_total = chi+ - |chi-|. (The script's comment says this branch returns 1 mm maps; the P-code
   returns them on the acquired grid.)

The networks are the toolbox's own files. Their declared input is a fixed 192x192x128 patch; the
toolbox replaces the input layer to fit the frame (layerGraph), and ONNX Runtime needs the same, so
`load_net` re-declares the spatial axes dynamic in memory (weights and nodes untouched: the graphs
are fully convolutional, and the output at the declared shape is identical).
"""
import math
import numpy as np

NORM = dict(  # xsepnet_train_patch_norm_factor_inplane_largedegree_romeo_arlo.mat (float32 values)
    cosmos_sus_mean=-0.0013402086915448308, cosmos_sus_std=0.031504031270742416,
    field_mean=-0.0026045702397823334, field_std=0.010849659331142902,
    r2prime_mean=0.05141879618167877, r2prime_std=0.06977531313896179,
    r2star_mean=0.15865366160869598, r2star_std=0.07501979172229767,
    x_pos_mean=0.025912819430232048, x_pos_std=0.03526417911052704,
    x_neg_mean=0.026700690388679504, x_neg_std=0.027936099097132683,
)


def load_norm(path=None):
    """The normalisation file's values (NORM holds the same numbers)."""
    import os
    import scipy.io as sio
    path = path or os.path.join(models_dir(), NORM_FILE)
    d = sio.loadmat(path)
    return {k: float(np.asarray(v).ravel()[0]) for k, v in d.items() if not k.startswith('__')}


def rot_mat(b0):
    """CalculateRotMat for a unit B0 direction: the rotation by acos(b·z) about z×b, mapping z to
    b (MATLAB's matches this to rounding for unit vectors). b = −z is NaN in the toolbox."""
    b = np.asarray(b0, float).ravel()
    b = b / np.linalg.norm(b)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(z, b)
    s = np.linalg.norm(v)
    c = float(b @ z)
    if s < 1e-15:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / s ** 2)


def native_axes(N, vs):
    """Native sample coordinates per array axis (mm): -fov_h : vs : fov_h, fov_h = (N-1)·vs/2."""
    return [(-(n - 1) * v / 2) + np.arange(n) * v for n, v in zip(N, vs)]


def resampled_size(N, vs, res=1.0):
    """length(-fov_h:res:fov_h) rounded up to a multiple of 16."""
    out = []
    for n, v in zip(N, vs):
        m = math.floor((n - 1) * v / res + 1e-9) + 1
        out.append(16 * math.ceil(m / 16))
    return out


def grid_points(axes):
    g = np.meshgrid(*axes, indexing='ij')
    return np.stack([a.ravel(order='F') for a in g])  # 3 × n, array-axis order


def _nak_M(v, h, axis):
    v = np.moveaxis(v, axis, 0)
    n = v.shape[0]
    if n == 2:
        M = np.zeros_like(v)
    elif n == 3:
        M = np.broadcast_to((v[0] - 2 * v[1] + v[2]) / h ** 2, v.shape).copy()
    else:
        A = np.zeros((n, n))
        A[0, :3] = [1, -2, 1]
        A[-1, -3:] = [1, -2, 1]
        for i in range(1, n - 1):
            A[i, i - 1:i + 2] = [1, 4, 1]
        b = np.zeros(v.shape)
        b[1:-1] = 6 / h ** 2 * (v[:-2] - 2 * v[1:-1] + v[2:])
        M = np.linalg.solve(A, b.reshape(n, -1)).reshape(v.shape)
    return np.moveaxis(M, 0, axis)


def spline(V, axes, q):
    """MATLAB interp3(..., 'spline') at points q (3 × n): tensor not-a-knot spline, extrapolating."""
    o = [a[0] for a in axes]
    h = [a[1] - a[0] for a in axes]
    A = {0: V}
    A[1] = _nak_M(V, h[0], 0)
    A[2] = _nak_M(V, h[1], 1)
    A[4] = _nak_M(V, h[2], 2)
    A[3] = _nak_M(A[1], h[1], 1)
    A[5] = _nak_M(A[1], h[2], 2)
    A[6] = _nak_M(A[2], h[2], 2)
    A[7] = _nak_M(A[3], h[2], 2)
    J, W = [], []
    for d in range(3):
        n = V.shape[d]
        u = (q[d] - o[d]) / h[d]
        j = np.clip(np.floor(u), 0, n - 2).astype(int)
        t = u - j
        w = 1 - t
        c = h[d] ** 2 / 6
        J.append(j)
        W.append([(0, 0, w), (1, 0, t), (0, 1, c * (w ** 3 - w)), (1, 1, c * (t ** 3 - t))])
    r = np.zeros(q.shape[1])
    for dz, mz, wz in W[2]:
        for dy, my, wy in W[1]:
            for dx, mx, wx in W[0]:
                r += wx * wy * wz * A[mx | (my << 1) | (mz << 2)][J[0] + dx, J[1] + dy, J[2] + dz]
    return r


def linear(V, axes, q):
    """MATLAB interp3(..., 'linear'): NaN outside the grid."""
    o = [a[0] for a in axes]
    h = [a[1] - a[0] for a in axes]
    J, T, bad = [], [], np.zeros(q.shape[1], bool)
    for d in range(3):
        n = V.shape[d]
        u = (q[d] - o[d]) / h[d]
        bad |= ~((u >= 0) & (u <= n - 1))
        j = np.clip(np.floor(u), 0, n - 2).astype(int)
        J.append(j)
        T.append(u - j)
    r = np.zeros(q.shape[1])
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                w = (T[0] if dx else 1 - T[0]) * (T[1] if dy else 1 - T[1]) * (T[2] if dz else 1 - T[2])
                r += w * V[np.minimum(J[0] + dx, V.shape[0] - 1), np.minimum(J[1] + dy, V.shape[1] - 1),
                           np.minimum(J[2] + dz, V.shape[2] - 1)]
    r[bad] = np.nan
    return r


def _f(a, shape):
    return a.reshape(shape, order='F')


def forward(field_hz, map_hz, mask, vs, b0, R=None):
    """Resample onto the rotated, centred 1 mm grid (chi_sepnet_general)."""
    N = field_hz.shape
    R = rot_mat(b0) if R is None else R
    nat = native_axes(N, vs)
    M = resampled_size(N, vs)
    samp = [-(m - 1) / 2 + np.arange(m) for m in M]
    q = R @ grid_points(samp)
    lf = _f(spline(field_hz, nat, q), M)
    mp = _f(spline(map_hz, nat, q), M) if map_hz is not None else None
    mk = _f(linear(mask.astype(float), nat, q), M)
    mk = np.nan_to_num(mk) > 0.5
    return lf, mp, mk, dict(R=R, nat=nat, samp=samp, M=M, N=N)


def backward(V, geo):
    """Map a 1 mm-grid map back onto the native grid (inv(R) · native points, spline)."""
    qi = np.linalg.inv(geo['R']) @ grid_points(geo['nat'])
    return _f(spline(V, geo['samp'], qi), geo['N'])


def _run(net, x):
    return np.asarray(net(x[None, None].astype(np.float32) if x.ndim == 3 else x[None].astype(np.float32)),
                      dtype=np.float64)[0]


def qsmnetme_1mm(lf_hz, mk, CF, nets, norm=NORM):
    """QSMnetME on the resampled grid: Hz → ppm (CF/1e6), z-score with the field stats, mask,
    network, de-normalise with the COSMOS stats, mask."""
    x = ((lf_hz / (CF * 1e-6) - norm['field_mean']) / norm['field_std']) * mk
    y = _run(nets['qsmnet'], x)[0]
    return (y * norm['cosmos_sus_std'] + norm['cosmos_sus_mean']) * mk, x


def route(field_hz, map_hz, mask, Dr, b0, CF, vs, have_r2prime, nets, norm=NORM, R=None):
    lf, mp, mk, geo = forward(field_hz, map_hz, mask, vs, b0, R)
    qsm, x_lf = qsmnetme_1mm(lf, mk, CF, nets, norm)
    if have_r2prime:
        ch2 = ((mp / Dr - norm['r2prime_mean']) / norm['r2prime_std']) * mk
    else:
        xr = ((mp / Dr - norm['r2star_mean']) / norm['r2star_std']) * mk   # R2* not clipped
        ch2 = _run(nets['r2primenet'], xr)[0] * mk                         # raw z-scored R2'
    ch0 = ((qsm - norm['cosmos_sus_mean']) / norm['cosmos_sus_std']) * mk
    y = _run(nets['xsepnet'], np.stack([ch0, x_lf, ch2]))
    xp1 = np.maximum(y[0] * norm['x_pos_std'] + norm['x_pos_mean'], 0) * mk
    xn1 = np.maximum(y[1] * norm['x_neg_std'] + norm['x_neg_mean'], 0) * mk
    m = mask.astype(bool)
    xp = np.maximum(backward(xp1, geo), 0) * m
    xn = np.maximum(backward(xn1, geo), 0) * m
    q_native = backward(qsm, geo) * m
    return xp, xn, xp - xn, q_native, dict(geo=geo, lf=lf, mp=mp, mk=mk, qsm1=qsm, xp1=xp1, xn1=xn1, ch=[ch0, x_lf, ch2])


def qsmnetme(field_hz, mask, b0, CF, vs, nets, norm=NORM, R=None):
    """Standalone QSMnetME: the toolbox's forward route, QSMnetME, and the toolbox's backward
    mapping (the one it applies to χ-sepnet's maps), masked."""
    lf, _, mk, geo = forward(field_hz, None, mask, vs, b0, R)
    qsm, _ = qsmnetme_1mm(lf, mk, CF, nets, norm)
    return backward(qsm, geo) * mask.astype(bool)


FILES = dict(qsmnet='240904_QSMnet.onnx', r2primenet='240531_R2PRIMEnet.onnx', xsepnet='240904_xsepnet.onnx')
NORM_FILE = 'xsepnet_train_patch_norm_factor_inplane_largedegree_romeo_arlo.mat'


def models_dir():
    """$XSEPNET_MODELS (baked into the image), else next to this file, else $CHISEP_TOOLBOX/models."""
    import os
    env = os.environ.get('XSEPNET_MODELS')
    if env and os.path.exists(os.path.join(env, FILES['xsepnet'])):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(here, FILES['xsepnet'])):
        return here
    return os.path.join(os.environ.get('CHISEP_TOOLBOX', '.'), 'models')


def load_net(path, threads=0):
    """A toolbox network with its spatial axes re-declared dynamic (in memory), as a callable on
    NCDHW float32."""
    import onnx
    import onnxruntime as ort
    m = onnx.load(path)
    for vals in (m.graph.input, m.graph.output):
        for v in vals:
            dims = v.type.tensor_type.shape.dim
            for k, name in zip((2, 3, 4), ('D', 'H', 'W')):
                dims[k].ClearField('dim_value')
                dims[k].dim_param = name
    o = ort.SessionOptions()
    if threads:
        o.intra_op_num_threads = threads
    s = ort.InferenceSession(m.SerializeToString(), o, providers=['CPUExecutionProvider'])
    n = s.get_inputs()[0].name
    return lambda x: s.run(None, {n: x})[0]


def toolbox_nets(model_dir=None, which=('qsmnet', 'r2primenet', 'xsepnet'), threads=0):
    import os
    d = model_dir or models_dir()
    return {k: load_net(os.path.join(d, FILES[k]), threads) for k in which}
