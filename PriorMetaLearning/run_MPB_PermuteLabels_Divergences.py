from subprocess import call
import argparse

n_train_tasks = 5

parser = argparse.ArgumentParser()

parser.add_argument('--complexity_type', type=str,
                    help=" The learning objective complexity type",
                    default='NewBoundSeeger')
# 'NoComplexity' /  'Variational_Bayes' / 'PAC_Bayes_Pentina'   NewBoundMcAllaster / NewBoundSeeger'"

args = parser.parse_args()

complexity_type = args.complexity_type

divergence_type = 'Wasserstein' # 'KL' / 'Wasserstein' / Wasserstein_NoSqrt

call(['python', 'main_Meta_Bayes.py',
      '--run-name', 'PermutedLabels_{}_Tasks_{}_Divergence_{}'.format(n_train_tasks, complexity_type, divergence_type),
      '--data-source', 'MNIST',
      '--data-transform', 'Permute_Labels',
      '--limit_train_samples_in_test_tasks', '2000',
      '--n_train_tasks',  str(n_train_tasks),
      '--mode', 'LoadMetaModel',  # MetaTrain / LoadMetaModel
      '--complexity_type',  complexity_type,
      '--model-name', 'ConvNet3',
      '--n_meta_train_epochs', '150',
      '--n_meta_test_epochs', '200',
      '--n_test_tasks', '20',
      '--meta_batch_size', '16',
      '--divergence_type', divergence_type,
      '--init_from_prior', 'False',
      ])
