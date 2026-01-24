#!/bin/bash
#SBATCH --job-name=test
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --time=00:02:00
#SBATCH --output=out_%j.txt

module load openmpi   # o mpich / modulo giusto del cluster

srun python test_mpi4py.py
