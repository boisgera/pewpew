# Python 3 Standard Library
import inspect
import operator

# Third-Party Libraries
import numpy as np
import numpy.random as npr
import scipy.special as ss
import wrapt

# We need to support : random init, custom seed it, continuation (save/restore)
# What should be the default ? Init at 0 or None ? I'd rather fo with 0 here,
# right ? And the experts could set the seed to None to get a random init.
# But by default we are deterministic.

# Yes, i'd probably rather have restart and save external ...

# UPDATE : changed the design to be more vector-friendly. Consequences :
# the nature of every random variable as a function of omega is more explicit
# (but the very easy use cases are slightly more verbose) and Omega is now
# a different beast (not the API of a random thingy anymore).

# NOTE : X(Omega(10)) and np.array([X(Omega(1)) for _ in range(10)]
# won't generate the same numbers, even if the universe state is the
# same to begin with. Because the generation of numpy.random works the
# same (generation of random arrays and looping or partial array generation
# won't generate the same results). NAAAAAAAH. This is probably a mistake,
# check this and make a test to confirm ; first check this at low-level
# (numpy.random), then in my code.

class Universe: # actually, looks like a random VECTOR, the only one in town so far. Funny :)
    # I am going to break this, by replacing the omega argument (useless), with
    # a size
    def __call__(self, size=None):
        if size is None:
            output_size = (self.n,)
        elif isinstance(size, int):
            output_size = (self.n, size)
        else: # tuple -- TODO check
            output_size = (self.n,) + size
        return self.rng.uniform(size=output_size)


# TODO : need to make all distributions universe-dependent ? Urk :(
# Or single universe at a time ? And maybe a with construct ? So that
# in any VA invocation, a universe is bound ?

Omega = Universe() # the universe (as long as we sample the variables only once ;
# otherwise the "true" univers is the cartesian product of this one).
# Here U is the "universal" random vector, that sums up everything there is
# to know about the universe.

def restore(snapshot=None):
    if snapshot is None:
        snapshot = (0, 0)
    n, state = snapshot
    Omega.ss = np.random.SeedSequence(state)
    Omega.rng = npr.default_rng(Omega.ss)
    Omega.n = n        

restart = restore
restore()

def save():
    snapshot = (Omega.n, Omega.ss.entropy)
    return snapshot

# ------------------------------------------------------------------------------

# TODO: these functions already exist in the operator module, don't redeclare them.
def __add__(x, y):
    return x + y

def __mul__(x, y):
    return x * y

def __sub__(x, y):
    return x - y

def __rsub__(x, y):
    return y - x

def __div__(x, y):
    return x / y

def __rdiv__(x, y):
    return y / x

def __pos__(x):
    return x

def __neg__(x):
    return - x

def __bool__(x):
    return bool(x)

class RandomVariable:
    def __call__(omega):
        raise NotImplementedError()
    # Binary operators
    def __add__(self, other):
        return function(__add__)(self, other) # wrapped each and every time ? This is ugly.
        # at the moment I can't make it work otherwise. Probably because I don't understand
        # what wrapt is doing, I should probably get rid of it.
        # There is at least one level of nesting I can get rid of (the decoration
        # can be done at class definition time and the result stored in it).
    __radd__ = __add__
    def __sub__(self, other):
        return function(__sub__)(self, other)
    def __rsub__(self, other):
        return function(__rsub__)(self, other)
    def __mul__(self, other):
        return function(__mul__)(self, other)
    __rmul__ = __mul__
    def __div__(self, other):
        return function(__div__)(self, other)
    def __rdiv__(self, other):
        return function(__div__)(self, other)
    # TODO: divmod, pow, lshift, rshift, and, xor, or

    def __lt__(self, other):
        return function(operator.lt)(self, other)
    def __le__(self, other):
        return function(operator.le)(self, other)
    def __eq__(self, other):
        return function(operator.eq)(self, other)
    def __ne__(self, other):
        return function(operator.ne)(self, other)
    def __ge__(self, other):
        return function(operator.ge)(self, other)
    def __gt__(self, other):
        return function(operator.gt)(self, other)

    # Unary operators
    def __neg__(self):
        return function(__neg__)(self)
    def __pos__(self):
        return function(__pos__)(self)
    def __bool__(self):
        return function(__bool__)(self)
    # TODO : abs, invert, complex, int, long, float, oct, hex.

