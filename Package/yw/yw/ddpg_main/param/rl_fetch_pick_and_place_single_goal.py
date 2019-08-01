# Best parameters found so far to be used for the Open AI fetch pick and place environment with a single goal.
params_config = {
    # Config Summary (Overwrite this later)
    "config": "default",  # change this for each customized params file
    # Environment Config
    "env_name": "FetchPickAndPlace-v1",
    "r_scale": 1.0,  # scale the reward of the environment down
    "r_shift": 0.0,  # shift the reward of the environment up
    "eps_length": 30,  # overwrite the default length of the episode
    "env_args": {},  # extra arguments passed to the environment.
    "fix_T": True,  # whether or not to fix episode length for all rollouts. If false, use the ring buffer
    # DDPG Config
    "ddpg": {
        "buffer_size": int(1e6),
        # replay strategy to be used
        "replay_strategy": "none",  # choose between ["her", "none"] (her for hindsight exp replay)
        # networks
        "scope": "ddpg",
        "use_td3": 1,  # whether or not to use td3
        "layer_sizes": [256, 256, 256],  # number of neurons in each hidden layers
        "Q_lr": 0.001,  # critic learning rate
        "pi_lr": 0.001,  # actor learning rate
        "action_l2": 0.4,  # (1.0 for OpenAI envs) quadratic penalty on actions (before rescaling by max_u)
        "batch_size": 256,  # per mpi thread, measured in transitions and reduced to even multiple of chunk_length.
        # double q learning
        "polyak": 0.95,  # polyak averaging coefficient for double q learning
        # use demonstrations
        "demo_strategy": "none",  # choose between ["none", "bc", "norm", "manual", "maf"]
        "sample_demo_buffer": 0,  # whether or not to sample from demonstration buffer
        "use_demo_reward": 0,  # whether or not to assume that demonstrations also have rewards
        "batch_size_demo": 128,  # number of samples to be used from the demonstrations buffer, per mpi thread 128/1024 or 32/256
        "num_demo": 10,  # number of expert demo episodes
        "q_filter": 1,  # whether or not a Q value filter should be used on the actor outputs
        "prm_loss_weight": 1.0,  # (0.001 for OpenAI) weight corresponding to the primary loss
        "aux_loss_weight": 10.0,  # (0.0078 for OpenAI) weight corresponding to the auxilliary loss also called the cloning loss
        "shaping_params": {"num_ens": 1, "prm_loss_weight": 1.0, "reg_loss_weight": 800.0, "potential_weight": 5.0},
        # normalization
        "norm_eps": 0.01,  # epsilon used for observation normalization
        "norm_clip": 5,  # normalized observations are cropped to this values
        # i/o clippings
        "clip_obs": 200.0,
        "clip_pos_returns": False,  # Whether or not this environment has positive return or not.
        "clip_return": False,
    },
    # HER Config
    "her": {"k": 4},  # number of additional goals used for replay
    # Rollouts Config
    "rollout": {
        "rollout_batch_size": 4,  # per mpi thread
        "random_eps": 0.2,  # (0.3 for OpenAI) percentage of time a random action is taken
        "noise_eps": 0.2,  # (0.2 for OpenAI) std of gaussian noise added to not-completely-random actions as a percentage of max_u
    },
    "evaluator": {
        "rollout_batch_size": 20,  # number of test rollouts per epoch, each consists of rollout_batch_size rollouts
        "random_eps": 0.0,
        "noise_eps": 0.05,
        "compute_Q": True,
    },
    # Training Config
    "train": {
        "n_epochs": 1000,
        "n_cycles": 10,  # per epoch
        "n_batches": 40,  # training batches per cycle
        "save_interval": 10,
        "shaping_policy": 0,  # whether or not to use a pretrained shaping policy
    },
    "seed": tuple(range(2)),
}