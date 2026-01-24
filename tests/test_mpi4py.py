
from mpi4py import MPI
import time

comm = MPI.COMM_WORLD
size = comm.Get_size()
rank = comm.Get_rank()

N = 20  # numero totale di frame (esempio)

def analyze_frame(i):
    # Simuliamo un lavoro costoso
    time.sleep(0.2)
    return f"Frame {i} analizzato dal rank {rank}"

local_results = []

# pattern standard: i = rank, rank+size, ...
for i in range(rank, N, size):
    res = analyze_frame(i)
    print(res, flush=True)
    local_results.append(res)

# raccogliamo tutto sul rank 0
all_results = comm.gather(local_results, root=0)

if rank == 0:
    print("\n=== RISULTATI FINALI ===")
    for r in all_results:
        for line in r:
            print(line)
