# RBA VANET ns-3 Reproducibility

This repository contains the ns-3 experiment files used to study packet loss and end-to-end delay for a reputation-based authentication (RBA) VANET scenario as node count increases.

It is designed as a small reproducibility repo that sits on top of a clean `ns-3-dev` checkout rather than a fork containing the full ns-3 source tree.

## Repository Contents

- `scratch/rba-paper-scaling.cc`: ns-3 simulation for the VANET scaling experiment
- `tools/rba/run-scaling.sh`: automation script for the node-count sweep
- `tools/rba/plot-scaling.py`: SVG plot generator
- `results/rba/rba-scaling-summary.csv`: sample per-run output
- `results/rba/rba-node-count-summary.csv`: sample aggregated output by node count
- `results/rba/packet-loss-vs-node-count.svg`: sample packet-loss figure
- `results/rba/end-to-end-delay-vs-node-count.svg`: sample end-to-end-delay figure

Intermediate shard files used during parallel runs are not part of the public repo.

## Base ns-3 Revision

Use this repository with `ns-3-dev` at:

```text
e2c9e30c6ebdfd534aa7e30f6324b5674d138b9f
```

## Experiment Summary

The simulation measures packet loss and end-to-end delay while increasing the number of vehicles from `10` to `1000`.

Default scenario:

- IEEE 802.11p ad hoc wireless configuration
- PHY mode: `OfdmRate6MbpsBW10MHz`
- `105` byte authenticated packets
- `4` RSUs deployed along a `3000 m` road
- `4` lanes
- vehicle speed sampled uniformly from `15` to `20 m/s`
- communication range of `300 m`
- packet interval of `100 ms`

Reported metrics:

- `packet_loss_ratio = (tx_packets - rx_packets) / tx_packets`
- `mean_network_delay_ms`: delay measured by ns-3 FlowMonitor
- `mean_rba_end_to_end_delay_ms = mean_network_delay_ms + 4.467 ms + 5.956 ms`

The end-to-end delay metric includes fixed prover and verifier processing costs used in the study.

## Applying the Files to ns-3-dev

Clone `ns-3-dev`, check out the reference revision, and copy this repository's `scratch/` and `tools/` directories into that tree.

```bash
git clone https://gitlab.com/nsnam/ns-3-dev.git ns-3-dev
cd ns-3-dev
git checkout e2c9e30c6ebdfd534aa7e30f6324b5674d138b9f
```

Then copy the experiment files from this repo into the ns-3 checkout:

```bash
OVERLAY=/path/to/this-repo
NS3=/path/to/ns-3-dev

rsync -av "$OVERLAY/scratch/" "$NS3/scratch/"
rsync -av "$OVERLAY/tools/" "$NS3/tools/"
```

## Build

Run these commands inside the `ns-3-dev` checkout:

```bash
cmake -S . -B cmake-build-rba \
  -DNS3_OUTPUT_DIRECTORY=build-rba \
  -DNS3_EXAMPLES=ON \
  -DNS3_TESTS=OFF \
  -DNS3_WARNINGS_AS_ERRORS=OFF

cmake --build cmake-build-rba --target scratch_rba-paper-scaling -j4
```

The resulting binary is placed under `build-rba/scratch/`.

## Single Run

```bash
build-rba/scratch/ns3.47-rba-paper-scaling-default \
  --numVehicles=100 \
  --numRsus=4 \
  --activeTime=1s \
  --cleanupTime=1s \
  --resultsCsv=results/rba/single-run.csv
```

## Full Sweep

The sweep script builds the target if needed, runs the node-count experiment, and writes plots automatically.

```bash
chmod +x tools/rba/run-scaling.sh

COUNT_START=10 \
COUNT_END=1000 \
COUNT_STEP=10 \
RUNS=5 \
NUM_RSUS=4 \
ROAD_LENGTH=3000 \
ACTIVE_TIME=4s \
CLEANUP_TIME=5s \
tools/rba/run-scaling.sh
```

Outputs:

- `results/rba/rba-scaling-summary.csv`
- `results/rba/rba-node-count-summary.csv`
- `results/rba/packet-loss-vs-node-count.svg`
- `results/rba/end-to-end-delay-vs-node-count.svg`

Optional flags:

- `KEEP_FLOWMON_XML=1`: keep FlowMonitor XML outputs
- `GENERATE_PLOTS=0`: skip SVG generation

## Output Files

Per-run CSV columns include:

- `seed`, `run`
- `num_vehicles`, `num_rsus`, `total_nodes`
- `road_length_m`, `lane_count`, `lane_spacing_m`, `coverage_range_m`
- `packet_size_bytes`, `beacon_interval_ms`, `phy_mode`
- `tx_packets`, `rx_packets`, `lost_packets`
- `delivery_ratio`, `packet_loss_ratio`
- `mean_network_delay_ms`
- `mean_rba_end_to_end_delay_ms`

The aggregated CSV groups rows by node count and reports mean, standard deviation, minimum, and maximum values for both loss and delay.

## Sample Results Included in This Repo

The `results/rba/` directory contains sample CSV and SVG outputs so the expected file layout and plot format are visible directly in the public repository.

These sample results are included for reference. To reproduce the study dataset from scratch, rerun the sweep on a clean `ns-3-dev` checkout using the commands above.

## Citation

This repository includes a `CITATION.cff` file so GitHub can generate a repository citation automatically.

If you use this repository in a paper, cite:

- this repository
- the related manuscript
- `ns-3` as the simulation platform

Suggested BibTeX entries:

```bibtex
@software{ns3_rba_vanet_reproducibility_2026,
  title   = {ns3-rba-vanet-reproducibility},
  author  = {Abdelmoaty, Abdelrhman and Ramadan, Ahmed Adel and Elmasry, Karim and Shawky, Mahmoud A.},
  year    = {2026},
  version = {1.0.0}
}

@article{abdelmoaty2026rba,
  title   = {Privacy-Preserving Reputation-Based Authentication for Real-Time VANET and IoV Using Zero-Knowledge Proofs and Blockchain},
  author  = {Abdelmoaty, Abdelrhman and Ramadan, Ahmed Adel and Elmasry, Karim and Shawky, Mahmoud A.},
  year    = {2026},
  note    = {Preprint submitted to Elsevier}
}

@software{ns3_2026,
  title   = {ns-3},
  author  = {{ns-3 project}},
  year    = {2026},
  version = {3.47},
  url     = {https://www.nsnam.org/}
}
```

## Modifications Relative to Clean ns-3-dev

- added `scratch/rba-paper-scaling.cc`
- added `tools/rba/run-scaling.sh`
- added `tools/rba/plot-scaling.py`
- no files under `src/` were modified
