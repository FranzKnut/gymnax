import jax
import jax.numpy as jnp
from jax import lax

from gymnax.utils.frozen_dict import FrozenDict
from gymnax.environments import environment, spaces

from typing import Union, Tuple
import chex
Array = chex.Array
PRNGKey = chex.PRNGKey

"""
Template for JAX Compatible Environments.
-------------------------------------------
Steps for adding your own environments/contributing to the repository:
0. Fork and clone the repository.
1. Modify step, reset, get_obs functions from template for your needs.
2. Add the environment id/name to registration.py and the __init__.py imports.
3. Add a unit test to the tests directory and check correctness.
4. Add any reference to the original version/documentation of the environment.
5. [OPTIONAL] Add a link to the Readme of projects that use this environment.
6. [OPTIONAL] Add an example notebook with a step transition/episode rollout.
7. [OPTIONAL] Run a speed benchmark comparing performance on different devices.
8. Open a pull request.
"""


class YourCoolEnv(environment.Environment):
    def __init__(self):
        super().__init__()
        # Default environment parameters
        self.env_params = FrozenDict({"max_steps_in_episode": 100})

    def step(self, key: PRNGKey, state: dict, action: int
             ) -> Tuple[Array, dict, float, bool, dict]:
        """ Perform single timestep state transition. """
        action = jnp.clip(action, -1, 1)
        reward = 0

        # Check game condition & no. steps for termination condition
        state["time"] += 1
        done = self.is_terminal(state)
        state["terminal"] = done
        info = {"discount": self.discount(state)}
        return (lax.stop_gradient(self.get_obs(state)),
                lax.stop_gradient(state), reward, done, info)

    def reset(self, key: PRNGKey) -> Tuple[Array, dict]:
        """ Reset environment state by sampling initial position. """
        high = jnp.array([jnp.pi, 1])
        state = {}
        state["var"] = jax.random.uniform(key, shape=(2,),
                                          minval=-high, maxval=high)
        return self.get_obs(state), state

    def get_obs(self, state: dict) -> Array:
        """ Return observation from raw state trafo. """
        return obs

    def is_terminal(self, state: dict) -> bool:
        """ Check whether state is terminal. """
        done_steps = (state["time"] > self.env_params["max_steps_in_episode"])
        return False

    @property
    def name(self) -> str:
        """ Environment name. """
        return "YourCoolEnv-v0"

    @property
    def action_space(self):
        """ Action space of the environment. """
        return spaces.Discrete(2)

    @property
    def observation_space(self):
        """ Observation space of the environment. """
        return spaces.Box(-1, 1, (1,))

    @property
    def state_space(self):
        """ State space of the environment. """
        return spaces.Dict(
            {"time": spaces.Discrete(self.env_params["max_steps_in_episode"]),
             "terminal": spaces.Discrete(2)})


# JAX Compatible version of Breakout MinAtar environment. Source:
# github.com/kenjyoung/MinAtar/blob/master/minatar/environments/seaquest.py


"""
ENVIRONMENT DESCRIPTION - 'Seaquest-MinAtar'
- Player controls submarine consisting of two cells - front and back.
- Player can fire bullets from front of submarine.
- Enemies consist of submarines [shoot] and fish [don't shoot].
- A reward of +1 is given whenever enemy is struck by bullet and removed.
- Player can pick up drivers which increments a bar indicated by a channel.
- Player has limited oxygen supply indicated by bar in separate channel.
- Oxygen degrades over time. Can be restored:
- If player moves to top of screen and has at least 1 rescued driver on board.
- When surfacing with less than 6, one diver is removed.
- When surfacing with 6, remove all divers. Reward for each active cell in oxygen bar.
- Each time the player surfaces increase difficulty by increasing the spawn rate and movement speed of enemies.
- Termination occurs when player is hit by an enemy fish, sub or bullet
- Or when oxygen reached 0.
- Or when the layer attempts to surface with no rescued divers.
- Enemy and diver directions are indicated by a trail channel active
- in their previous location to reduce partial observability.

- Channels are encoded as follows: 'sub_front':0, 'sub_back':1,
                                   'friendly_bullet':2, 'trail':3,
                                   'enemy_bullet':4, 'enemy_fish':5,
                                   'enemy_sub':6, 'oxygen_guage':7,
                                   'diver_guage':8, 'diver':9
- Observation has dimensionality (10, 10, 10)
- Actions are encoded as follows: ['n','l','u','r','d','f']
"""

