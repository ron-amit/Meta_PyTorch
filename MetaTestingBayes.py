
from __future__ import absolute_import, division, print_function

import timeit
import data_gen

import numpy as np
import torch
import random
import common as cmn
from common import count_correct, get_param_from_model, grad_step
from models_Bayes import get_bayes_model
from meta_utils import get_posterior_complexity_term, get_eps_std


def run_learning(task_data, prior_model, prm, model_type, optim_func, optim_args, loss_criterion, lr_schedule, init_from_prior):

    # -------------------------------------------------------------------------------------------
    #  Setting-up
    # -------------------------------------------------------------------------------------------


    # Create posterior model for the new task:
    post_model = get_bayes_model(model_type, prm)

    if init_from_prior:
        post_model.load_state_dict(prior_model.state_dict())

    # The data-sets of the new task:
    train_loader = task_data['train']
    test_loader = task_data['test']
    n_train_samples = len(train_loader.dataset)

    #  Get optimizer:
    optimizer = optim_func(post_model.parameters(), **optim_args)


    # -------------------------------------------------------------------------------------------
    #  Training epoch  function
    # -------------------------------------------------------------------------------------------

    def run_train_epoch(i_epoch):
        log_interval = 500
        n_batches = len(train_loader)

        post_model.train()
        for batch_idx, batch_data in enumerate(train_loader):

            eps_std = get_eps_std(i_epoch, batch_idx, n_batches, prm)

            # get batch:
            inputs, targets = data_gen.get_batch_vars(batch_data, prm)

            # Calculate empirical loss:
            outputs = post_model(inputs, eps_std)
            empirical_loss = loss_criterion(outputs, targets)

            # Total objective:
            intra_task_comp = get_posterior_complexity_term(
                prm.complexity_type, prior_model, post_model, n_train_samples)
            total_objective = empirical_loss + intra_task_comp

            # Take gradient step:
            grad_step(total_objective, optimizer, lr_schedule, prm.lr, i_epoch)

            # Print status:
            if batch_idx % log_interval == 0:
                batch_acc = count_correct(outputs, targets) / prm.batch_size
                print(cmn.status_string(i_epoch, batch_idx, n_batches, prm, batch_acc, total_objective.data[0]) +
                      'Eps-STD: {:.4}\t Empiric Loss: {:.4}\t Intra-Comp. {:.4}'.
                      format(eps_std, empirical_loss.data[0], intra_task_comp.data[0]))


    # -------------------------------------------------------------------------------------------
    #  Test evaluation function
    # --------------------------------------------------------------------------------------------
    def run_test():
        post_model.eval()
        test_loss = 0
        n_correct = 0
        for batch_data in test_loader:
            inputs, targets = data_gen.get_batch_vars(batch_data, prm)
            eps_std = 0.0  # test with max-posterior
            outputs = post_model(inputs, eps_std)
            test_loss += loss_criterion(outputs, targets)  # sum the mean loss in batch
            n_correct += count_correct(outputs, targets)

        n_test_samples = len(test_loader.dataset)
        n_test_batches = len(test_loader)
        test_loss = test_loss.data[0] / n_test_batches
        test_acc = n_correct / n_test_samples
        print('\nTest set: Average loss: {:.4}, Accuracy: {:.3} ( {}/{})\n'.format(
            test_loss, test_acc, n_correct, n_test_samples))
        return test_acc

    # -----------------------------------------------------------------------------------------------------------#
    # Update Log file
    # -----------------------------------------------------------------------------------------------------------#
    run_name = cmn.gen_run_name('Meta-Testing')
    cmn.write_result('-'*10+run_name+'-'*10, prm.log_file)
    cmn.write_result(str(prm), prm.log_file)
    cmn.write_result(cmn.get_model_string(post_model), prm.log_file)
    cmn.write_result(str(optim_func) + str(optim_args) + str(lr_schedule), prm.log_file)

    # -------------------------------------------------------------------------------------------
    #  Run epochs
    # -------------------------------------------------------------------------------------------
    start_time = timeit.default_timer()

    # Training loop:
    for i_epoch in range(prm.num_epochs):
        run_train_epoch(i_epoch)

    # Test:
    test_acc = run_test()

    stop_time = timeit.default_timer()
    cmn.write_final_result(test_acc, stop_time - start_time, prm.log_file)
    cmn.save_code('CodeBackup', run_name)

    return (1 - test_acc)