import random
import math
from environment import Agent, Environment
from planner import RoutePlanner
from simulator import Simulator
import operator


class LearningAgent(Agent):
    """ An agent that learns to drive in the Smartcab world.
        This is the object you will be modifying. """ 

    def __init__(self, env, learning=False, epsilon=1.0, alpha=0.5, edecay=None, adecay=None):
        """
        
        :param env:
        :param learning:
        :param epsilon:
        :param alpha:
        :param edecay: Espilon Decay
            - None = No decay
            - (float) = linear decay rate
            - "a^t" = alpha to the power of time step.
            - "a" =  same value as alpha
            - "a2" = alpha^2
            - "1/t2" = 1/(t^2)
            - "1/t" = 1/t
            - "eat" = e ^ (-alpha * t)
            - "ert" followed by anything that could be converted to a
                float, eg "ert0.05" = e^(-0.05 * t)
            - "et" = e^(-t)
            - "cat" = cos(alpha * t)
            - "inv_sigmoid_k...o..." where there is a float just after the k,
               and o. Creates an inverse sigmoid parameterized by k, which
               controls how quickly it decays, and o which is the offset, which
               controls what portion of the sigmoid curve to start at for time 0
            - "r" followed by any number that could be converted
                          to a float and interpreted as a percentage.
                          eg, "r99.5". The espilon value decays at each time step
                          by that percentage.
                                          
        :param adecay: Alpha Decay
                - (float) linear decay rate
                - "1/t"  = 1/t
                - "1/t2" = 1/t^2
                - "1/logt" = 1/log(t + e - 1)
                - "r" followed by any number that could be converted
                          to a float and interpreted as a percentage.
                          eg, "r99.5". The alpha value decays at each time step
                          by that percentage.
                - "cr99.5" same as above, but the alpha decay is capped to a
                           minumum value of 0.001.
        
        """
        super(LearningAgent, self).__init__(env)     # Set the agent in the evironment 
        self.planner = RoutePlanner(self.env, self)  # Create a route planner
        self.valid_actions = self.env.valid_actions  # The set of valid actions

        # Set parameters of the learning agent
        self.learning = learning # Whether the agent is expected to learn
        self.Q = dict()          # Create a Q-table which will be a dictionary of tuples
        self.epsilon = epsilon   # Random exploration factor
        self.epsilon_init = epsilon
        self.alpha = alpha       # Learning factor

        self.train_iteration = 0
        self.init_qval = 0.0  # initial Q values
        self.edecay =  edecay
        self.adecay = adecay
        self.t = 0
        


    def reset(self, destination=None, testing=False):
        """ The reset function is called at the beginning of each trial.
            'testing' is set to True if testing trials are being used
            once training trials have completed. """

        # Select the destination as the new location to route to
        self.planner.route_to(destination)
        
        self.state = self.build_state()
        self.reward = 0
        self.t += 1
        
        # If 'testing' is True, set epsilon and alpha to 0
        if testing:
            self.epsilon = 0
            self.alpha = 0
        else:
            # ALPHA DECAY
            if type(self.adecay)is float:
                self.alpha -= self.adecay  # linear decay rate for alpha
            elif self.adecay == "1/t":
                self.alpha = 1.0 / (self.t)
            elif self.adecay == "1/t2":
                self.alpha = 1.0 / (self.t ** 2)
            elif self.adecay == "1/logt":
                self.alpha = 1.0/math.log((self.t + math.e - 1))
            elif self.adecay == "half":
                self.alpha = self.alpha/2.0
            elif type(self.adecay) is str and self.adecay.startswith("r"):
                r = float(self.adecay[1:]) / 100.
                self.alpha = r*self.alpha
            elif type(self.adecay) is str and self.adecay.startswith("cr"):
                # Capped rate (capped to a min alpha val of 0.005)
                r = float(self.adecay[2:]) / 100.
                self.alpha = max(r*self.alpha, 0.001)

            # EPSILON DECAY
            if type(self.edecay) is float:
                self.epsilon -= self.edecay # linear decay rate for epsilon
            elif self.edecay == "a^t":
                self.epsilon = self.alpha**self.t
            elif self.edecay == "a":
                self.epsilon = self.alpha
            elif self.edecay == "a2":
                self.epsilon = self.alpha**2
            elif self.edecay == "1/t2":
                self.epsilon = 1.0/ (self.t**2)
            elif self.edecay == "1/t":
                self.epsilon = 1.0 / (self.t)
            elif self.edecay == "eat":
                self.epsilon = math.e ** (-self.alpha * self.t)
            elif type(self.edecay) is str and self.edecay.startswith("ert"):
                r = float(self.edecay[3:])
                self.epsilon = math.e ** (-r * self.t)
            elif self.edecay == "et":
                self.epsilon = math.e ** (-self.t)
            elif self.edecay == "cat":
                self.epsilon = math.cos(self.alpha * self.t)
            elif type(self.edecay) is str and self.edecay.startswith("r"):
                r = float(self.edecay[1:]) / 100.
                self.epsilon = r*self.epsilon
            elif type(self.edecay) is str and self.edecay.startswith("inv_sigmoida"):
                #s = "inv_sigmoid_k2.6o60"
                k, offset = [float(val) for val in self.edecay.split("k")[1].split("o")]
                # self.trial_count = self.trial_count + 1
                self.epsilon = 1 - (1 / (1 + math.exp(-k * self.alpha * (self.t - offset))))
            elif type(self.edecay) is str and self.edecay.startswith("inv_sigmoid"):
                k, offset = [float(val) for val in self.edecay.split("k")[1].split("o")]
                # self.trial_count = self.trial_count + 1
                self.epsilon = 1 - (1 / (1 + math.exp(-k * (self.t - offset))))
        return None


    def build_state(self):
        """ The build_state function is called when the agent requests data from
            the environment. The next waypoint, the intersection inputs, and the
            deadline are all features available to the agent.
        """
        # Collect data about the environment
        waypoint = self.planner.next_waypoint() # The next waypoint 
        inputs = self.env.sense(self)           # Visual input - intersection light and traffic
        deadline = self.env.get_deadline(self)  # Remaining deadline

        input_keys = ['light', 'oncoming', 'left']
        state = tuple(inputs[key] for key in input_keys)
        state += (waypoint,)
        return state


    def get_maxQ(self, state):
        """ The get_max_Q function is called when the agent is asked to find the
            maximum Q-value of all actions based on the 'state' the smartcab is in. """

        if state in self.Q:
            Q_vals = self.Q[state]
            maxQ = max(Q_vals.iteritems(), key=operator.itemgetter(1))[1]
        else:
            # Handle the case where state is not in self.Q
            maxQ = random.choice(self.valid_actions)
    
        return maxQ


    def createQ(self, state):
        """ The createQ function is called when a state is generated by the agent. """

        # When learning, check if the 'state' is not in the Q-table
        # If it is not, create a new dictionary for that state
        #   Then, for each action available, set the initial Q-value to 0.0
        if self.learning and state not in self.Q:
            self.Q[state] = {action: self.init_qval for action in
                                  self.valid_actions}
        
        return None


    def choose_action(self, state):
        """ The choose_action function is called when the agent is asked to choose
            which action to take, based on the 'state' the smartcab is in. """

        # Set the agent state and default action
        self.state = state
        self.next_waypoint = self.planner.next_waypoint()
        # action = random.choice(self.valid_actions)
        
        # When learning, choose a random action with 'epsilon' probability
        #   Otherwise, choose an action with the highest Q-value for the current state
        if self.learning:
            # With a probability of epsilon, chose an action at random
            # (but only if it is in the learning phase)
            if (random.random() < self.epsilon):
                action = random.choice(self.valid_actions)

            # Otherwise select the action that has the highest expected value..
            else:
                # Chose the action with the  highest Q value. For multiple
                # actions with equally high Q values, select one at random
                Q_vals = self.Q[state]
                maxval = max(Q_vals.iteritems(), key=operator.itemgetter(1))[1]
                maxacts = [act for act in Q_vals if Q_vals[act] == maxval]
                action = random.choice(maxacts)

        else:
            # When not learning, choose a random action
            action = random.choice(self.valid_actions)

        return action


    def learn(self, state, action, reward):
        """ The learn function is called after the agent completes an action and
            receives an award. This function does not consider future rewards 
            when conducting learning. """

        # When learning, implement the value iteration update rule
        #   Use only the learning rate 'alpha' (do not use the discount factor 'gamma')
        if self.learning:
            Qval = self.Q[state][action]
            Qval += self.alpha * (reward - Qval) # Without considering future rewards
            self.Q[state][action] = Qval
        print("ALPHA: {}  EPSILON: {}".format(self.alpha, self.epsilon))
        print("ADECAY: {}  EDECAY: {}".format(self.adecay, self.edecay))
        return


    def update(self):
        """ The update function is called when a time step is completed in the 
            environment for a given trial. This function will build the agent
            state, choose an action, receive a reward, and learn if enabled. """

        state = self.build_state()          # Get current state
        self.createQ(state)                 # Create 'state' in Q-table
        action = self.choose_action(state)  # Choose an action
        reward = self.env.act(self, action) # Receive a reward
        self.learn(state, action, reward)   # Q-learn

        return
        

