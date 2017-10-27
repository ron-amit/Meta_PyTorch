# Meta_PyTorch



## Prerequisites

- Computer with NVIDIA GPU and Linux or OSX
- Python 3.5+ or 2.7+
- [PyTorch 0.2+ with CUDA](http://pytorch.org)
- NumPy and Matplotlib


## Reproducing experiments in  the paper:

* Stochsastic_Meta_Learning/main_Meta_Bayes.py             - Learns a prior from the obsereved (meta-training) tasks and use it to learn new (meta-test) tasks.
* Toy_Examples\Toy_Main.py -  Toy example of 2D  estimation.
* Single_Task/main_TwoTaskTransfer_PermuteLabels and  Single_Task/main_TwoTaskTransfer_PermutePixels.py -
run alternative tranfer methods.
Stochsastic_Meta_Learning/Analyze_Prior.py - Analysis of the weight uncertainty ine each layer of the learned prior (run after creating a prior with main_Meta_Bayes.py)

## Other experiments:

* Single_Task/main_single_standard.py         - Learn standard neural network in a single task.
* Single_Task/main_single_Bayes.py            - Learn stochastic neural network in a single task.