# Default environment parameters
params_seaquest = FrozenDict({"ramp_interval": 100,
                              "max_oxygen": 200,
                              "init_spawn_speed": 20,
                              "diver_spawn_speed": 30,
                              "init_move_interval": 5,
                              "shot_cool_down": 5,
                              "enemy_shot_interval": 10,
                              "enemy_move_interval": 5,
                              "diver_move_interval": 5})


def step(rng_input, params, state, action):
    """ Perform single timestep state transition. """
    state = 0
    reward = 0
    done = False
    info = {}
    return get_obs(state), state, reward, done, info


def reset(rng_input, params):
    """ Reset environment state by sampling initial position. """
    state = {"oxygen": params["max_oxygen"],
             "diver_count": 0,
             "sub_x": 5,
             "sub_y": 0,
             "sub_or": False,
             "f_bullets": [],
             "e_bullets": [],
             "e_fish": [],
             "e_subs": [],
             "divers": [],
             "e_spawn_speed": params["init_spawn_speed"],
             "e_spawn_timer": params["init_spawn_speed"],
             "d_spawn_timer": params["diver_spawn_speed"],
             "move_speed": params["init_move_interval"],
             "ramp_index": 0,
             "shot_timer": 0,
             "surface": True,
             "terminal": False}
    return get_obs(state, params), state


def get_obs(state, params):
    """ Return observation from raw state trafo. """
    obs = jnp.zeros((10, 10, 10), dtype=bool)
    # Set agents sub-front and back, oxygen_gauge and diver_gauge
    obs = jax.ops.index_update(obs, jax.ops.index[state['sub_y'],
                                                  state['sub_x'], 0], 1)
    back_x = ((state["sub_x"] - 1) * state["sub_or"] +
              (state["sub_x"] + 1) * (1 - state["sub_or"]))
    obs = jax.ops.index_update(obs, jax.ops.index[state['sub_y'],
                                                  back_x, 1], 1)
    obs = jax.ops.index_update(obs, jax.ops.index[9,
                            0:state["oxygen"]*10//params["max_oxygen"], 7], 1)
    obs = jax.ops.index_update(obs, jax.ops.index[9, 9-state["diver_count"]:9,
                                                  8], 1)

    # Set friendly bulltes, enemy bullets, enemy fish+trail, enemey sub+trail
    for bullet in state["f_bullets"]:
        obs = jax.ops.index_update(obs, jax.ops.index[bullet[1], bullet[0],
                                                      2], 1)
    for bullet in state["e_bullets"]:
        obs = jax.ops.index_update(obs, jax.ops.index[bullet[1], bullet[0],
                                                      4], 1)

    for fish in state["e_fish"]:
        obs = jax.ops.index_update(obs, jax.ops.index[fish[1], fish[0], 5], 1)
        back_x = ((fish[0] - 1) * fish[2] +
                  (fish[0] + 1) * (1 - fish[2]))
        border_cond = jnp.logical_and(back_x >= 0, back_x <= 9)
        obs = (border_cond * jax.ops.index_update(obs, jax.ops.index[fish[1],
               back_x, 3], 1) + (1 - border_cond) * obs)

    for sub in state["e_subs"]:
        obs = jax.ops.index_update(obs, jax.ops.index[sub[1], sub[0], 6], 1)
        back_x = ((sub[0] - 1) * sub[2] +
                  (sub[0] + 1) * (1 - sub[2]))
        border_cond = jnp.logical_and(back_x >= 0, back_x <= 9)
        obs = (border_cond * jax.ops.index_update(obs, jax.ops.index[sub[1],
               back_x, 3], 1) + (1 - border_cond) * obs)

    for diver in state["divers"]:
        obs = jax.ops.index_update(obs, jax.ops.index[diver[1],diver[0], 9], 1)
        back_x = ((diver[0] - 1) * diver[2] +
                  (diver[0] + 1) * (1 - diver[2]))
        border_cond = jnp.logical_and(back_x >= 0, back_x <= 9)
        obs = (border_cond * jax.ops.index_update(obs, jax.ops.index[diver[1],
               back_x, 3], 1) + (1 - border_cond) * obs)
    return obs


reset_seaquest = jit(reset, static_argnums=(1,))
step_seaquest = jit(step, static_argnums=(1,))
