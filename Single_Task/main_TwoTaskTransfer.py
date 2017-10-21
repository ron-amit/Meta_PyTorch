from __future__ import absolute_import, division, print_function

import argparse

import torch
import torch.optim as optim


from Single_Task import learn_single_Bayes, learn_single_standard
from Utils import data_gen
from Utils.common import save_model_state, load_model_state, get_loss_criterion, write_result, set_random_seed

import Single_Task.learn_single_standard
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
                    default=50) # 200

parser.add_argument('--lr', type=float, help='initial learning rate',
                    default=1e-3)

parser.add_argument('--seed', type=int,  help='random seed',
                    default=55)

parser.add_argument('--test-batch-size',type=int,  help='input batch size for testing',
                    default=1000)

parser.add_argument('--log-file', type=str, help='Name of file to save log (default: no save)',
                    default='log')


prm = parser.parse_args()
prm.cuda = True

prm.data_path = '../data'

set_random_seed(prm.seed)

#  Define model:
prm.model_name = 'ConvNet'   # 'FcNet2' / 'FcNet3' / 'ConvNet' / 'ConvNet_Dropout'

# Weights initialization:
prm.init_override = None # {'bias': 0, 'std': 0.1}
# None = use default initializer

#  Define optimizer:
prm.optim_func, prm.optim_args = optim.Adam,  {'lr': prm.lr}
# optim_func, optim_args = optim.SGD, {'lr': prm.lr, 'momentum': 0.9}

# Learning rate decay schedule:
# lr_schedule = {'decay_factor': 0.1, 'decay_epochs': [10]}
prm.lr_schedule = {} # No decay

n_expirements = 10
test_err_orig_avg = 0
test_err_scratch_avg = 0
test_err_transfer_avg = 0

for i_exp in range(n_expirements):
    write_result('-' * 5 + ' Expirement #{} out of {}'.format(i_exp, n_expirements), prm.log_file)

    # Generate the task #1 data set:
    task1_data = data_gen.get_data_loader(prm)
    n_samples_orig = task1_data['n_train_samples']

    #  Run learning of task 1
    write_result('-'*5 + 'Standard learning of task #1' + '-'*5, prm.log_file)
    test_err_orig, transfered_model = learn_single_standard.run_learning(task1_data, prm)

    # Generate the task 2 data set:
    limit_train_samples = 2000
    write_result('-'*5 + 'Generating task #2 with at most {} samples'.format(limit_train_samples) + '-'*5, prm.log_file)
    task2_data = data_gen.get_data_loader(prm, limit_train_samples = limit_train_samples)

    #  Run learning of task 2 from scratch:
    write_result('-'*5 + 'Standard learning of task #2 from scratch' + '-'*5, prm.log_file)
    test_err_scratch, _ = learn_single_standard.run_learning(task2_data, prm, verbose=0)

    #  Run learning of task 2 using transferred initial point:
    write_result('-'*5 + 'Standard learning of task #2 using transferred weights as initial point' + '-'*5, prm.log_file)
    test_err_transfer, _ = learn_single_standard.run_learning(task2_data, prm, initial_model=transfered_model, verbose=0)

    test_err_orig_avg += (1 / n_expirements) * test_err_orig
    test_err_scratch_avg += (1 / n_expirements) * test_err_scratch
    test_err_transfer_avg += (1 / n_expirements) * test_err_transfer

write_result('-'*5 + ' Final Results: '+'-'*5, prm.log_file)
write_result('Averaging of {} expirements...'.format(n_expirements), prm.log_file)

write_result('Standard learning of task #1 ({} samples), average test error: {}'.
             format(n_samples_orig, 100*test_err_orig_avg), prm.log_file)

write_result('Standard learning of task #2  (at most {} samples) from scratch, average test error: {}'.
             format(limit_train_samples, 100*test_err_scratch_avg), prm.log_file)

write_result('Standard learning of task #2  (at most {} samples) using transferred weights as initial point, average test error: {}'.
             format(limit_train_samples, 100*test_err_transfer_avg), prm.log_file)

