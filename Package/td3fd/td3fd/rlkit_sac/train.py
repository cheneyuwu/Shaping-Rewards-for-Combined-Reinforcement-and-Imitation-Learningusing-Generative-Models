from gym.envs.mujoco import HalfCheetahEnv

import rlkit.torch.pytorch_util as ptu
from rlkit.data_management.env_replay_buffer import EnvReplayBuffer
from rlkit.envs.wrappers import NormalizedBoxEnv
from rlkit.launchers.launcher_util import setup_logger
from rlkit.samplers.data_collector import MdpPathCollector
from rlkit.torch.sac.policies import TanhGaussianPolicy, MakeDeterministic
from rlkit.torch.sac.sac import SACTrainer
from rlkit.torch.networks import FlattenMlp
from rlkit.torch.torch_rl_algorithm import TorchBatchRLAlgorithm

from td3fd import config
from td3fd.env_manager import EnvManager
from td3fd.rlkit_sac.sacfd import SACFDTrainer
from td3fd.rlkit_sac.shaping import RewardShaping

import os
import numpy as np
import pickle


def experiment(root_dir, variant):

    # expl_env = NormalizedBoxEnv(HalfCheetahEnv())
    # eval_env = NormalizedBoxEnv(HalfCheetahEnv())
    env_manager = EnvManager(env_name=variant["env_name"], with_goal=False)
    expl_env = NormalizedBoxEnv(env_manager.get_env())
    eval_env = NormalizedBoxEnv(env_manager.get_env())

    obs_dim = expl_env.observation_space.low.size
    action_dim = eval_env.action_space.low.size

    # IMPORTANT: Modify path length to be the environment max path length
    variant["algorithm_kwargs"]["max_path_length"] = expl_env.eps_length

    M = variant["layer_size"]
    qf1 = FlattenMlp(input_size=obs_dim + action_dim, output_size=1, hidden_sizes=[M, M],)
    qf2 = FlattenMlp(input_size=obs_dim + action_dim, output_size=1, hidden_sizes=[M, M],)
    target_qf1 = FlattenMlp(input_size=obs_dim + action_dim, output_size=1, hidden_sizes=[M, M],)
    target_qf2 = FlattenMlp(input_size=obs_dim + action_dim, output_size=1, hidden_sizes=[M, M],)
    policy = TanhGaussianPolicy(obs_dim=obs_dim, action_dim=action_dim, hidden_sizes=[M, M],)
    eval_policy = MakeDeterministic(policy)
    eval_path_collector = MdpPathCollector(eval_env, eval_policy,)
    expl_path_collector = MdpPathCollector(expl_env, policy,)
    replay_buffer = EnvReplayBuffer(variant["replay_buffer_size"], expl_env,)

    shaping = RewardShaping(
        env=eval_env,
        demo_strategy=variant["demo_strategy"],
        discount=variant["trainer_kwargs"]["discount"],
        **variant["shaping"],
    )
    demo_replay_buffer = EnvReplayBuffer(variant["replay_buffer_size"], expl_env,)  # TODO load from demo buffer
    if variant["demo_strategy"] != "none":
        demo_file = os.path.join(root_dir, "demo_data.npz")
        assert os.path.isfile(demo_file), "demonstration training set does not exist"
        demo_data = pickle.load(open(demo_file, "rb"))
        demo_replay_buffer.add_paths(demo_data)
        if variant["demo_strategy"] in ["gan", "nf"]:
            shaping.train(demo_data)
            shaping.evaluate()

    trainer = SACFDTrainer(
        env=eval_env,
        policy=policy,
        qf1=qf1,
        qf2=qf2,
        target_qf1=target_qf1,
        target_qf2=target_qf2,
        shaping=shaping,  # TODO
        demo_strategy=variant["demo_strategy"],
        demo_replay_buffer=demo_replay_buffer,  # TODO
        **variant["trainer_kwargs"],
    )
    algorithm = TorchBatchRLAlgorithm(
        trainer=trainer,
        exploration_env=expl_env,
        evaluation_env=eval_env,
        exploration_data_collector=expl_path_collector,
        evaluation_data_collector=eval_path_collector,
        replay_buffer=replay_buffer,
        **variant["algorithm_kwargs"],
    )
    algorithm.to(ptu.device)
    algorithm.train()


def main(root_dir, params):
    config.check_params(params, DEFAULT_PARAMS)
    setup_logger(exp_name=params["config"], variant=params, log_dir=root_dir)
    ptu.set_gpu_mode(True)  # optionally set the GPU (default=True)
    experiment(root_dir, params)


DEFAULT_PARAMS = dict(
    # params required by td3fd for logging
    alg="rlkit-sac",
    config="default",
    env_name="HalfCheetah-v3",
    seed=0,
    # rlkit default params
    algorithm="SAC",
    version="normal",
    layer_size=256,
    replay_buffer_size=int(1e6),
    demo_strategy="maf",
    algorithm_kwargs=dict(
        num_epochs=3000,
        num_eval_steps_per_epoch=5000,
        num_trains_per_train_loop=1000,
        num_expl_steps_per_train_loop=1000,
        min_num_steps_before_training=1000,
        max_path_length=1000,
        batch_size=256,
    ),
    trainer_kwargs=dict(
        discount=0.99,
        soft_target_tau=5e-3,
        target_update_period=1,
        policy_lr=3e-4,
        qf_lr=3e-4,
        reward_scale=1,
        use_automatic_entropy_tuning=True,
        demo_batch_size=128,
        prm_loss_weight=1.0,
        aux_loss_weight=1.0,
        q_filter=True,
    ),
    shaping=dict(
        num_ensembles=1,
        num_epochs=int(3e3),
        batch_size=128,
        norm_obs=True,
        norm_eps=0.01,
        norm_clip=5,
        nf=dict(
            num_blocks=4,
            num_hidden=100,
            prm_loss_weight=1.0,
            reg_loss_weight=200.0,
            potential_weight=500.0,
        ),
        gan=dict(
            layer_sizes=[256, 256, 256], 
            potential_weight=3.0,
        ),
    ),
)

# if __name__ == "__main__":
# setup_logger("name-of-experiment", variant=DEFAULT_PARAMS)
# ptu.set_gpu_mode(True)  # optionally set the GPU (default=False)
# experiment(variant)