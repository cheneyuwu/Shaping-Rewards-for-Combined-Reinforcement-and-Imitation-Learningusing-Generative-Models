import os.path as osp
import pickle

import numpy as np
import tensorflow as tf

from rlfd import normalizer
from rlfd.agents import td3_networks
from rlfd.shapings import shaping


class OfflineRLShaping(shaping.Shaping):

  def __init__(self, **kwargs):
    self.init_args = locals()

    super(OfflineRLShaping, self).__init__()

    self._policy = None

  @tf.function
  def potential(self, o, g, u):
    return self._policy.estimate_q_graph(o, g, u)

  def before_training_hook(self, data_dir, **kwargs):
    policy = osp.join(data_dir, "demo_policy.pkl")
    with open(policy, "rb") as f:
      self._policy = pickle.load(f)

  def __getstate__(self):
    state = {k: v for k, v in self.init_args.items() if not k == "self"}
    state["policy"] = self._policy
    return state

  def __setstate__(self, state):
    policy = state.pop("policy")
    self.__init__(**state)
    self._policy = policy