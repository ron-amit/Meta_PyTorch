
from __future__ import absolute_import, division, print_function

import argparse

import torch
import torch.optim as optim

from Stochsastic_Meta_Learning import meta_testing_Bayes, meta_training_Bayes
from Models import models_Bayes
from Single_Task import learn_single_Bayes, learn_single_standard
from Utils import data_gen
from Utils.common import save_model_state, load_model_state, get_loss_criterion, write_result

# torch.backends.cudnn.benchmark=True # For speed improvement with convnets with fixed-length inputs - https://discuss.pytorch.org/t/pytorch-performance/3079/7


# -------------------------------------------------------------------------------------------
#  Set Parameters
# -------------------------------------------------------------------------------------------

# Training settings
parser = argparse.ArgumentParser()

parser.add_argument('--data-source', type=str, help="Data: 'MNIST' / 'Sinusoid' ",
                    default='MNIST')

parser.add_argument('--data-transform', type=str, help="Data transformation: 'None' / 'Permute_Pixels' / 'Permute_Labels'",
                    default='Permute_Labels')

parser.add_argument('--loss-type', type=str, help="Data: 'CrossEntropy' / 'L2_SVM'",
                    default='CrossEntropy')

parser.add_argument('--batch-size', type=int, help='input batch size for training',
                    default=128)

parser.add_argument('--num-epochs', type=int, help='number of epochs to train',
                    default=200) # 200

parser.add_argument('--lr', type=float, help='initial learning rate',
                    default=1e-3)

parser.add_argument('--seed', type=int,  help='random seed',
                    default=1)

parser.add_argument('--no-cuda', action='store_true', default=False, help='disables CUDA training')

parser.add_argument('--test-batch-size',type=int,  help='input batch size for testing',
                    default=1000)

parser.add_argument('--log-file', type=str, help='Name of file to save log (default: no save)',
                    default='log')

prm = parser.parse_args()
prm.cuda = not prm.no_cuda and torch.cuda.is_available()

prm.data_path = './data'

torch.manual_seed(prm.seed)

#  Define model type (hypothesis class):
model_type = 'BayesNN' # 'BayesNN' \ 'BigBayesNN'
model_type_standard = 'FcNet'#  for comparision

# Weights initialization:
prm.log_var_init_std = 0.1
prm.log_var_init_bias = -10
prm.mu_init_std = 0.1
prm.mu_init_bias = 0.0
# Note:
# 1. start with small sigma - so gradients variance estimate will be low
# 2.  don't init with too much variance so that complexity term won;t be too large


# Number of Monte-Carlo iterations (for re-parametrization trick):
prm.n_MC = 3

# Loss criterion
loss_criterion = get_loss_criterion(prm.loss_type)

#  Define optimizer:
optim_func, optim_args = optim.Adam,  {'lr': prm.lr,} #'weight_decay': 1e-4
# optim_func, optim_args = optim.SGD, {'lr': prm.lr, 'momentum': 0.9}

# Learning rate decay schedule:
#lr_schedule = {'decay_factor': 0.1, 'decay_epochs': [150]}
lr_schedule = {} # No decay

# Meta-alg params:
prm.complexity_type = 'PAC_Bayes_McAllaster'   #  'Variational_Bayes' / 'PAC_Bayes_McAllaster' / 'KLD' / 'NoComplexity'
prm.hyper_prior_factor = 1e-6  #  1e-5
# Note: Hyper-prior is important to keep the sigma not too low.
# Choose the factor  so that the Hyper-prior  will be in the same order of the other terms.

init_from_prior = True  #  False \ True . In meta-testing -  init posterior from learned prior

# Learning parameters:
# In the stage 1 of the learning epochs, epsilon std == 0
# In the second stage it increases linearly until reaching std==1 (full eps)
prm.stage_1_ratio = 0.0  # 0.05
prm.full_eps_ratio_in_stage_2 = 0.3
# Note:

# Test type:
prm.test_type = 'MaxPosterior' # 'MaxPosterior' / 'MajorityVote'

# -------------------------------------------------------------------------------------------
# Generate the data sets of the training tasks:
# -------------------------------------------------------------------------------------------
n_train_tasks = 5
# Why it worked with just one task???
train_tasks_data = [data_gen.get_data_loader(prm) for i_task in range(n_train_tasks)]

# -------------------------------------------------------------------------------------------
#  Run Meta-Training
# -------------------------------------------------------------------------------------------

mode = 'MetaTrain'  # 'MetaTrain'  \ 'LoadPrior' \ 'FromScratch'
dir_path = './data'
f_name='prior'


if mode == 'MetaTrain':
    # Meta-training to learn prior:
    prior_model = meta_training_Bayes.run_meta_learning(train_tasks_data,
                                                        prm, model_type, optim_func, optim_args, loss_criterion, lr_schedule)
    # save learned prior:
    f_path = save_model_state(prior_model, dir_path, name=f_name)
    print('Trained prior saved in ' + f_path)

elif mode == 'LoadPrior':
    # Loads  previously training prior.
    # First, create the model:
    prior_model = models_Bayes.get_bayes_model(model_type, prm)
    # Then load the weights:
    load_model_state(prior_model, dir_path, name=f_name)
    print('Pre-trained  prior loaded from ' + dir_path)

# -------------------------------------------------------------------------------------------
# Generate the data sets of the test tasks:
# -------------------------------------------------------------------------------------------

n_test_tasks = 5
limit_train_samples = 1000
test_tasks_data = [data_gen.get_data_loader(prm, limit_train_samples) for _ in range(n_test_tasks)]

write_result('-'*5 + 'Meta-Testing with {} test-tasks with at most {} training samples'.
                 format(n_test_tasks, limit_train_samples)+'-'*5, prm.log_file)
# -------------------------------------------------------------------------------------------
#  Run Meta-Testing
# -------------------------------------------------------------------------------

test_err_avg = 0
for i_task in range(n_test_tasks):
    print('Meta-Testing task {} out of {}...'.format(i_task, n_test_tasks))
    task_data = test_tasks_data[i_task]
    if mode == 'FromScratch':
        test_err = learn_single_Bayes.run_learning(task_data, prm, model_type, optim_func, optim_args, loss_criterion, lr_schedule)
    else:
        test_err = meta_testing_Bayes.run_learning(task_data, prior_model, prm,
                                                   model_type, optim_func, optim_args, loss_criterion,
                                                   lr_schedule, init_from_prior, verbose=0)
    test_err_avg += test_err / n_test_tasks


# -------------------------------------------------------------------------------------------
#  Compare to standard learning
# -------------------------------------------------------------------------------------------

test_err_avg2 = 0
for i_task in range(n_test_tasks):
    print('Standard learning task {} out of {}...'.format(i_task, n_test_tasks))
    task_data = test_tasks_data[i_task]
    test_err = learn_single_standard.run_learning(task_data, prm, model_type_standard,
                                                  optim_func, optim_args, loss_criterion, lr_schedule, verbose=0)
    test_err_avg2 += test_err / n_test_tasks


# -------------------------------------------------------------------------------------------
#  Print results
# -------------------------------------------------------------------------------------------
write_result('-'*5 + ' Final Results: '+'-'*5, prm.log_file)
write_result('Meta-Testing - Avg test err: {0}%'.format(100 * test_err_avg), prm.log_file)
write_result('Standard - Avg test err: {0}%'.format(100 * test_err_avg2), prm.log_file)