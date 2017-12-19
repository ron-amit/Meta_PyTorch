
from __future__ import absolute_import, division, print_function

import numpy as np
import torch
from torch.autograd import Variable
import math
from Utils import common as cmn, data_gen
from Utils.common import count_correct
import torch.nn.functional as F
from Models.stochastic_layers import StochasticLayer



def run_test_Bayes(model, test_loader, loss_criterion, prm, verbose=1):

    if prm.test_type == 'MaxPosterior':
        info =  run_test_max_posterior(model, test_loader, loss_criterion, prm)
    elif prm.test_type == 'MajorityVote':
        info = run_test_majority_vote(model, test_loader, loss_criterion, prm, n_votes=5)
    elif prm.test_type == 'AvgVote':
        info = run_test_avg_vote(model, test_loader, loss_criterion, prm, n_votes=5)
    else:
        raise ValueError('Invalid test_type')
    if verbose:
        print('Test Accuracy: {:.3} ({}/{}), Test loss: {:.4}'.format(info['test_acc'], info['n_correct'], info['n_test_samples'], info['test_loss']))
    return info['test_acc'], info['test_loss']


def run_test_max_posterior(model, test_loader, loss_criterion, prm):

    n_test_samples = len(test_loader.dataset)
    n_test_batches = len(test_loader)

    model.eval()
    test_loss = 0
    n_correct = 0
    for batch_data in test_loader:
        inputs, targets = data_gen.get_batch_vars(batch_data, prm, is_test=True)
        old_eps_std = model.set_eps_std(0.0)   # test with max-posterior
        outputs = model(inputs)
        model.set_eps_std(old_eps_std)  # return model to normal behaviour
        test_loss += loss_criterion(outputs, targets)  # sum the mean loss in batch
        n_correct += count_correct(outputs, targets)

    test_loss /= n_test_samples
    test_acc = n_correct / n_test_samples
    info = {'test_acc':test_acc, 'n_correct':n_correct, 'test_type':'max_posterior',
            'n_test_samples':n_test_samples, 'test_loss':test_loss.data[0]}
    return info


def run_test_majority_vote(model, test_loader, loss_criterion, prm, n_votes=9):
#
    n_test_samples = len(test_loader.dataset)
    n_test_batches = len(test_loader)
    model.eval()
    test_loss = 0
    n_correct = 0
    for batch_data in test_loader:
        inputs, targets = data_gen.get_batch_vars(batch_data, prm, is_test=True)

        batch_size = min(prm.test_batch_size, n_test_samples)
        info = data_gen.get_info(prm)
        n_labels = info['n_classes']
        votes = cmn.zeros_gpu((batch_size, n_labels))
        for i_vote in range(n_votes):

            outputs = model(inputs)
            test_loss += loss_criterion(outputs, targets)
            pred = outputs.data.max(1, keepdim=True)[1]  # get the index of the max output
            for i_sample in range(batch_size):
                pred_val = pred[i_sample].cpu().numpy()[0]
                votes[i_sample, pred_val] += 1

        majority_pred = votes.max(1, keepdim=True)[1]
        n_correct += majority_pred.eq(targets.data.view_as(majority_pred)).cpu().sum()
    test_loss /= n_test_samples
    test_acc = n_correct / n_test_samples
    info = {'test_acc': test_acc, 'n_correct': n_correct, 'test_type': 'majority_vote',
            'n_test_samples': n_test_samples, 'test_loss': test_loss.data[0]}
    return info


def run_test_avg_vote(model, test_loader, loss_criterion, prm, n_votes=5):

    n_test_samples = len(test_loader.dataset)
    n_test_batches = len(test_loader)
    model.eval()
    test_loss = 0
    n_correct = 0
    for batch_data in test_loader:
        inputs, targets = data_gen.get_batch_vars(batch_data, prm, is_test=True)

        batch_size = min(prm.test_batch_size, n_test_samples)
        info = data_gen.get_info(prm)
        n_labels = info['n_classes']
        votes = cmn.zeros_gpu((batch_size, n_labels))
        for i_vote in range(n_votes):

            outputs = model(inputs)
            test_loss += loss_criterion(outputs, targets)
            votes += outputs.data

        majority_pred = votes.max(1, keepdim=True)[1]
        n_correct += majority_pred.eq(targets.data.view_as(majority_pred)).cpu().sum()

    test_loss /= n_test_samples
    test_acc = n_correct / n_test_samples
    info = {'test_acc': test_acc, 'n_correct': n_correct, 'test_type': 'AvgVote',
            'n_test_samples': n_test_samples, 'test_loss': test_loss.data[0]}
    return info



def get_meta_complexity_term(hyper_kl, prm, n_train_tasks):
    if n_train_tasks == 0:
        meta_complex_term = 0  # infinite tasks case
    else:
        if prm.complexity_type == 'NewBoundMcAllaster' or  prm.complexity_type == 'NewBoundSeeger':
            delta =  prm.delta
            meta_complex_term = torch.sqrt(hyper_kl / (2*n_train_tasks) + math.log(4*math.sqrt(n_train_tasks) / delta))
        elif prm.complexity_type == 'KLD':
            meta_complex_term = hyper_kl
        else:
            meta_complex_term = hyper_kl / math.sqrt(n_train_tasks)
    return meta_complex_term

