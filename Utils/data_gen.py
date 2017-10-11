
from __future__ import absolute_import, division, print_function

import torch
from torchvision import datasets, transforms
import torch.utils.data as data_utils
from torch.autograd import Variable
import multiprocessing
import numpy as np
# -------------------------------------------------------------------------------------------
#  Create data loader
# -------------------------------------------------------------------------------------------


def get_data_loader(prm, limit_train_samples = None):

    # Set data transformation function:
    input_trans = None
    target_trans = None

    if prm.data_transform == 'Permute_Pixels':
        # Create a fixed random pixels permutation, applied to all images
        input_trans = create_pixel_permute_trans(prm)

    elif prm.data_transform == 'Permute_Labels':
        # Create a fixed random label permutation, applied to all images
        target_trans = create_label_permute_trans(prm)

    # Get dataset:
    if prm.data_source == 'MNIST':
        train_dataset, test_dataset = load_MNIST(input_trans, target_trans, prm)

    elif prm.data_source == 'Sinusoid':

        task_param = create_sinusoid_task()
        train_dataset = create_sinusoid_data(task_param, n_samples=10)
        test_dataset = create_sinusoid_data(task_param, n_samples=100)

    else:
        raise ValueError('Invalid data_source')

    # Limit the training samples:
    if limit_train_samples:
        n_samples_orig = train_dataset.train_data.size()[0]
        sampled_inds = torch.randperm(n_samples_orig)[:limit_train_samples]
        train_dataset.train_data = train_dataset.train_data[sampled_inds]
        train_dataset.train_labels = train_dataset.train_labels[sampled_inds]

    # Create data loaders:
    kwargs = {'num_workers': multiprocessing.cpu_count(), 'pin_memory': True} if prm.cuda else {}
    # kwargs = {'num_workers': 0, 'pin_memory': True} if prm.cuda else {}

    train_loader = data_utils.DataLoader(train_dataset, batch_size=prm.batch_size, shuffle=True, **kwargs)
    test_loader = data_utils.DataLoader(test_dataset, batch_size=prm.test_batch_size, shuffle=True, **kwargs)

    n_train_samples = len(train_loader.dataset)
    n_test_samples = len(test_loader.dataset)

    data_loader = {'train': train_loader, 'test': test_loader,
                   'n_train_samples': n_train_samples, 'n_test_samples': n_test_samples}

    return data_loader


# -------------------------------------------------------------------------------------------
#  Data sets
# -------------------------------------------------------------------------------------------

def load_MNIST(input_trans, target_trans, prm):
    MNIST_MEAN = (0.1307,)  # (0.5,)
    MNIST_STD = (0.3081,)  # (0.5,)
    # Note: keep values in [0,1] to avoid too large input norm (which cause high variance)

    # Data transformations list:

    input_trans_list = [transforms.ToTensor()]
    # input_trans_list.append(transforms.Normalize(MNIST_MEAN, MNIST_STD))
    if input_trans:
        # Note: this operates before transform to tensor
        input_trans_list.append(transforms.Lambda(input_trans))

    # Train set:
    train_dataset = datasets.MNIST(prm.data_path, train=True, download=True,
                                   transform=transforms.Compose(input_trans_list), target_transform=target_trans)

    # Test set:
    test_dataset = datasets.MNIST(prm.data_path, train=False,
                                  transform=transforms.Compose(input_trans_list), target_transform=target_trans)


    return train_dataset, test_dataset

# -------------------------------------------------------------------------------------------
#  Data sets parameters
# -------------------------------------------------------------------------------------------


def get_info(prm):
    if prm.data_source == 'MNIST':
        info = {'im_size': 28, 'color_channels': 1, 'n_classes': 10, 'input_size': 1 * 28 * 28}
    else:
        raise ValueError('Invalid data_source')

    return info


# -------------------------------------------------------------------------------------------
#  Transform batch to variables
# -------------------------------------------------------------------------------------------
def get_batch_vars(batch_data, args, is_test=False):
    inputs, targets = batch_data
    if args.cuda:
        inputs, targets = inputs.cuda(), targets.cuda(async=True)
    inputs, targets = Variable(inputs, volatile=is_test), Variable(targets, volatile=is_test)
    return inputs, targets

# -----------------------------------------------------------------------------------------------------------#
# Data manipulation
# -----------------------------------------------------------------------------------------------------------#

def create_pixel_permute_trans(prm):
    info = get_info(prm)
    inds_permute = torch.randperm(info['input_size'])
    transform_func = lambda x: permute_pixels(x, inds_permute)
    return transform_func

def permute_pixels(x, inds_permute):
    ''' Permute pixels of a tensor image'''
    im_H = x.shape[1]
    im_W = x.shape[2]
    input_size = im_H * im_W
    x = x.view(input_size)  # flatten image
    x = x[inds_permute]
    x = x.view(1, im_H, im_W)
    return x

def create_label_permute_trans(prm):
    info = get_info(prm)
    inds_permute = torch.randperm(info['n_classes'])
    transform_func = lambda target: inds_permute[target]
    return transform_func

# -----------------------------------------------------------------------------------------------------------#
# Sinusoid Regression
# -----------------------------------------------------------------------------------------------------------#
def create_sinusoid_task():
    task_param = {'phase':np.random.uniform(0, np.pi),
                  'amplitude':np.random.uniform(0.1, 5.0),
                  'freq': 5.0,
                  'input_range': [-0.5, 0.5]}
    return task_param

def create_sinusoid_data(task_param, n_samples):
    amplitude = task_param['amplitude']
    phase = task_param['phase']
    freq = task_param['freq']
    input_range = task_param['input_range']
    y = np.ndarray(shape=(n_samples, 1), dtype=np.float32)
    x = np.random.uniform(input_range[0], input_range[1], n_samples)
    y = amplitude * np.sin(phase + 2 * np.pi * freq * x)
    return x, y