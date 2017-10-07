


from __future__ import absolute_import, division, print_function

from datetime import datetime
import glob
import os
import shutil
from torch.autograd import Variable
import torch.nn as nn
import torch


# -----------------------------------------------------------------------------------------------------------#
# General - PyTorch
# -----------------------------------------------------------------------------------------------------------#

# Get the parameters from a model:
def get_param_from_model(model, param_name):
    return [param for (name, param) in model.named_parameters() if name == param_name][0]

def zeros_gpu(size):
    return torch.cuda.FloatTensor(*size).fill_(0)

def randn_gpu(size, mean=0, std=1):
    return torch.cuda.FloatTensor(*size).normal_(mean, std)


def count_correct(outputs, targets):
    ''' Deterimne the class prediction by the max output and compare to ground truth'''
    pred = outputs.data.max(1, keepdim=True)[1] # get the index of the max output
    return pred.eq(targets.data.view_as(pred)).cpu().sum()


def correct_rate(outputs, targets):
    n_correct = count_correct(outputs, targets)
    return n_correct / outputs.size()[0]


def save_models_dict(models_dict, dir_path):

    for name in models_dict:
        save_model_state(models_dict[name], dir_path, name)

def save_model_state(model, dir_path, name):

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    f_path = dir_path + '/' + name + '.pt'
    with open(f_path, 'wb') as f_pointer:
        torch.save(model.state_dict(), f_pointer)
    return f_path


def load_models_dict(models_dict, dir_path):
    ''' Load models '''
    for name in models_dict:
        load_model_state(models_dict[name], dir_path, name)

def load_model_state(model, dir_path, name):

    f_path = dir_path + '/' + name + '.pt'
    with open(f_path, 'rb') as f_pointer:
        model.load_state_dict(torch.load(f_pointer))


# -------------------------------------------------------------------------------------------
#  Regularization
# -------------------------------------------------------------------------------------------

def net_L1_norm(model):
    l1_crit = torch.nn.L1Loss(size_average=False)
    total_norm = 0
    for param in model.parameters():
        target = Variable(zeros_gpu(param.size()), requires_grad=False)  # dummy target
        total_norm += l1_crit(param, target)
    return total_norm


# -----------------------------------------------------------------------------------------------------------#
# Optimizer
# -----------------------------------------------------------------------------------------------------------#
# Gradient step function:
def grad_step(objective, optimizer, lr_schedule=None, initial_lr=None, i_epoch=None):
    if lr_schedule:
        adjust_learning_rate_schedule(optimizer, i_epoch, initial_lr, **lr_schedule)
    optimizer.zero_grad()
    objective.backward()
    # clip_grad_norm(***.parameters(), 5.)
    optimizer.step()


def adjust_learning_rate_interval(optimizer, epoch, initial_lr, gamma, decay_interval):
    """Sets the learning rate to the initial LR decayed by gamma every decay_interval epochs"""
    lr = initial_lr * (gamma ** (epoch // decay_interval))
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr


def adjust_learning_rate_schedule(optimizer, epoch, initial_lr, decay_factor, decay_epochs):
    """The learning rate is decayed by decay_factor at each interval start """

    # Find the index of the current interval:
    interval_index = len([mark for mark in decay_epochs if mark < epoch])

    lr = initial_lr * (decay_factor ** interval_index)
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr


# -----------------------------------------------------------------------------------------------------------#
#  Configuration
# -----------------------------------------------------------------------------------------------------------#

def get_loss_criterion(loss_type):
# Note: the loss use the un-normalized net outputs (scores, not probabilities)

    criterion_dict = {'CrossEntropy':nn.CrossEntropyLoss(size_average=True),
                 'L2_SVM':nn.MultiMarginLoss(p=2, margin=1, weight=None, size_average=True)}

    return criterion_dict[loss_type]


# -----------------------------------------------------------------------------------------------------------#
# Prints
# -----------------------------------------------------------------------------------------------------------#

def status_string(i_epoch, batch_idx, n_batches, prm, batch_acc, loss_data):

    progress_per = 100. * (i_epoch * n_batches + batch_idx) / (n_batches * prm.num_epochs)
    return ('({:2.1f}%)\tEpoch: {:3} \t Batch: {:4} \t Objective: {:.4} \t  Acc: {:1.3}\t'.format(
        progress_per, i_epoch + 1, batch_idx, loss_data, batch_acc))

def get_model_string(model):
    return str(model.model_type)+ ': ' + '-> '.join([m.__str__() for m in model._modules.values()])

# -----------------------------------------------------------------------------------------------------------#
# Result saving
# -----------------------------------------------------------------------------------------------------------#

def write_result(str, log_file_name):

    print(str)
    if log_file_name:
        with open(log_file_name + '.out', 'a') as f:
            print(str, file=f)


def gen_run_name(name_prefix):
    time_str = datetime.now().strftime(' %Y-%m-%d %H:%M:%S')
    return name_prefix + time_str

# def save_code(setting_name, run_name):
#     dir_name = setting_name + '_' + run_name
#     # Create backup of code
#     source_dir = os.getcwd()
#     dest_dir = source_dir + '/Code_Archive/' + dir_name
#     if not os.path.exists(dest_dir):
#         os.makedirs(dest_dir)
#     for filename in glob.glob(os.path.join(source_dir, '*.*')):
#         shutil.copy(filename, dest_dir)


def write_final_result(test_acc,run_time, log_file_name, result_name='', verbose=1):
    if verbose == 1:
        write_result('Run finished at: ' + datetime.now().strftime(' %Y-%m-%d %H:%M:%S'), log_file_name)
    write_result(result_name + ' Average Test Error: {:.3}%\t Runtime: {} [sec]'
                     .format(100 * (1 - test_acc), run_time), log_file_name)


