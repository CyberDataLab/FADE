#!/bin/bash
MODE="cpu"

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --mode) MODE="$2"; shift ;;
    *) echo "Unknown parameter: $1"; exit 1 ;;
  esac
  shift
done

if [[ "$MODE" != "cpu" && "$MODE" != "gpu" ]]; then
  echo "Invalid mode: $MODE. Use --mode cpu or --mode gpu"
  exit 1
fi

HOST_OS=$(uname)
echo "Detected host OS: $HOST_OS"
echo "Starting platform in mode: $MODE"

GPU_FLAG=""
if [[ "$MODE" == "gpu" ]]; then
  GPU_FLAG="--gpus all"        
fi

HOST_OS=$HOST_OS EXECUTION_MODE=$MODE \
  docker-compose -f docker-compose.$MODE.yml up --build $GPU_FLAG
