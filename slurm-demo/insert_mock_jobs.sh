!/usr/bin/env bash
set -x
set -eo pipefail

COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:="auditor"}

function insert_records() {
        # Run on partition1
        # docker exec "${COMPOSE_PROJECT_NAME}-slurm-1" sh -c "sbatch --job-name=test_part1 --partition=part1 --comment=\"$COMMENT\" /batch.sh" 
        for i in $(seq 1 20); do

      sh -c "sbatch \
        --job-name=test_part${i} \
        --partition=part1 \
        ./batch.sh"
              
      
    done
        
    for i in $(seq 21 40); do
    sh -c "sbatch \
        --job-name=test_part${i} \
        --partition=part2 \
        ./batch.sh"
        done
}

insert_records
