#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$ROOT_DIR/cmake-build-rba}"
NS3_OUTPUT_DIR="${NS3_OUTPUT_DIR:-build-rba}"
TARGET_NAME="${TARGET_NAME:-scratch_rba-paper-scaling}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/results/rba}"
RESULTS_CSV="${RESULTS_CSV:-$RESULTS_DIR/rba-scaling-summary.csv}"
PLOT_SCRIPT="${PLOT_SCRIPT:-$ROOT_DIR/tools/rba/plot-scaling.py}"

COUNT_START="${COUNT_START:-10}"
COUNT_END="${COUNT_END:-1000}"
COUNT_STEP="${COUNT_STEP:-10}"
COUNTS="${COUNTS:-}"
RUN_START="${RUN_START:-1}"
RUNS="${RUNS:-5}"
SEED="${SEED:-12345}"
JOBS="${JOBS:-4}"

NUM_RSUS="${NUM_RSUS:-4}"
ROAD_LENGTH="${ROAD_LENGTH:-3000}"
WARMUP_TIME="${WARMUP_TIME:-1s}"
ACTIVE_TIME="${ACTIVE_TIME:-4s}"
CLEANUP_TIME="${CLEANUP_TIME:-5s}"
BEACON_INTERVAL="${BEACON_INTERVAL:-100ms}"
KEEP_FLOWMON_XML="${KEEP_FLOWMON_XML:-0}"
GENERATE_PLOTS="${GENERATE_PLOTS:-1}"

mkdir -p "$RESULTS_DIR"

if [[ "${APPEND:-0}" != "1" ]]; then
  rm -f "$RESULTS_CSV"
fi

cmake \
  -S "$ROOT_DIR" \
  -B "$BUILD_DIR" \
  -DNS3_OUTPUT_DIRECTORY="$NS3_OUTPUT_DIR" \
  -DNS3_EXAMPLES=ON \
  -DNS3_TESTS=OFF \
  -DNS3_WARNINGS_AS_ERRORS=OFF

cmake --build "$BUILD_DIR" --target "$TARGET_NAME" -j "$JOBS"

SIM_BIN="$(find "$ROOT_DIR/$NS3_OUTPUT_DIR/scratch" -maxdepth 1 -type f -name '*rba-paper-scaling*' | head -n 1)"
if [[ -z "$SIM_BIN" ]]; then
  echo "Could not locate the rba-paper-scaling binary under $ROOT_DIR/$NS3_OUTPUT_DIR/scratch" >&2
  exit 1
fi

COUNT_VALUES=()
if [[ -n "$COUNTS" ]]; then
  for value in $COUNTS; do
    COUNT_VALUES+=("$value")
  done
else
  for value in $(seq "$COUNT_START" "$COUNT_STEP" "$COUNT_END"); do
    COUNT_VALUES+=("$value")
  done
fi

RUN_END=$((RUN_START + RUNS - 1))

for run in $(seq "$RUN_START" "$RUN_END"); do
  for vehicles in "${COUNT_VALUES[@]}"; do
    CMD=(
      "$SIM_BIN"
      "--numVehicles=$vehicles"
      "--numRsus=$NUM_RSUS"
      "--roadLength=$ROAD_LENGTH"
      "--warmupTime=$WARMUP_TIME"
      "--activeTime=$ACTIVE_TIME"
      "--cleanupTime=$CLEANUP_TIME"
      "--beaconInterval=$BEACON_INTERVAL"
      "--seed=$SEED"
      "--run=$run"
      "--resultsCsv=$RESULTS_CSV"
    )

    if [[ "$KEEP_FLOWMON_XML" == "1" ]]; then
      FLOWMON_DIR="$RESULTS_DIR/flowmon/run-$run"
      mkdir -p "$FLOWMON_DIR"
      CMD+=("--flowMonitorXml=$FLOWMON_DIR/vehicles-$vehicles.xml")
    fi

    echo "Running vehicles=$vehicles run=$run"
    "${CMD[@]}"
  done
done

echo
echo "Summary CSV written to: $RESULTS_CSV"

if [[ "$GENERATE_PLOTS" == "1" ]]; then
  python3 "$PLOT_SCRIPT" --input-csv "$RESULTS_CSV" --output-dir "$RESULTS_DIR"
  echo "Plots written to: $RESULTS_DIR"
fi
