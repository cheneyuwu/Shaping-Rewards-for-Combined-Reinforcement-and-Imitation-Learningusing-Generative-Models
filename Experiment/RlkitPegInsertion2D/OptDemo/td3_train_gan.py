from copy import deepcopy
from td3fd.rlkit_td3.params.peginhole2d import params_config as base_params

params_config = deepcopy(base_params)
params_config["config"] = ("TD3_GAN_Shaping",)
params_config["demo_strategy"] = "gan"
params_config["seed"] = 0 # tuple(range(2))