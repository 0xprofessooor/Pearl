import shutil

import gym
import numpy as np
import torch as T

from anvilrl.agents.base_agents import BaseDeepAgent, BaseEvolutionAgent
from anvilrl.buffers import ReplayBuffer
from anvilrl.common.enumerations import PopulationInitStrategy
from anvilrl.common.type_aliases import Log
from anvilrl.common.utils import set_seed
from anvilrl.models.actor_critics import Actor, ActorCritic, Critic, DeepIndividual
from anvilrl.models.encoders import IdentityEncoder
from anvilrl.models.heads import ContinuousQHead
from anvilrl.models.torsos import MLP
from anvilrl.settings import ExplorerSettings, LoggerSettings
from anvilrl.updaters.evolution import NoisyGradientAscent


class MockDeepAgent(BaseDeepAgent):
    def _fit(self, batch_size, actor_epochs=1, critic_epochs=1):
        return Log(actor_loss=0, critic_loss=0, entropy=0, divergence=0)


class MockEvolutionAgent(BaseEvolutionAgent):
    def _fit(self, epochs=1):
        return Log(actor_loss=0, critic_loss=0, entropy=0, divergence=0)


env = gym.make("Pendulum-v0")
envs = gym.vector.make("Pendulum-v0", num_envs=2, asynchronous=False)

encoder = IdentityEncoder()
torso = MLP(layer_sizes=[3, 64, 32], activation_fn=T.nn.ReLU)
head = ContinuousQHead(input_shape=32)
model = ActorCritic(
    actor=Actor(encoder, torso, head), critic=Critic(encoder, torso, head)
)
individual = DeepIndividual(encoder=encoder, torso=torso, head=head)

deep_agent = MockDeepAgent(
    env=env,
    model=model,
    buffer_class=ReplayBuffer,
    explorer_settings=ExplorerSettings(start_steps=0),
    logger_settings=LoggerSettings(tensorboard_log_path="runs/tests"),
)
vec_deep_agent = MockDeepAgent(
    env=envs,
    model=model,
    buffer_class=ReplayBuffer,
    explorer_settings=ExplorerSettings(start_steps=0),
    logger_settings=LoggerSettings(tensorboard_log_path="runs/tests"),
)
evolution_agent = MockEvolutionAgent(
    env=envs,
    model=individual,
    updater_class=NoisyGradientAscent,
    buffer_class=ReplayBuffer,
    logger_settings=LoggerSettings(tensorboard_log_path="runs/tests"),
)


def test_deep_step_env():
    set_seed(0, env)
    observation = env.reset()
    action = model(observation).detach().numpy()
    expected_next_obs, _, _, _ = env.step(action)
    set_seed(0, env)
    observation = env.reset()
    actual_next_obs = deep_agent.step_env(observation)
    np.testing.assert_array_equal(actual_next_obs, expected_next_obs)

    set_seed(0, env)
    observation = env.reset()
    final_episode = deep_agent.episode + 1
    for i in range(200):
        observation = deep_agent.step_env(observation)
        if i == 199:
            assert deep_agent.episode == final_episode
        else:
            assert deep_agent.episode != final_episode

    set_seed(0, envs)
    observation = envs.reset()
    action = model(observation).detach().numpy()
    expected_next_obs, _, _, _ = envs.step(action)
    set_seed(0, envs)
    observation = envs.reset()
    actual_next_obs = vec_deep_agent.step_env(observation)
    np.testing.assert_array_equal(actual_next_obs, expected_next_obs)


def test_deep_fit():
    deep_agent.step = 0
    deep_agent.episode = 0
    deep_agent.fit(num_steps=2, batch_size=1, train_frequency=("step", 1))
    assert deep_agent.episode == 0
    assert deep_agent.step == 2

    deep_agent.step = 0
    deep_agent.episode = 0
    deep_agent.fit(num_steps=200, batch_size=1, train_frequency=("episode", 1))
    assert deep_agent.step == 200
    assert deep_agent.episode == 1

    vec_deep_agent.step = 0
    vec_deep_agent.episode = 0
    vec_deep_agent.fit(num_steps=2, batch_size=1, train_frequency=("step", 1))
    assert vec_deep_agent.episode == 0
    assert vec_deep_agent.step == 2

    vec_deep_agent.step = 0
    vec_deep_agent.episode = 0
    vec_deep_agent.fit(num_steps=200, batch_size=1, train_frequency=("episode", 1))
    assert deep_agent.step == 200
    assert vec_deep_agent.episode == 1


def test_evolution_step_env():
    set_seed(0, envs)
    observations = envs.reset()
    population = evolution_agent.updater.initialize_population(
        PopulationInitStrategy.NORMAL, starting_point=individual.numpy()
    )
    action = np.array(
        [
            individual(observation)
            for individual, observation in zip(population, observations)
        ]
    )
    expected_next_obs, _, _, _ = envs.step(action)
    set_seed(0, envs)
    evolution_agent.population = evolution_agent.updater.initialize_population(
        PopulationInitStrategy.NORMAL, starting_point=individual.numpy()
    )
    observations = envs.reset()
    actual_next_obs = evolution_agent.step_env(observations)
    np.testing.assert_array_equal(actual_next_obs, expected_next_obs)


def test_evolution_fit():
    evolution_agent.step = 0
    evolution_agent.episode = 0
    evolution_agent.fit(num_steps=2, train_frequency=("step", 1))
    assert evolution_agent.episode == 0
    assert evolution_agent.step == 2

    evolution_agent.step = 0
    evolution_agent.episode = 0
    evolution_agent.fit(num_steps=200, train_frequency=("episode", 1))
    assert evolution_agent.step == 200
    assert evolution_agent.episode == 1


shutil.rmtree("runs/tests")
