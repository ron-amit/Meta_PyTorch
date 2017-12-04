#
# the code is inspired by: https://github.com/katerakelly/pytorch-maml

import numpy as np
import random
import math
from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from Utils import data_gen

# -------------------------------------------------------------------------------------------
# Main function
# -------------------------------------------------------------------------------------------
def get_model(prm):
    model_name = prm.model_name
    # Get task info:
    info = data_gen.get_info(prm)
    input_shape = info['input_shape']
    color_channels = input_shape[0]
    n_classes = info['n_classes']
    input_size = input_shape[0] * input_shape[1] * input_shape[2]

    if model_name == 'FcNet3':
        model = FcNet3(input_size=input_size, n_classes=n_classes)
    elif model_name == 'ConvNet3':
        model = ConvNet3(input_shape=input_shape, n_classes=n_classes)
    else:
        raise ValueError('Invalid model_name')
    return model

# -------------------------------------------------------------------------------------------
# Auxiliary functions
# -------------------------------------------------------------------------------------------

# generate dummy input sample and forward to get shape after conv layers
def get_size_of_conv_output(input_shape, conv_func):
    batch_size = 1
    input = Variable(torch.rand(batch_size, *input_shape))
    output_feat = conv_func(input)
    conv_out_size = output_feat.data.view(batch_size, -1).size(1)
    return conv_out_size


# -------------------------------------------------------------------------------------------
#  Base class for models
# -------------------------------------------------------------------------------------------
class base_model(nn.Module):
    def __init__(self):
        super(base_model, self).__init__()
        self.model_type = 'Standard'

    def net_forward(self, x, weights=None):
        return self.forward(x, weights) # forward is defined in derived classes

    def _init_weights(self):
        ''' Set weights to Gaussian, biases to zero '''

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
                if m.bias is not None:
                    m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.Linear):
                # Similar to PyTorch' default initializer
                n = m.weight.size(1)
                stdv = 1. / math.sqrt(n)
                m.weight.data.uniform_(-stdv, stdv)
                # m.weight.data.normal_(0, 0.01)
                if m.bias is not None:
                    m.bias.data.uniform_(1-stdv, 1+stdv)
                    # m.bias.data = torch.ones(m.bias.data.size())

    def copy_weights(self, net):
        ''' Set this module's weights to be the same as those of 'net' '''
        # TODO: breaks if nets are not identical
        # TODO: won't copy buffers, e.g. for batch norm
        for m_from, m_to in zip(net.modules(), self.modules()):
            if isinstance(m_to, nn.Linear) or isinstance(m_to, nn.Conv2d) or isinstance(m_to, nn.BatchNorm2d):
                m_to.weight.data = m_from.weight.data.clone()
                if m_to.bias is not None:
                    m_to.bias.data = m_from.bias.data.clone()

# -------------------------------------------------------------------------------------------
#  3-hidden-layer Fully-Connected Net
# -------------------------------------------------------------------------------------------
class FcNet3(base_model):
    def __init__(self, input_size, n_classes):
        super(FcNet3, self).__init__()
        self.model_name = 'FcNet3'
        self.input_size = input_size
        n_hidden1 = 400
        n_hidden2 = 400
        n_hidden3 = 400
        self.net = nn.Sequential(OrderedDict([
                ('fc1',  nn.Linear(input_size, n_hidden1)),
                ('a1',  nn.ELU(inplace=True)),
                ('fc2',  nn.Linear(n_hidden1, n_hidden2)),
                ('a2', nn.ELU(inplace=True)),
                ('fc3',  nn.Linear(n_hidden2, n_hidden3)),
                ('a3', nn.ELU(inplace=True)),
                ('fc_out', nn.Linear(n_hidden3, n_classes)),
                ]))
        # Initialize weights
        self._init_weights()
        self.cuda()  # always use GPU

    def forward(self, x, weights=None):
        ''' Define what happens to data in the net '''
        x = x.view(-1, self.input_size)  # flatten image
        if weights is None:
            x = self.net(x)
        else:
            x = F.linear(x, weights['net.fc1.weight'], weights['net.fc1.bias'])
            x = F.elu(x)
            x = F.linear(x, weights['net.fc2.weight'], weights['net.fc2.bias'])
            x = F.elu(x)
            x = F.linear(x, weights['net.fc3.weight'], weights['net.fc3.bias'])
            x = F.elu(x)
            x = F.linear(x, weights['net.fc_out.weight'], weights['net.fc_out.bias'])
        return x


# -------------------------------------------------------------------------------------------
#  3-hidden-layer ConvNet
# -------------------------------------------------------------------------------- -----------
class ConvNet3(base_model):
    def __init__(self, input_shape, n_classes):
        super(ConvNet3, self).__init__()
        self.model_name = 'ConvNet3'
        n_in_channels = input_shape[0]
        n_filt1 = 10
        n_filt2 = 20
        n_hidden_fc1 = 50
        self.conv_layers = nn.Sequential(OrderedDict([
                ('conv1',  nn.Conv2d(n_in_channels, n_filt1, kernel_size=5)),
                ('pool1', nn.MaxPool2d(kernel_size=2, stride=2)),
                ('a1',  nn.ELU(inplace=True)),
                ('conv2', nn.Conv2d(n_filt1, n_filt2, kernel_size=5)),
                ('pool2', nn.MaxPool2d(kernel_size=2, stride=2)),
                ('a2', nn.ELU(inplace=True)),
                 ]))
        conv_out_size = get_size_of_conv_output(input_shape, self._forward_conv_layers)
        self.add_module('fc1', nn.Linear(conv_out_size, n_hidden_fc1))
        self.add_module('a3', nn.ELU(inplace=True)),
        self.add_module('fc_out', nn.Linear(n_hidden_fc1, n_classes))

        # Initialize weights
        self._init_weights()
        self.cuda()  # always use GPU

    def _forward_conv_layers(self, x, weights=None):
        if weights is None:
            x = self.conv_layers(x)
        else:
            x = F.conv2d(x, weights['conv_layers.conv1.weight'], weights['conv_layers.conv1.bias'])
            x = F.max_pool2d(x, kernel_size=2, stride=2)
            x = F.elu(x)
            x = F.conv2d(x, weights['conv_layers.conv2.weight'], weights['conv_layers.conv2.bias'])
            x = F.max_pool2d(x, kernel_size=2, stride=2)
            x = F.elu(x)
        return x

    def forward(self, x, weights=None):
        x = self._forward_conv_layers(x, weights)
        x = x.view(x.size(0), -1)
        if weights is None:
            x = self.fc1(x)
            x = F.elu(x)
            x = self.fc_out(x)
        else:
            x = F.linear(x, weights['fc1.weight'], weights['fc1.bias'])
            x = F.elu(x)
            x = F.linear(x, weights['fc_out.weight'], weights['fc_out.bias'])
        return x
