import json
import os
import pickle
import sys
osp = os.path

import numpy as np
import tensorflow as tf
import ray
from ray import tune

from rlfd import (logger, agents, metrics, policies, env_manager, drivers,
                  shapings)

from rlfd.utils.util import set_global_seeds


def get_env_constructor_and_config(params):
  manager = env_manager.EnvManager(env_name=params["env_name"],
                                   env_args=params["env_args"],
                                   r_scale=params["r_scale"],
                                   r_shift=params["r_shift"])
  tmp_env = manager.get_env()
  tmp_env.reset()
  obs, _, _, _ = tmp_env.step(tmp_env.action_space.sample())
  dims = dict(o=tmp_env.observation_space["observation"].shape,
              g=tmp_env.observation_space["desired_goal"].shape,
              u=tmp_env.action_space.shape)
  info = dict(env_name=params["env_name"],
              env_args=params["env_args"],
              r_scale=params["r_scale"],
              r_shift=params["r_shift"])
  config = dict(eps_length=tmp_env.eps_length,
                fix_T=params["fix_T"],
                max_u=tmp_env.max_u,
                dims=dims,
                info=info)
  return manager.get_env, config


def config_driver(fix_T, seed, *args, **kwargs):
  driver = (drivers.EpisodeBasedDriver(*args, **kwargs)
            if fix_T else drivers.StepBasedDriver(*args, **kwargs))
  driver.seed(seed)
  return driver


