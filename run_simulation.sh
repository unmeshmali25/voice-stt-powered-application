#!/bin/bash
# VoiceOffers Simulation Runner
# This runs the simulation with production configuration

python -m app.simulation.orchestrator \
  --time-scale 148 \
  --llm-percentage 0.1 \
  --llm-tier-split 0.9 \
  --start-date 2024-04-01 \
  --hours 1 \
  --fresh