def run():
    """ Driving function for running the simulation. 
        Press ESC to close the simulation, or [SPACE] to pause the simulation. """

    ##############
    # Create the environment
    # Flags:
    #   verbose     - set to True to display additional output from the simulation
    #   num_dummies - discrete number of dummy agents in the environment, default is 100
    #   grid_size   - discrete number of intersections (columns, rows), default is (8, 6)
    env = Environment(num_dummies=100, grid_size=[8,6])
    
    ##############
    # Create the driving agent
    # Flags:
    #   learning   - set to True to force the driving agent to use Q-learning
    #    * epsilon - continuous value for the exploration factor, default is 1
    #    * alpha   - continuous value for the learning rate, default is 0.5
    # agent = env.create_agent(LearningAgent, learning=True, epsilon=1.0, alpha=0.5, edecay=0.05, adecay=None)
    agent = env.create_agent(LearningAgent, learning=True, epsilon=1.0, alpha=0.15, edecay="inv_sigmoid_k0.03o100", adecay=None)
    

    ##############
    # Follow the driving agent
    # Flags:
    #   enforce_deadline - set to True to enforce a deadline metric
    env.set_primary_agent(agent, enforce_deadline=True)

    ##############
    # Create the simulation
    # Flags:
    #   update_delay - continuous time (in seconds) between actions, default is 2.0 seconds
    #   display      - set to False to disable the GUI if PyGame is enabled
    #   log_metrics  - set to True to log trial and simulation results to /logs
    #   optimized    - set to True to change the default log file name
    sim = Simulator(env, display=False, update_delay=0.00001, log_metrics=True, optimized=True)
    
    ##############
    # Run the simulator
    # Flags:
    #   tolerance  - epsilon tolerance before beginning testing, default is 0.05 
    #   n_test     - discrete number of testing trials to perform, default is 0
    sim.run(n_test=100, tolerance=0.001)


if __name__ == '__main__':
    run()
