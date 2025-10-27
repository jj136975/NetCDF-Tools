import os
import pathlib
import zipfile
from os import PathLike
from typing import Generator, Any

import matplotlib.pyplot as plt
import numpy as np
from netCDF4 import Dataset


def rolling_mean(arr, n):
    """Calculate rolling mean with center alignment"""
    if n % 2 == 0:
        n += 1  # Make it odd for center alignment

    pad_width = n // 2
    padded = np.pad(arr, pad_width, mode='constant', constant_values=np.nan)

    result = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        window = padded[i:i + n]
        result[i] = np.nanmean(window)

    return result


def export_range(nc: Dataset, start_idx: int, end_idx: int, output_filename: str, max_buffer: int) -> memoryview:
    point_idxs = nc.variables['scan_index']
    start_point = point_idxs[start_idx]
    end_point = point_idxs[end_idx]
    print("Start index:", start_idx, "End index:", end_idx)
    print("Start point:", start_point, "End point:", end_point)

    """Export a range of scans to a new NetCDF file"""
    out_nc = Dataset(output_filename, 'w', format='NETCDF4', diskless=True, memory=max_buffer)
    out_nc.setncatts({k: nc.getncattr(k) for k in nc.ncattrs()})

    # Copy dimensions
    for name, dimension in nc.dimensions.items():
        if dimension.isunlimited():
            out_nc.createDimension(name, None)
        elif name == 'scan_number':
            out_nc.createDimension(name, end_idx - start_idx)
        elif name == 'point_number':
            out_nc.createDimension(name, end_point - start_point)
        else:
            out_nc.createDimension(name, len(dimension))

    # Copy variables
    for name, variable in nc.variables.items():
        out_var = out_nc.createVariable(name, variable.datatype, variable.dimensions)
        # Copy variable attributes
        out_var.setncatts({k: variable.getncattr(k) for k in variable.ncattrs()})
        # Copy data for the specified range
        if 'scan_number' in variable.dimensions:
            if name == 'scan_index':
                out_var[:] = variable[start_idx:end_idx] - start_point
            elif name == 'actual_scan_number':
                out_var[:] = variable[start_idx:end_idx] - start_idx
            else:
                out_var[:] = variable[start_idx:end_idx]
        elif 'point_number' in variable.dimensions:
            out_var[:] = variable[start_point:end_point]
        else:
            out_var[:] = variable[:]

    return out_nc.close()


def find_ranges(arr: np.ndarray, threshold: float) -> Generator[tuple[int, int], None, None]:
    size = len(arr)
    i = 0

    while True:
        start = None
        while i < size - 1:
            if arr[i] <= threshold < arr[i + 1]:
                start = i
                break
            i += 1
        if start is None:
            return
        i += 1
        while i < size - 1:
            if arr[i - 1] > threshold >= arr[i]:
                break
            i += 1
        yield start, i
        i += 1


def show(output_file: PathLike, nc: Dataset, ranges: list[tuple[int, int]], rollmean: np.ndarray[tuple[int], Any],
         noise_lim: float) -> None:
    # Read variables
    total_intensity = nc.variables['total_intensity'][:]
    scan_acquisition_time = nc.variables['scan_acquisition_time'][:]

    # Create plot
    fig, ax = plt.subplots(sharex=True, figsize=(10, 6))

    # Plot total intensity
    ax.plot(scan_acquisition_time, total_intensity, color='grey', linewidth=1, label='Total Intensity')
    ax.scatter(scan_acquisition_time, total_intensity, s=1, alpha=0.5, color='grey')

    # Plot rolling mean (only non-nan values)
    valid_rollmean = ~np.isnan(rollmean)
    ax.plot(scan_acquisition_time[valid_rollmean], rollmean[valid_rollmean],
            color='blue', linewidth=1, alpha=0.5, label='Rolling Mean')

    # Plot noise limit horizontal line
    ax.axhline(y=noise_lim, color='black', linewidth=1)

    if ranges:
        # Vertical lines at crossing times
        for start, end in ranges:
            ax.axvline(x=scan_acquisition_time[start], color='green', alpha=0.5, linewidth=1)
            ax.axvline(x=scan_acquisition_time[end], color='red', alpha=0.5, linewidth=1)

    ax.set_xlabel('Scan Acquisition Time')
    ax.set_ylabel('Total Intensity')

    # Use classic theme-like styling
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')


def netcdf_split(input_file_path: str | PathLike, output_dir_path: str | PathLike, noise_sec: float, noise_method: str,
         noise_sd_factor: float, noise_rollmean_n: int):
    input_file = pathlib.Path(input_file_path)
    output_file = pathlib.Path(output_dir_path)

    if output_file.exists() and not output_file.is_dir():
        raise ValueError(f"Output path {output_file} exists but is not a directory")

    # Open NetCDF file
    nc = Dataset(input_file, 'r')

    # Read variables
    total_intensity = nc.variables['total_intensity'][:]
    scan_acquisition_time = nc.variables['scan_acquisition_time'][:]

    # Calculate rolling mean
    rollmean = rolling_mean(total_intensity, noise_rollmean_n)

    # Calculate noise limit
    noise_mask = scan_acquisition_time <= noise_sec

    if noise_method == 'sd':
        noise_data = total_intensity[noise_mask]
        noise_lim = np.mean(noise_data) + noise_sd_factor * np.std(noise_data)
    else:
        noise_lim = np.max(total_intensity[noise_mask])

    cross_idx_ranges = list(find_ranges(rollmean, noise_lim))

    # Export ranges to separate files
    if not os.path.isdir(output_file):
        os.mkdir(output_file)

    basename = os.path.basename(input_file.name.split('.')[0])
    file_size = os.path.getsize(input_file)

    zip_file = zipfile.ZipFile(output_file.joinpath(f"{basename}_split.zip"), 'w', zipfile.ZIP_DEFLATED)

    for i, (start_idx, end_idx) in enumerate(cross_idx_ranges):
        output_filename = f"{basename}_range_{i + 1}.cdf"
        data = export_range(nc, start_idx, end_idx, output_filename, file_size)
        zip_file.writestr(output_filename, data)
        print(f"Exported range {i + 1}: scans {start_idx} to {end_idx} to {output_filename}")

    show(output_file.joinpath("plot_intensity.png"), nc, cross_idx_ranges, rollmean, noise_lim)

    # Close NetCDF file
    nc.close()
