import math
import random
from test import redis, flushdb


NUM_VALUES = 100000


def cdf(x, values):
  n1 = 0
  n2 = 0

  for v in values:
    n1 += 1 if v < x else 0
    n2 += 1 if v <= x else 0

  return (n1 + n2) / 2.0 / len(values)


def run_test_for_dist(redis, distfn):
  key = distfn.__name__
  redis.tdigest_new(key)

  quantiles = [0.001, 0.01, 0.1, 0.5, 0.9, 0.99, 0.999]
  values = []

  for _ in xrange(NUM_VALUES):
    v = distfn()
    redis.tdigest_add(key, v, 1)
    values.append(v)

  values = sorted(values)
  soft_errs = 0

  redis.tdigest_meta(key)

  for i, q in enumerate(quantiles):
    ix = NUM_VALUES * quantiles[i] - 0.5;
    idx = int(math.floor(ix))
    p = ix - idx;
    x = values[idx] * (1 - p) + values[idx + 1] * p;
    estimate_x = float(redis.tdigest_quantile(key, q)[0])
    estimate_q = float(redis.tdigest_cdf(key, x)[0])

    assert abs(q - estimate_q) < 0.005
    if abs(cdf(estimate_x, values) - q) > 0.005:
      soft_errs += 1
  assert soft_errs < 3


def test_uniform(redis, flushdb):
  def uniform():
    return random.uniform(-1, 1)
  run_test_for_dist(redis, uniform)


def test_gaussian(redis, flushdb):
  def gaussian():
    return random.gauss(0, 1)
  run_test_for_dist(redis, gaussian)


def test_beta(redis, flushdb):
  def beta():
    return random.betavariate(2, 2)
  run_test_for_dist(redis, beta)


def test_meta(redis, flushdb):
  redis.tdigest_new('test_meta0')
  redis.tdigest_new('test_meta1')
  redis.tdigest_new('test_meta2', compression=100)

  m0 = redis.tdigest_meta('test_meta0')
  m1 = redis.tdigest_meta('test_meta1')
  m2 = redis.tdigest_meta('test_meta2')

  assert m0[0] == m1[0]
  assert m2[0] == 100
  assert m0[1] == m1[1] == m2[1] == 0
  assert m0[2] == m1[2] == m2[2]

  for i in xrange(100):
    redis.tdigest_add('test_meta0', i, 1)
    redis.tdigest_add('test_meta1', i, 1)
    redis.tdigest_add('test_meta2', i, 1)

  m0 = redis.tdigest_meta('test_meta0')
  m1 = redis.tdigest_meta('test_meta1')
  m2 = redis.tdigest_meta('test_meta2')

  assert m0[0] == m1[0]
  assert m2[0] == 100
  assert m0[1] == m1[1] == m2[1] == 100
  assert m0[2] == m1[2] == m2[2]

  for i in xrange(1000):
    redis.tdigest_add('test_meta0', i, 1)
    redis.tdigest_add('test_meta1', i, 1)
    redis.tdigest_add('test_meta2', i, 1)

  m0 = redis.tdigest_meta('test_meta0')
  m1 = redis.tdigest_meta('test_meta1')
  m2 = redis.tdigest_meta('test_meta2')

  assert m0[0] == m1[0]
  assert m2[0] == 100
  assert m0[1] == m1[1]
  assert m0[1] > m2[1]
  assert m0[2] == m1[2]
  assert m0[2] > m2[2]


def test_mem_leak(redis, flushdb):
  redis.tdigest_new('test_mem_leak0')
  redis.tdigest_new('test_mem_leak1')

  for i in xrange(1000):
    redis.tdigest_add('test_mem_leak0', i, 1)
    redis.tdigest_add('test_mem_leak1', i, 1)

  # Compression forces storing < 1000 centroids
  assert redis.tdigest_meta('test_mem_leak0')[1] < 1000
  assert redis.tdigest_meta('test_mem_leak1')[1] < 1000

  start_rss_mem = redis.info()['used_memory_rss']

  for i in xrange(100000):
    redis.tdigest_add('test_mem_leak0', i, 1)
    redis.tdigest_add('test_mem_leak1', i, 1)
    if i % 1000 == 0:
      redis.tdigest_cdf('test_mem_leak0', random.randint(100, 1000))
      redis.tdigest_cdf('test_mem_leak1', random.randint(100, 1000))
    if i % 1000 == 500:
      redis.tdigest_quantile('test_mem_leak0', 0.4)
      redis.tdigest_quantile('test_mem_leak1', 0.8)

  end_rss_mem = redis.info()['used_memory_rss']

  # %age difference should be < 1%
  percent_diff = abs(end_rss_mem - start_rss_mem) / float(end_rss_mem)
  assert percent_diff < 0.01
