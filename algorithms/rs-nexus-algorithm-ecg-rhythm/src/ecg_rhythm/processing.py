import numpy as np
from scipy.signal import butter, filtfilt


def bandpass_filter(x: np.ndarray, fs: float, low_hz: float, high_hz: float, order: int = 4) -> np.ndarray:
    b, a = butter(order, [low_hz, high_hz], btype="bandpass", fs=fs)
    padlen = 3 * (max(len(a), len(b)) - 1)
    if len(x) <= padlen:
        return x
    return filtfilt(b, a, x)


def moving_average(x: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return x
    kernel = np.ones(win, dtype=float) / float(win)
    return np.convolve(x, kernel, mode="same")


def detrend_ma(x: np.ndarray, fs: float, window_seconds: float) -> np.ndarray:
    win = max(1, int(window_seconds * fs))
    baseline = moving_average(x, win)
    return x - baseline


def _smooth_envelope(x: np.ndarray, fs: float, smooth_ms: float) -> np.ndarray:
    win = max(1, int((smooth_ms / 1000.0) * fs))
    return moving_average(x, win)


def detect_rpeaks_derivative_energy(
    x: np.ndarray,
    t_ms: np.ndarray,
    fs: float,
    qrs_smooth_ms: float = 100.0,
    refractory_ms: float = 250.0,
    k: float = 3.0,
) -> list[float]:
    """
    Lightweight QRS detection for streaming:
      derivative -> abs -> smooth -> adaptive threshold
      + refractory period to prevent double-counting.
    Returns list of R-peak timestamps (ms).
    """
    if len(x) < 10:
        return []

    dx = np.diff(x, prepend=x[0])
    env = np.abs(dx)
    env = _smooth_envelope(env, fs, qrs_smooth_ms)

    med = float(np.median(env))
    thr = k * med if med > 0 else float(np.mean(env) + 3.0 * np.std(env))

    refractory_samples = int((refractory_ms / 1000.0) * fs)

    peaks: list[float] = []
    i = 0
    n = len(env)

    while i < n:
        if env[i] > thr:
            # Search local max over a short window (~120ms)
            j_end = min(n, i + int(0.12 * fs))
            j = i + int(np.argmax(env[i:j_end]))
            peaks.append(float(t_ms[j]))
            i = j + refractory_samples
        else:
            i += 1

    return peaks


def compute_rr_ms(rpeaks_ms: list[float]) -> np.ndarray:
    if len(rpeaks_ms) < 2:
        return np.array([], dtype=float)
    return np.diff(np.array(rpeaks_ms, dtype=float))


def rr_features(rr_ms: np.ndarray):
    if rr_ms.size < 2:
        return None
    rr_mean = float(np.mean(rr_ms))
    sdnn = float(np.std(rr_ms, ddof=1)) if rr_ms.size >= 2 else 0.0
    diffs = np.diff(rr_ms)
    rmssd = float(np.sqrt(np.mean(diffs * diffs))) if diffs.size > 0 else 0.0
    cvrr = float(sdnn / rr_mean) if rr_mean > 0 else None
    return rr_mean, sdnn, rmssd, cvrr


def hr_from_rr(rr_ms: np.ndarray) -> np.ndarray:
    if rr_ms.size == 0:
        return np.array([], dtype=float)
    return 60000.0 / rr_ms


def ectopy_flags(rr_ms: np.ndarray, short_ratio: float = 0.75, long_ratio: float = 1.20) -> int:
    """
    Simple premature beat suspicion: short RR followed by long RR.
    Returns count of such patterns.
    """
    if rr_ms.size < 3:
        return 0
    med = float(np.median(rr_ms))
    if med <= 0:
        return 0

    count = 0
    for i in range(rr_ms.size - 1):
        if rr_ms[i] < short_ratio * med and rr_ms[i + 1] > long_ratio * med:
            count += 1
    return count


def compute_sqi(
    x_raw: np.ndarray,
    x_detrended: np.ndarray,
    rpeaks_ms: list[float],
    cfg: dict,
    present_fraction: float | None = None,
) -> dict:
    """
    SQI gating:
      - missing sample presence
      - plausible beat count
      - noise proxies (baseline_std, diff_std)
      - optional clipping
    """
    if not cfg.get("enabled", True):
        return {
            "is_valid": True,
            "reason": None,
            "beats_in_window": len(rpeaks_ms),
            "present_fraction": float(present_fraction) if present_fraction is not None else None,
        }
    beats = len(rpeaks_ms)

    # Missing sample gating (optional)
    miss_cfg = cfg.get("missing_samples", {})
    if miss_cfg.get("enabled", False) and present_fraction is not None:
        if present_fraction < float(miss_cfg.get("min_fraction_present", 0.9)):
            return {
                "is_valid": False,
                "reason": "too_many_missing_samples",
                "beats_in_window": beats,
                "present_fraction": float(present_fraction),
            }

    # Beat count gating
    br = cfg.get("beats_required", {})
    min_b = int(br.get("min_beats_per_window", 4))
    max_b = int(br.get("max_beats_per_window", 40))

    if beats < min_b:
        return {
            "is_valid": False,
            "reason": "too_few_beats",
            "beats_in_window": beats,
            "present_fraction": float(present_fraction) if present_fraction is not None else None,
        }
    if beats > max_b:
        return {
            "is_valid": False,
            "reason": "too_many_beats",
            "beats_in_window": beats,
            "present_fraction": float(present_fraction) if present_fraction is not None else None,
        }

    baseline_std = float(np.std(x_raw - x_detrended))
    diff_std = float(np.std(np.diff(x_detrended))) if len(x_detrended) > 2 else 0.0

    # Optional clipping check
    clip_frac = None
    clip_cfg = cfg.get("clipping", {})
    if clip_cfg.get("enabled", False):
        rail_min = float(clip_cfg["rail_min"])
        rail_max = float(clip_cfg["rail_max"])
        near = float(clip_cfg.get("near_rail_fraction", 0.01))
        lo = rail_min + near * (rail_max - rail_min)
        hi = rail_max - near * (rail_max - rail_min)
        clip_frac = float(np.mean((x_raw <= lo) | (x_raw >= hi)))
        if clip_frac > 0.01:
            return {
                "is_valid": False,
                "reason": "clipping",
                "beats_in_window": beats,
                "baseline_std": baseline_std,
                "diff_std": diff_std,
                "clipping_fraction": clip_frac,
                "present_fraction": float(present_fraction) if present_fraction is not None else None,
            }

    return {
        "is_valid": True,
        "reason": None,
        "beats_in_window": beats,
        "baseline_std": baseline_std,
        "diff_std": diff_std,
        "clipping_fraction": clip_frac,
        "present_fraction": float(present_fraction) if present_fraction is not None else None,
    }
