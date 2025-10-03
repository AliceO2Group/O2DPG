#!/usr/bin/env bash

# a simple top-N metrics query for a couple of examples using jq
# assumes JSON produced by o2dpg_sim_metrics.py

# top CPU-time consumers
jq 'to_entries
    | map(select(.value.cpu?.mean != null and .value.lifetime?.mean != null))
    | sort_by(-(.value.cpu.mean * .value.lifetime.mean))
    | .[:5]
    | map({name: .key,
           cpu_mean: .value.cpu.mean,
           lifetime_mean: .value.lifetime.mean,
           product: (.value.cpu.mean * .value.lifetime.mean)})' merged_metrics.json 

# top mem consumers


# top cpu consumers
jq 'to_entries
    | map(select(.value.cpu?.mean != null))
    | sort_by(-.value.cpu.mean)
    | .[:5]
    | map({name: .key, cpu_mean: .value.cpu.mean})'

# top walltime consumers
jq 'to_entries
    | map(select(.value.lifetime?.mean != null))
    | sort_by(-.value.lifetime.mean)
    | .[:5]
    | map({name: .key, lifetime_mean: .value.lifetime.mean})'