def randomize(value):
    if isinstance(value, RandomVariable):
        return value
    else:
        return Constant(value)

class Constant(RandomVariable):
    def __init__(self, value):
        # Yep, the value of a constant can be randomized too.
        if isinstance(value, RandomVariable): 
            self.rv = value
        else:
            self.rv = lambda u: value
    def __call__(self, omega=None):
        return self.rv(omega)

# Distributions
# ------------------------------------------------------------------------------
class Uniform(RandomVariable):
    def __init__(self, low=0.0, high=1.0):
        self.n = Omega.n
        Omega.n += 1
        self.low = randomize(low)
        self.high = randomize(high)
    def __call__(self, omega):
        u_n = omega[self.n] # localized abstraction leak HERE.
        return self.low(omega) * (1 - u_n) + self.high(omega) * u_n

class Bernoulli(RandomVariable):
    def __init__(self, p=0.5):
        self.U = Uniform()
        self.P = randomize(p)
    def __call__(self, omega):
        u = self.U(omega)
        p = self.P(omega)
        return u <= p

class Normal(RandomVariable):
    def __init__(self, mu=0.0, sigma=1.0):
        self.U = Uniform()
        self.mu = randomize(mu)
        self.sigma = randomize(sigma)
    def __call__(self, omega):
        u = self.U(omega)
        mu = self.mu(omega)
        sigma = self.sigma(omega)
        return ss.erfinv(2*u - 1) * np.sqrt(2) * sigma + mu

class Exponential(RandomVariable):
    def __init__(self, lambda_=1.0):
        self.U = Uniform()
        self.lambda_ = randomize(lambda_)
    def __call__(self, omega):
        u = self.U(omega)
        lambda_ = self.lambda_(omega)
        return - np.log(1 - u) / lambda_

class Cauchy(RandomVariable):
    def __init__(self, x0=0.0, gamma=1.0):
        self.U = Uniform()
        self.x0 = randomize(x0)
        self.gamma = randomize(gamma)
    def __call__(self, omega=None):
        u = self.U(omega)
        x0 = self.x0(omega)
        gamma = self.gamma(omega)
        return x0 + gamma * np.tan(np.pi * (u - 0.5))

# ------------------------------------------------------------------------------

@wrapt.decorator
def function(wrapped, instance, args, kwargs):
    # if instance is not None: # Nah, forget about this ATM
    #     args = [instance] + list(args)
    all_args = list(args) + list(kwargs.values())
    if not any(isinstance(arg, RandomVariable) for arg in all_args):
        return wrapped(*args, **kwargs)
    class Deterministic(RandomVariable):
        def __init__ (self, *args, **kwargs): # TODO: I'd like these args and 
            # kwargs to have wrapped signature and be checked against it ...
            # Does it work by default ?
            self.args = [randomize(arg) for arg in args]
            self.kwargs = {k: randomize(v) for k, v in kwargs.items()}
        def __call__(self, omega):
            args_values = [arg(omega) for arg in self.args]
            kwargs_values = {k: v(omega) for k, v in kwargs.items()}
            return wrapped(*args_values, **kwargs_values)
    return Deterministic(*args, **kwargs)

for name in dir(np):
    item = getattr(np, name)
    if isinstance(item, np.ufunc):
        globals()[name] = function(item)


if False:
    import matplotlib.pyplot as pp
    import scipy.stats as ss
    U = Uniform()
    data = [U() for _ in range(10000)]
    #print(data)
    pp.hist(data, bins=100, range=(-2,2), density=True, color="blue", alpha=0.25)
    kernel = ss.gaussian_kde(data)
    x = np.arange(-2, 2, 0.01)
    pp.plot(x, kernel(x), color="blue")
    pp.show()