def main(config):
  # Setup Paths
  root_dir = os.path.join(
      config["root_dir"], "config_" + config["config"],
      *[x + "_" + str(config[x]) for x in config["search_params_list"]])
  logger.configure(dir=root_dir, format_strs=["log", "csv"], log_suffix="")
  assert logger.get_dir() is not None

  # Limit gpu memory growth for tensorflow
  physical_gpus = tf.config.list_physical_devices("GPU")
  try:
    for gpu in physical_gpus:
      tf.config.experimental.set_memory_growth(gpu, True)
    logical_gpus = tf.config.list_logical_devices("GPU")
    print("Found", len(physical_gpus), "physical GPUs", len(logical_gpus),
          "logical GPUs")
  except RuntimeError as e:
    print(e)  # Memory growth must be set before GPUs have been initialized

  # Load parameters.
  param_file = os.path.join(root_dir, "params.json")
  assert os.path.isfile(param_file), param_file
  with open(param_file, "r") as f:
    params = json.load(f)

  # Seed everything.
  set_global_seeds(params["seed"])

  # Tensorboard summary writer
  summary_writer_path = osp.join(root_dir, "summaries")
  summary_writer = tf.summary.create_file_writer(summary_writer_path,
                                                 flush_millis=10 * 1000)
  summary_writer.set_as_default()

  make_env, env_params = get_env_constructor_and_config(params=params)

  # Configure shaping
  if "shaping" in params.keys():
    shaping = shapings.EnsembleShaping(**params["shaping"], **env_params)
    shaping.before_training_hook(data_dir=root_dir, env=make_env())
    shaping.train()
    shaping.after_training_hook()
  else:
    shaping = None

  # Configure agents and drivers.
  agent_params = params["agent"]
  agent = agents.AGENTS[params["algo"]](**agent_params, **env_params)

  random_driver = config_driver(
      params["fix_T"],
      params["seed"],
      make_env=make_env,
      policy=policies.RandomPolicy(env_params["dims"]["o"],
                                   env_params["dims"]["g"],
                                   env_params["dims"]["u"],
                                   env_params["max_u"]),
      num_steps=params["expl_num_steps_per_cycle"],
      num_episodes=params["expl_num_episodes_per_cycle"])
  expl_driver = config_driver(
      params["fix_T"],
      params["seed"],
      make_env=make_env,
      policy=agent.expl_policy,
      num_steps=params["expl_num_steps_per_cycle"],
      num_episodes=params["expl_num_episodes_per_cycle"])
  eval_driver = config_driver(
      params["fix_T"],
      params["seed"],
      make_env=make_env,
      policy=agent.eval_policy,
      num_steps=params["eval_num_steps_per_cycle"],
      num_episodes=params["eval_num_episodes_per_cycle"])

  offline_testing_metrics = [
      metrics.EnvironmentSteps(),
      metrics.NumberOfEpisodes(),
      metrics.AverageReturnMetric(),
      metrics.AverageEpisodeLengthMetric(),
  ]
  training_metrics = [
      metrics.EnvironmentSteps(),
      metrics.NumberOfEpisodes(),
      metrics.AverageReturnMetric(),
      metrics.AverageEpisodeLengthMetric(),
  ]
  testing_metrics = [
      metrics.EnvironmentSteps(),
      metrics.NumberOfEpisodes(),
      metrics.AverageReturnMetric(),
      metrics.AverageEpisodeLengthMetric(),
  ]

  # Learning parameters
  offline_num_epochs = params["offline_num_epochs"]
  offline_num_batches_per_epoch = params["offline_num_batches_per_epoch"]
  random_exploration_cycles = params["random_expl_num_cycles"]
  num_epochs = params["num_epochs"]
  num_cycles_per_epoch = params["num_cycles_per_epoch"]
  num_batches_per_cycle = params["num_batches_per_cycle"]

  # Setup policy saving
  save_interval = 0
  policy_path = osp.join(root_dir, "policies")
  os.makedirs(policy_path, exist_ok=True)

  # Load offline data and initialize shaping
  agent.before_training_hook(data_dir=root_dir, env=make_env(), shaping=shaping)

  # Train offline
  for epoch in range(offline_num_epochs):
    for _ in range(offline_num_batches_per_epoch):
      agent.train_offline()

    eval_driver.clear_history()
    experiences = eval_driver.generate_rollouts(
        observers=offline_testing_metrics)

    with tf.name_scope("OfflineTesting"):
      for metric in offline_testing_metrics[2:]:
        metric.summarize(step=agent.offline_training_step,
                         step_metrics=offline_testing_metrics[:2])
      for key, val in eval_driver.logs("test"):
        logger.record_tabular(key, val)

    logger.dump_tabular()

    agent.save(osp.join(policy_path, "offline_policy_initial.pkl"))
    logger.info("Saving agent after offline training.")

    # For ray status updates
    if ray.is_initialized():
      try:
        tune.report(mode="offline", epoch=epoch)  # ray 0.8.6
      except:
        tune.track.log(mode="offline", epoch=epoch)  # previous versions

  # Train online
  for _ in range(random_exploration_cycles):
    experiences = random_driver.generate_rollouts(observers=training_metrics)
    agent.store_experiences(experiences)

  for epoch in range(num_epochs):
    logger.record_tabular("epoch", epoch)

    # 1 epoch contains multiple cycles of training, 1 time testing, logging
    # and agent saving

    expl_driver.clear_history()
    for cyc in range(num_cycles_per_epoch):

      experiences = expl_driver.generate_rollouts(observers=training_metrics)
      if num_batches_per_cycle != 0:  # agent is being updated
        agent.store_experiences(experiences)

      for _ in range(num_batches_per_cycle):
        agent.train_online()

      if cyc == num_cycles_per_epoch - 1:
        # update meta parameters
        potential_weight = agent.update_potential_weight()
        logger.info("Current potential weight: ", potential_weight)

    with tf.name_scope("OnlineTraining"):
      for metric in training_metrics[2:]:
        metric.summarize(step_metrics=training_metrics[:2])
      for key, val in expl_driver.logs("train"):
        logger.record_tabular(key, val)
      for key, val in agent.logs():
        logger.record_tabular(key, val)

    eval_driver.clear_history()
    experiences = eval_driver.generate_rollouts(observers=testing_metrics)

    with tf.name_scope("OnlineTesting"):
      for metric in testing_metrics[2:]:
        metric.summarize(step_metrics=training_metrics[:2])
      for key, val in eval_driver.logs("test"):
        logger.record_tabular(key, val)

    logger.dump_tabular()

    # Save the agent periodically.
    if (save_interval > 0 and epoch % save_interval == save_interval - 1):
      agent.save(osp.join(policy_path, "online_policy_{}.pkl".format(epoch)))
    agent.save(osp.join(policy_path, "online_policy_latest.pkl"))
    logger.info("Saving agent after online training.")

    # For ray status updates
    if ray.is_initialized():
      try:
        tune.report(mode="online", epoch=epoch)  # ray 0.8.6
      except:
        tune.track.log(mode="online", epoch=epoch)  # previous versions