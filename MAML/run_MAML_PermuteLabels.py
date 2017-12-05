from subprocess import call

call(['python', 'main_MAML.py',
      '--data-source', 'MNIST',
      '--n_train_tasks', '2',
      '--data-transform', 'Permute_Labels',
      '--model-name', 'ConvNet3',
      # MAML hyper-parameters:
      '--alpha', '0.4',
      '--n_meta_train_grad_steps', '1',
      '--n_meta_train_iterations', '60000',
      '--meta_batch_size', '32',
      '--n_meta_test_grad_steps', '100',
      ])