from copy import deepcopy
from td3fd.rlkit_td3.params.peginholerandinit import params_config as base_params

params_config = deepcopy(base_params)
params_config["config"] = ("TD3_BC",)
params_config["demo_strategy"] = "bc"
params_config["seed"] = 0 # tuple(range(2))

# tune parameters
params_config["trainer_kwargs"]["prm_loss_weight"] = (1e-4,)