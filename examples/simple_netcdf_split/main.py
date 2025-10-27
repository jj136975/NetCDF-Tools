import argparse
import os

from netcdf_tools import split

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process NetCDF intensity data')
    parser.add_argument('-i', '--input', type=str,
                        default=os.path.join('input', 'MethnolExtractant.cdf'),
                        help='Input filename')
    parser.add_argument('-o', '--output', type=str,
                        default='output',
                        help='Output filename')
    parser.add_argument('-s', '--noise_sec', type=float, default=50.0,
                        help='Number of seconds to use to delimit the noise (default: 50)')
    parser.add_argument('-m', '--noise_method', type=str, default='max',
                        choices=['max', 'sd'],
                        help='Noise calculation method: max or sd (default: max)')
    parser.add_argument('-f', '--noise_sd_factor', type=float, default=2.0,
                        help='mu + factor * sd (default: 2.0)')
    parser.add_argument('-n', '--noise_rollmean_n', type=int, default=15,
                        help='Number of points to average (default: 15)')

    args = parser.parse_args()
    split(
        input_file_path=args.input,
        output_dir_path=args.output,
        noise_sec=args.noise_sec,
        noise_method=args.noise_method,
        noise_sd_factor=args.noise_sd_factor,
        noise_rollmean_n=args.noise_rollmean_n
    )