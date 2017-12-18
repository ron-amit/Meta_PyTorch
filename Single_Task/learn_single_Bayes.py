

from __future__ import absolute_import, division, print_function

import timeit
from copy import deepcopy
from Models.stochastic_models import get_model
from Utils import common as cmn, data_gen
from Utils.Bayes_utils import run_test_Bayes, get_posterior_complexity_term
from Utils.common import grad_step, correct_rate, get_loss_criterion, get_value


def run_learning(data_loader, prm, prior_model=None, init_from_prior=True, verbose=1):

    # -------------------------------------------------------------------------------------------
    #  Setting-up
    # -------------------------------------------------------------------------------------------

    # Unpack parameters:
    optim_func, optim_args, lr_schedule = \
        prm.optim_func, prm.optim_args, prm.lr_schedule

    # Loss criterion
    loss_criterion = get_loss_criterion(prm.loss_type)

    train_loader = data_loader['train']
    test_loader = data_loader['test']
    n_batches = len(train_loader)
    n_train_samples = data_loader['n_train_samples']

    # get model:
    if prior_model and init_from_prior:
        # init from prior model:
        post_model = deepcopy(prior_model)
    else:
        post_model = get_model(prm)

    # post_model.set_eps_std(0.0) # DEBUG: turn off randomness

    #  Get optimizer:
    optimizer = optim_func(post_model.parameters(), **optim_args)

    # -------------------------------------------------------------------------------------------
    #  Training epoch  function
    # -------------------------------------------------------------------------------------------

    def run_train_epoch(i_epoch):

        # # Adjust randomness (eps_std)
        # if hasattr(prm, 'use_randomness_schedeule') and prm.use_randomness_schedeule:
        #     if i_epoch > prm.randomness_full_epoch:
        #         eps_std = 1.0
        #     elif i_epoch > prm.randomness_init_epoch:
        #         eps_std = (i_epoch - prm.randomness_init_epoch) / (prm.randomness_full_epoch - prm.randomness_init_epoch)
        #     else:
        #         eps_std = 0.0  #  turn off randomness
        #     post_model.set_eps_std(eps_std)

        # post_model.set_eps_std(0.00) # debug

        complexity_term = 0

        post_model.train()

        for batch_idx, batch_data in enumerate(train_loader):

            # Monte-Carlo iterations:
            empirical_loss = 0
            n_MC = prm.n_MC
            for i_MC in range(n_MC):
                # get batch:
                inputs, targets = data_gen.get_batch_vars(batch_data, prm)

                # calculate objective:
                outputs = post_model(inputs)
                empirical_loss_c = loss_criterion(outputs, targets)
                empirical_loss += (1 / n_MC) * empirical_loss_c

            #  complexity/prior term:
            if prior_model:
                complexity_term = get_posterior_complexity_term(
                    prm, prior_model, post_model, n_train_samples, empirical_loss)
            else:
                complexity_term = 0.0

                # Total objective:
            objective = empirical_loss + complexity_term

            # Take gradient step:
            grad_step(objective, optimizer, lr_schedule, prm.lr, i_epoch)

            # Print status:
            log_interval = 500
            if batch_idx % log_interval == 0:
                batch_acc = correct_rate(outputs, targets)
                print(cmn.status_string(i_epoch, prm.num_epochs, batch_idx, n_batches, batch_acc, objective.data[0]) +
                      ' Loss: {:.4}\t Comp.: {:.4}'.format(get_value(empirical_loss), get_value(complexity_term)))
    # -------------------------------------------------------------------------------------------
    #  Main Script
    # -------------------------------------------------------------------------------------------


    #  Update Log file
    run_name = cmn.gen_run_name('Bayes')
    if verbose == 1:
        cmn.write_result('-'*10+run_name+'-'*10, prm.log_file)
        cmn.write_result(str(prm), prm.log_file)
        cmn.write_result(cmn.get_model_string(post_model), prm.log_file)
        cmn.write_result('Total number of steps: {}'.format(n_batches * prm.num_epochs), prm.log_file)

    start_time = timeit.default_timer()

    # Run training epochs:
    for i_epoch in range(prm.num_epochs):
        run_train_epoch(i_epoch)

    # Test:
    test_acc, test_loss = run_test_Bayes(post_model, test_loader, loss_criterion, prm)

    stop_time = timeit.default_timer()
    cmn.write_final_result(test_acc, stop_time - start_time, prm.log_file, result_name=prm.test_type)

    test_err = 1 - test_acc
    return test_err, post_model