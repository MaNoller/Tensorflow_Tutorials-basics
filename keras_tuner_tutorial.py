# -*- coding: utf-8 -*-
"""keras_tuner_tutorial.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1vQk32FhDelAK6OnWNOrb4quGffMF7ZVS

Keras Tuner helps to optimize hyperparameters. The process of selecting there is called hyperparameter tuning.

The Hyperparameters are variables, that govern the training process and the topology of a model. They remain constant during training.
The two types:

1) Model hyperparameters: Influence model selection (eg number and width of hidden layers)

2) Algorithm hyperparameters: influence speed and quality of learning algo
"""

import tensorflow as tf
from tensorflow import keras

pip install -q -U keras-tuner

import keras_tuner as kt

"""# Dataset"""

(img_train, label_train), (img_test, label_test) = keras.datasets.fashion_mnist.load_data()

# Normalize pixel values between 0 and 1
img_train = img_train.astype('float32') / 255.0
img_test = img_test.astype('float32') / 255.0

"""# The Model

With models for hyperparameter tuning, the hyperparameter search space has also to be defined -> Hypermodel

There are two approaches:

1) Using model builder fcn

2) Subclassing the HyperModel  class

here a modelbuilderfcn will be used. the model builder fcn returns a compiled model and uses user defined hyperparams
"""

def model_builder(hp):
  model = keras.Sequential()
  model.add(keras.layers.Flatten(input_shape=(28, 28)))

  # Tune the number of units in the first Dense layer
  # Choose an optimal value between 32-512
  hp_units = hp.Int('units', min_value=32, max_value=512, step=32)
  model.add(keras.layers.Dense(units=hp_units, activation='relu'))
  model.add(keras.layers.Dense(10))

  # Tune the learning rate for the optimizer
  # Choose an optimal value from 0.01, 0.001, or 0.0001
  hp_learning_rate = hp.Choice('learning_rate', values=[1e-2, 1e-3, 1e-4])

  model.compile(optimizer=keras.optimizers.Adam(learning_rate=hp_learning_rate),
                loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                metrics=['accuracy'])

  return model

"""# Instantiate tuner and perform hypertuning

The Keras Tuner has four tuners available - RandomSearch, Hyperband, BayesianOptimization, and Sklearn
To instantiate the Hyperband tuner, you must specify the hypermodel, the objective to optimize and the maximum number of epochs to train (max_epochs).
"""

tuner = kt.Hyperband(model_builder,
                     objective='val_accuracy',
                     max_epochs=10,
                     factor=3,
                     directory='my_dir',
                     project_name='intro_to_kt')

"""Hyperband uses adaptive resource allocation and early-stopping for quick convergence towards high-performance model.

A large umber of models are trained for a few epochs and only the best half will be carried to the next round

callback to stop early after a certain val_loss is reached
"""

stop_early = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=5)

tuner.search(img_train, label_train, epochs=50, validation_split=0.2, callbacks=[stop_early])

# Get the optimal hyperparameters
best_hps=tuner.get_best_hyperparameters(num_trials=1)[0]

print(f"""
The hyperparameter search is complete. The optimal number of units in the first densely-connected
layer is {best_hps.get('units')} and the optimal learning rate for the optimizer
is {best_hps.get('learning_rate')}.
""")

"""# Train the model

find opt. num of epochs
"""

# Build the model with the optimal hyperparameters and train it on the data for 50 epochs
model = tuner.hypermodel.build(best_hps)
history = model.fit(img_train, label_train, epochs=50, validation_split=0.2)

val_acc_per_epoch = history.history['val_accuracy']
best_epoch = val_acc_per_epoch.index(max(val_acc_per_epoch)) + 1
print('Best epoch: %d' % (best_epoch,))

"""re-instantiate ad retrain with opt. epochs"""

hypermodel = tuner.hypermodel.build(best_hps)

# Retrain the model
hypermodel.fit(img_train, label_train, epochs=best_epoch, validation_split=0.2)

eval_result = hypermodel.evaluate(img_test, label_test)
print("[test loss, test accuracy]:", eval_result)