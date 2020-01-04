import numpy as np

from td3fd.env import reacher_2d

try:
    from td3fd.env.franka_env import panda_env
except:
    panda_env = None
try:
    import gym

    # Need this for getting observation in pixels (for vision based learning) (for future works)
    from mujoco_py import GlfwContext

    GlfwContext(offscreen=True)  # Create a window to init GLFW.
except:
    gym = None


try:
    from metaworld.envs.mujoco.env_dict import HARD_MODE_ARGS_KWARGS, HARD_MODE_CLS_DICT

    mtw_envs = {**HARD_MODE_CLS_DICT["train"], **HARD_MODE_CLS_DICT["test"]}
    mtw_args = {**HARD_MODE_ARGS_KWARGS["train"], **HARD_MODE_ARGS_KWARGS["test"]}

except:
    mtw_envs = None
    mtw_args = None


class EnvWrapper:
    """Wrapper of the environment that does the following:
        1. adjust rewards: r = (r + r_shift) / r_scale
        2. modify state to contain: observation, achieved_goal, desired_goal
    """

    def __init__(self, make_env, r_scale, r_shift, eps_length):
        self.env = make_env()
        self.r_scale = r_scale
        self.r_shift = r_shift
        self.eps_length = eps_length if eps_length else self.env._max_episode_steps
        # need the following properties
        self.action_space = self.env.action_space
        self.observation_space = self.env.observation_space
        self.max_u = self.action_space.high[0]

    # def compute_reward(self, achieved_goal, desired_goal, info):
    #     reward = self.env.compute_reward(achieved_goal=achieved_goal, desired_goal=desired_goal, info=info)
    #     reward = (reward + self.r_shift) / self.r_scale
    #     return reward

    def reset(self, **kwargs):
        state = self.env.reset(**kwargs)
        return self._transform_state(state)

    def render(self, **kwargs):
        return self.env.render(**kwargs)

    def seed(self, seed=0):
        return self.env.seed(seed)

    def step(self, action):
        state, r, done, info = self.env.step(action)
        r = (r + self.r_shift) / self.r_scale
        return self._transform_state(state), r, done, info

    def close(self):
        return self.env.close()

    def _transform_state(self, state):
        """
        modify state to contain: observation, achieved_goal, desired_goal
        """
        if not type(state) == dict:
            state = {"observation": state, "achieved_goal": np.empty(0), "desired_goal": np.empty(0)}
        return state


class EnvManager:
    def __init__(self, env_name, env_args={}, r_scale=1, r_shift=0.0, eps_length=0):
        self.make_env = None
        # Search from our own environments
        if env_name == "Reach2D":
            env_args["sparse"] = True
            self.make_env = lambda: reacher_2d.make("Reacher", **env_args)
        elif env_name == "Reach2DDense":
            env_args["sparse"] = False
            self.make_env = lambda: reacher_2d.make("Reacher", **env_args)
        elif env_name == "Reach2DF":
            env_args["order"] = 1
            env_args["sparse"] = True
            self.make_env = lambda: reacher_2d.make("Reacher", **env_args)
        elif env_name == "Reach2DFDense":
            env_args["order"] = 1
            env_args["sparse"] = False
            self.make_env = lambda: reacher_2d.make("Reacher", **env_args)
        elif env_name == "BlockReachF":
            env_args["sparse"] = True
            env_args["order"] = 1
            env_args["block"] = True
            self.make_env = lambda: reacher_2d.make("Reacher", **env_args)
        elif env_name == "BlockReachFDense":
            env_args["sparse"] = False
            env_args["order"] = 1
            env_args["block"] = True
            self.make_env = lambda: reacher_2d.make("Reacher", **env_args)

        # Search in Gym Envs
        if self.make_env is None and gym is not None:
            try:
                _ = gym.make(env_name, **env_args)
                self.make_env = lambda: gym.make(env_name, **env_args)
            except gym.error.UnregisteredEnv:
                pass

        # Search in MetaWorld Envs
        if self.make_env is None and mtw_envs is not None and env_name in mtw_envs.keys():

            def make_env():
                args = mtw_args[env_name]["args"]
                kwargs = mtw_args[env_name]["kwargs"]
                kwargs["random_init"] = False  # disable random goal locations
                kwargs["obs_type"] = "with_goal"  # disable random goal locations
                env = mtw_envs[env_name](*args, **kwargs)
                return env

            self.make_env = make_env

        # Franka environment
        if self.make_env is None and panda_env is not None:
            # TODO add a make function
            self.make_env = panda_env.FrankaPegInHole

        if self.make_env is None:
            raise NotImplementedError

        # Add extra properties on the environment.
        self.r_scale = r_scale
        self.r_shift = r_shift
        self.eps_length = eps_length

    def get_env(self):
        return EnvWrapper(self.make_env, self.r_scale, self.r_shift, self.eps_length)


if __name__ == "__main__":
    import numpy as np
    import matplotlib.pyplot as plt

    # # For a openai env
    # env_manager = EnvManager("YWFetchPegInHole2D-v0")
    # env = env_manager.get_env()

    # env.seed(0)
    # done = True
    # for i in range(1000):
    #     if done:
    #         env.reset()
    #     action = np.random.randn(env.action_space.shape[0]) * env.action_space.high[0]  # sample random action
    #     state, r, done, info = env.step(action)
    #     # print(state, r, done, info)
    #     # print(state["pixel"][..., :3].shape)
    #     # plt.imshow(state["pixel"][..., 3] / 255.0)
    #     # plt.show()
    #     env.render(mode="rgb_array")

    # For a metaworld env
    # env_manager = EnvManager("pick-place-v1", eps_length=50)
    # env = env_manager.get_env()
    # while True:
    #     obs = env.reset()  # Reset environment
    #     for _ in range(1000):
    #         a = env.action_space.sample()  # Sample an action

    #         obs, reward, done, info = env.step(a)  # Step the environoment with the sampled random action
    #         print(reward)
    #         env.render()

    env_manager = EnvManager("hammer-v1", eps_length=50)
    env = env_manager.get_env()
    for _ in range(1):
        env.reset()
        for _ in range(200):
            env.render()
            if _ < 20:
                obs, r, done, info = env.step(np.array([0, 0, -1, 0]))
            elif _ < 30:
                obs, r, done, info = env.step(np.array([0, 0, 0, 1]))
            elif _ < 40:
                obs, r, done, info = env.step(np.array([0, 0, 1, 1]))
            elif _ < 50:
                obs, r, done, info = env.step(np.array([1, 0, 0, 1]))
            elif _ < 60:
                obs, r, done, info = env.step(np.array([0, 1, 0, 1]))
            else:
                obs, r, done, info = env.step(np.array([0, 0, 0, 1]))
            print(done)
            # print(r)
