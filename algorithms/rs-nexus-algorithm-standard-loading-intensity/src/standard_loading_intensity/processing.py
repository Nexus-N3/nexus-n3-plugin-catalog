"""Signal processing utilities for loading intensity computation."""

import numpy as np
import math
from scipy.signal import butter, filtfilt, lfilter

def vector_magnitude(vectors):
    """
    Compute vector magnitude across axis arrays.

    Args:
        vectors: List of arrays for each axis.

    Returns:
        Array of magnitudes.
    """
    n = len(vectors[0])
    assert all(len(v) == n for v in vectors), "Vectors have different lengths"
    vm = np.sqrt(sum(v ** 2 for v in vectors))
    return vm

def build_filter(frequency, sample_rate, filter_type, filter_order):
    """
    Build a Butterworth filter.

    Args:
        frequency: Cutoff frequency or band tuple.
        sample_rate: Sampling rate in Hz.
        filter_type: "bandpass", "low", or "high".
        filter_order: Filter order.

    Returns:
        Tuple of (b, a) filter coefficients.
    """
    nyq = 0.5 * sample_rate

    if filter_type == "bandpass":
        nyq_cutoff = (frequency[0] / nyq, frequency[1] / nyq)
        b, a = butter(filter_order, (frequency[0], frequency[1]), btype=filter_type, analog=False, output='ba', fs=sample_rate)
    elif filter_type == "low":
        nyq_cutoff = frequency[1] / nyq
        b, a = butter(filter_order, frequency[1], btype=filter_type, analog=False, output='ba', fs=sample_rate)
    else:
        nyq_cutoff = frequency / nyq

    return b, a

def filter_signal(b, a, signal, filter):
    """
    Apply a filter to a signal.

    Args:
        b: Filter numerator coefficients.
        a: Filter denominator coefficients.
        signal: Input signal array.
        filter: "lfilter" or "filtfilt".

    Returns:
        Filtered signal.
    """
    if(filter=="lfilter"):
        return lfilter(b, a, signal)
    elif(filter=="filtfilt"):
        return filtfilt(b, a, signal)

def bandpass_filter(data, l_cut_off, high_cut_off, fs, order):
    """
    Apply a bandpass filter to data.

    Args:
        data: Input signal array.
        l_cut_off: Low cutoff frequency.
        high_cut_off: High cutoff frequency.
        fs: Sampling rate in Hz.
        order: Filter order.

    Returns:
        Filtered signal array.
    """
    b,a = build_filter((l_cut_off,high_cut_off), fs,"bandpass", order) # fs is specified so l and h cut off are in hz
    data_f = filter_signal(b,a,data, "filtfilt")
    return data_f

def highpass_filter(data, cutoff=0.25, fs=60, order=5):
    """
    Apply a high-pass filter to data.

    Args:
        data: Input signal array.
        cutoff: Cutoff frequency in Hz.
        fs: Sampling rate in Hz.
        order: Filter order.

    Returns:
        Filtered signal array.
    """
    b, a = butter(order, cutoff, btype='high', fs=fs, analog=False)
    filtered = filtfilt(b, a, data)
    return filtered

def lowpass_filter(data, cutoff=20, fs=60, order=4):
    """
    Apply a low-pass filter to data.

    Args:
        data: Input signal array.
        cutoff: Cutoff frequency in Hz.
        fs: Sampling rate in Hz.
        order: Filter order.

    Returns:
        Filtered signal array.
    """
    b, a = butter(order, cutoff, btype='low', fs=fs, analog=False)
    filtered = filtfilt(b, a, data)
    return filtered

def normalise_gravity(ax, ay, az, gravity):
    """
    Normalize acceleration by gravity.

    Args:
        ax: X-axis array.
        ay: Y-axis array.
        az: Z-axis array.
        gravity: Gravity constant for normalization.

    Returns:
        Tuple of normalized (ax, ay, az).
    """
    try:
        g = float(gravity)
    except (TypeError, ValueError):
        g = 9.80665
    if abs(g) < 1e-9:
        # Zero-g mode: keep raw acceleration values (no normalization).
        return ax, ay, az
    return ax / g, ay / g, az / g

def extract_axes(data_block):
    """
    Extract axis arrays from a sample block.

    Args:
        data_block: Iterable of samples with accel vectors.

    Returns:
        Tuple of (ax, ay, az) arrays.
    """
    ax = np.array([s.accel[0] for s in data_block])
    ay = np.array([s.accel[1] for s in data_block])
    az = np.array([s.accel[2] for s in data_block])

    return ax, ay, az

def pre_filter_axes(ax, ay, az, amag, sampling_rate, low_cutoff, high_cutoff, order):
    """
    Apply low-pass filtering to axes and magnitude.

    Args:
        ax: X-axis array.
        ay: Y-axis array.
        az: Z-axis array.
        amag: Magnitude array.
        sampling_rate: Sampling rate in Hz.
        low_cutoff: Low-pass cutoff frequency.
        high_cutoff: High-pass cutoff frequency.
        order: Filter order.

    Returns:
        Tuple of filtered (ax, ay, az, amag).
    """
    #bandpass_filter(data, l_cut_off, high_cut_off, fs, order)
    ax_f = bandpass_filter(ax, low_cutoff, high_cutoff, sampling_rate, order)
    ay_f = bandpass_filter(ay, low_cutoff, high_cutoff, sampling_rate, order)
    az_f = bandpass_filter(az, low_cutoff, high_cutoff, sampling_rate, order)
    amag_f = bandpass_filter(amag, low_cutoff, high_cutoff, sampling_rate, order)

    return ax_f, ay_f, az_f, amag_f

def compute_fft_mag(data):
    """
    Compute FFT magnitudes for a signal.

    Args:
        data: Input signal array.

    Returns:
        List of magnitudes from DC to Nyquist.
    """
    fftpoints = int(math.pow(2, math.ceil(math.log2(len(data)))))
    if fftpoints < 512:
        fftpoints = 512
    fft = np.fft.fft(data, n=fftpoints)
    mag = np.abs(fft) / (fftpoints / 2)
    mag_half = mag[:fftpoints // 2 + 1]  # Only DC to Nyquist
    return mag_half.tolist()

def compute_loading_intensity(fft_magnitudes, sampling_frequency, low_cut_off, high_cut_off):
    """
    Compute loading intensity from FFT magnitudes.

    Args:
        fft_magnitudes: Magnitude spectrum values.
        sampling_frequency: Sampling rate in Hz.
        low_cut_off: Low cutoff frequency.
        high_cut_off: High cutoff frequency.

    Returns:
        Loading intensity scalar.
    """
    N = 2 * (len(fft_magnitudes) - 1)  # Original FFT length
    fs = sampling_frequency

    kl = int(N / fs * low_cut_off)
    kc = int(N / fs * high_cut_off) + 1

    kl = max(0, kl)
    kc = min(len(fft_magnitudes), kc)

    f = [fs * i / N for i in range(len(fft_magnitudes))]

    LI = 0
    for k in range(kl, kc):
        LI += fft_magnitudes[k] * f[k]

    return LI


def compute_li_for_signal(signal, sampling_rate, f_band):
    """
    Compute loading intensity for a signal and frequency band.

    Args:
        signal: Input signal array.
        sampling_rate: Sampling rate in Hz.
        f_band: Tuple of (low, high) cutoff frequencies.

    Returns:
        Loading intensity scalar.
    """
    fft_mag = compute_fft_mag(signal)
    return compute_loading_intensity(
        fft_mag,
        sampling_rate,
        f_band[0],
        f_band[1]
    )