#  -------------------------------------------------------------------------------------------
#  Intra-task complexity for posterior distribution
# -------------------------------------------------------------------------------------------

def get_posterior_complexity_term(prm, prior_model, post_model, n_samples, task_empirical_loss, hyper_kl=0, noised_prior=True):

    complexity_type = prm.complexity_type
    delta = prm.delta  #  maximal probability that the bound does not hold
    tot_kld = get_total_kld(prior_model, post_model, prm, noised_prior)  # KLD between posterior and sampled prior

    if complexity_type == 'KLD':
        complex_term = tot_kld

    elif prm.complexity_type == 'NewBoundMcAllaster':
        complex_term = torch.sqrt((1 / (2 * (n_samples-1))) * (hyper_kl + tot_kld + math.log(2 * n_samples / delta)))

    elif prm.complexity_type == 'NewBoundSeeger':
        seeger_eps = (1 / n_samples) * (tot_kld + hyper_kl + math.log(4 * math.sqrt(n_samples) / delta))
        sqrt_arg = 2 * seeger_eps * task_empirical_loss
        sqrt_arg = F.relu(sqrt_arg)  # prevent negative values due to numerical errors
        complex_term = 2 * seeger_eps + torch.sqrt(sqrt_arg)


    elif complexity_type == 'PAC_Bayes_McAllaster':
        complex_term = torch.sqrt((1 / (2 * n_samples)) * (tot_kld + math.log(2*math.sqrt(n_samples) / delta)))

    elif complexity_type == 'PAC_Bayes_Pentina':
        complex_term = math.sqrt(1 / n_samples) * tot_kld

    elif complexity_type == 'PAC_Bayes_Seeger':
        # Seeger complexity is unique since it requires the empirical loss
        # small_num = 1e-9 # to avoid nan due to numerical errors
        # seeger_eps = (1 / n_samples) * (kld + math.log(2 * math.sqrt(n_samples) / delta))
        seeger_eps = (1 / n_samples) * (tot_kld + math.log(2 * math.sqrt(n_samples) / delta))
        sqrt_arg = 2 * seeger_eps * task_empirical_loss
        sqrt_arg = F.relu(sqrt_arg)  # prevent negative values due to numerical errors
        complex_term = 2 * seeger_eps + torch.sqrt(sqrt_arg)



    elif complexity_type == 'Variational_Bayes':
        # Since we approximate the expectation of the likelihood of all samples,
        # we need to multiply by the average_loss by total number of samples
        # Then we normalize the objective by n_samples
        complex_term = (1 / n_samples) * tot_kld

    elif complexity_type == 'NoComplexity':
        complex_term = Variable(cmn.zeros_gpu(1), requires_grad=False)

    elif complexity_type == 'None':
        complex_term = 0
    else:
        raise ValueError('Invalid complexity_type')

    return complex_term


def get_total_kld(prior_model, post_model, prm, noised_prior):

    prior_layers_list = [layer for layer in prior_model.children() if isinstance(layer, StochasticLayer)]
    post_layers_list = [layer for layer in post_model.children() if isinstance(layer, StochasticLayer)]

    total_kld = 0
    for i_layer, prior_layer in enumerate(prior_layers_list):
        post_layer = post_layers_list[i_layer]
        if hasattr(prior_layer, 'w'):
            total_kld += kld_element(post_layer.w, prior_layer.w, prm, noised_prior)
        if hasattr(prior_layer, 'b'):
            total_kld += kld_element(post_layer.b, prior_layer.b, prm, noised_prior)

    return total_kld


def kld_element(post, prior, prm, noised_prior):
    """KL divergence D_{KL}[post(x)||prior(x)] for a fully factorized Gaussian"""

    if noised_prior and prm.kappa_post > 0:
        prior_log_var = add_noise(prior['log_var'], prm.kappa_post)
        prior_mean = add_noise(prior['mean'], prm.kappa_post)
    else:
        prior_log_var = prior['log_var']
        prior_mean = prior['mean']

    post_var = torch.exp(post['log_var'])
    prior_var = torch.exp(prior_log_var)

    numerator = (post['mean'] - prior_mean).pow(2) + post_var
    denominator = prior_var
    kld = 0.5 * torch.sum(prior_log_var - post['log_var'] + numerator / denominator - 1)

    # note: don't add small number to denominator, since we need to have zero KL when post==prior.

    return kld


def add_noise(param, std):
    return param + Variable(param.data.new(param.size()).normal_(0, std), requires_grad=False)


def add_noise_to_model(model, std):

    layers_list = [layer for layer in model.children() if isinstance(layer, StochasticLayer)]

    for i_layer, layer in enumerate(layers_list):
        if hasattr(layer, 'w'):
            add_noise(layer.w['log_var'], std)
            add_noise(layer.w['mean'], std)
        if hasattr(layer, 'b'):
            add_noise(layer.b['log_var'], std)
            add_noise(layer.b['mean'], std)

