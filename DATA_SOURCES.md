# Data sources

The core benchmark uses ANU, IBM Belem, and IBM Quito byte streams. These are quantum random-number data, not packet or telemetry captures. Stored input files encode keys as little-endian unsigned 32-bit integers; the configured query universe is either 16 or 32 bits.

- **ANU:** The ANU input is a prefix of `anubits_1` in the [data release](https://zenodo.org/records/4440318) accompanying [Kavulich, Van Deren and Schlosshauer, Physics Letters A (2021)](https://doi.org/10.1016/j.physleta.2020.127032).
- **IBM Belem:** Basic QRNG trials in the `Belem/Basic_QRNG_Belem/` archive directory of [Owen Root's QRNG Trial Sequences, version 1](https://doi.org/10.5281/zenodo.10542216).
- **IBM Quito:** Basic QRNG trials in the `Quito/Basic_QRNG_Quito/` directory of the same release. Belem and Quito use distinct trial files.

The archived metadata identifies both records as CC BY 4.0. Original metadata, member names, and input checksums are in `core/data/provenance/`. The package retains a prefix of the ANU archive and the IBM trial archive needed to reconstruct the inputs.

The extension also contains explicitly generated sticky-uniform and fixed-support inputs. Their seeds and generation settings are in `extension/input_manifest.json` and `extension/run_extension.py`. Throughput uses a generated uniform stream. These controlled inputs are separate from the three recorded data sources and from the core headline averages.
