#!/bin/bash

#SBATCH --nodes=1
#SBATCH --gres=gpu:1                      # request GPU "generic resource"
#SBATCH --cpus-per-task=1                 # maximum CPU cores per GPU request: 6 on Cedar, 16 on Graham.
#SBATCH --ntasks=10                       # number of MPI processes
#SBATCH --mem-per-cpu=4G                  # memory per node
#SBATCH --time=00-03:00:00                # time format: day-hour:min:sec
#SBATCH --output=fetchreach-%N-%j.out     # %N for node name, %j for jobID
#SBATCH --account=def-florian7

#SBATCH --mail-user=cheney.wu@mail.utoronto.ca
#SBATCH --mail-type=END
#SBATCH --mail-type=FAIL
#SBATCH --mail-type=REQUEUE
#SBATCH --mail-type=ALL

# setup
module load nixpkgs/16.09  intel/2018.3  cuda/10.0  cudnn/7.5  python/3.6  openmpi/3.1.2  mpi4py/3.0.0
source /home/yuchenwu/.bashrc
source /home/yuchenwu/ENV/tf114/bin/activate
nvidia-smi --compute-mode=0
source /home/yuchenwu/projects/def-florian7/yuchenwu/RLProject/setup.sh
# Train RL dense and generate demonstration
# echo 'mpiexec -n 2 python $PROJECT/Experiment/launch.py --exp_dir ~/scratch/OpenAI/FetchReach --targets train:configs/rldense.py demo'
# mpiexec -n 2 python $PROJECT/Experiment/launch.py --exp_dir ~/scratch/OpenAI/FetchReach --targets train:configs/rldense.py demo
# Train RL and RL with demos
echo 'mpiexec -n 10 python $PROJECT/Experiment/launch.py --exp_dir ~/scratch/OpenAI/FetchReach --targets train:configs/cluster/rlmerged.py'
mpiexec -n 10 python $PROJECT/Experiment/launch.py --exp_dir ~/scratch/OpenAI/FetchReach --targets train:configs/cluster/rlmerged.py