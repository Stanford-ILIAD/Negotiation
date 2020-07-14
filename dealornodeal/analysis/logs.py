import argparse
import os
import numpy as np
import json
import matplotlib.pyplot as plt
from collections import namedtuple, defaultdict

Agent = namedtuple('Agent', 'book hat ball')

Event = namedtuple('Event', 'agent_id event')


def get_label(filename):
  """
  Args:
    filename(str): The file name for which the data has been generated

  Returns: the name of the base file, without the extension

  Examples:
    >>> get_label('./foo/bar/hello.txt')
    hello
  """
  base = os.path.basename(filename)
  return os.path.splitext(base)[0]


def plot_hist(label, freqs):
  labels = sorted(freqs.keys(), key=lambda x: -freqs[x])  # Sort in reverse order
  men_means = [freqs[x] for x in labels]

  x = np.arange(len(labels))  # the label locations
  width = 0.35  # the width of the bars

  fig, ax = plt.subplots()
  rects1 = ax.bar(x, men_means, width, label=label)

  # Add some text for labels, title and custom x-axis tick labels, etc.
  ax.set_ylabel('Frequency')
  ax.set_title('Coarse Dialogue Act Frequencies')
  ax.set_xticks(x)
  ax.set_xticklabels(labels)
  ax.legend()

  def autolabel(rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
      height = rect.get_height()
      ax.annotate('{}'.format(height),
                  xy=(rect.get_x() + rect.get_width() / 2, height),
                  xytext=(0, 3),  # 3 points vertical offset
                  textcoords="offset points",
                  ha='center', va='bottom')

  autolabel(rects1)

  fig.tight_layout()

  plt.show()


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--files', nargs='+')
  parser.add_argument('--plot-hist', action='store_true')
  args = parser.parse_args()

  print 'Summary'
  print '{:55}|{:20}|{:20}|{:20}|{:20}|{:20}|{:20}|'.format(
    'Name',
    'Agreement Rate',
    'Average 1st Reward',
    'Average 2nd Reward',
    'First Domination',
    'Second Domination',
    'Compromise'
  )

  labels = []
  freqs = []

  for filename in args.files:
    data = json.load(open(filename))
    total_action_frequencies = defaultdict(int)
    n_success = 0
    n_first_domination = 0
    n_second_domination = 0
    total_reward = [0, 0]

    for example in data:
      success = example['outcome']['agreed'] and example['outcome']['valid_deal']
      if success:
        n_success += 1

        rewards = example['outcome']['reward']

        for k, v in rewards.iteritems():
          index = int(k)
          total_reward[index] += v

        if rewards['0'] != rewards['1']:
          if rewards['0'] == 0:
            n_second_domination += 1
          elif rewards['1'] == 0:
            n_first_domination += 1

      for e in example['events']:
        action = e['data'].split(' ')[0] if e['action'] == 'message' else 'Action({})'.format(e['action'])
        total_action_frequencies[action] += 1

    label = get_label(filename)
    n = len(data)
    print '{:55}|{:20.2f}|{:20.2f}|{:20.2f}|{:20.2f}|{:20.2f}|{:20.2f}|'.format(
      label,
      float(n_success) / n,
      float(total_reward[0]) / n,
      float(total_reward[1]) / n,
      float(n_first_domination) / n,
      float(n_second_domination) / n,
      float(n_success - n_first_domination - n_second_domination) / n
    )

    labels.append(label)
    freqs.append(total_action_frequencies)

  if args.plot_hist:
    for l, f in zip(labels, freqs):
      plot_hist(l, f)


if __name__ == '__main__':
  main()
