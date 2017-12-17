from subprocess import call

call(['python', 'main_Meta_Bayes.py',
      '--data-source', 'Omniglot',  # MNIST Omniglot
      '--limit_train_samples_in_test_tasks', '5',
      '--N_Way', '5',
      '--K_Shot', '5',
      '--n_train_tasks', '0',
      '--data-transform', 'Rotate90',
      '--model-name',   'ConvNet3', # TODO: implement stochastic 'OmConvNet',
      '--n_test_tasks', '100',
      '--n_meta_train_epochs', '300',
      '--n_inner_steps', '50',
      '--meta_batch_size', '1',  # 32
      '--mode', 'MetaTrain',
      ])


