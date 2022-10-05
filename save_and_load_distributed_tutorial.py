# -*- coding: utf-8 -*-
"""save_and_load_distributed_tutorial.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/10GnMJBa9f430-d7XAu1jrpJ9M1uOrTGS

# General
save and load models with tf.distribute.Strategy during or after training will be mentioned.
"""

import tensorflow_datasets as tfds

import tensorflow as tf

"""Load data and create model"""

mirrored_strategy = tf.distribute.MirroredStrategy()

def get_data():
  datasets = tfds.load(name='mnist', as_supervised=True)
  mnist_train, mnist_test = datasets['train'], datasets['test']

  BUFFER_SIZE = 10000

  BATCH_SIZE_PER_REPLICA = 64
  BATCH_SIZE = BATCH_SIZE_PER_REPLICA * mirrored_strategy.num_replicas_in_sync

  def scale(image, label):
    image = tf.cast(image, tf.float32)
    image /= 255

    return image, label

  train_dataset = mnist_train.map(scale).cache().shuffle(BUFFER_SIZE).batch(BATCH_SIZE)
  eval_dataset = mnist_test.map(scale).batch(BATCH_SIZE)

  return train_dataset, eval_dataset

def get_model():
  with mirrored_strategy.scope():
    model = tf.keras.Sequential([
        tf.keras.layers.Conv2D(32, 3, activation='relu', input_shape=(28, 28, 1)),
        tf.keras.layers.MaxPooling2D(),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(10)
    ])

    model.compile(loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                  optimizer=tf.keras.optimizers.Adam(),
                  metrics=[tf.metrics.SparseCategoricalAccuracy()])
    return model

"""train model"""

model = get_model()
train_dataset, eval_dataset = get_data()
model.fit(train_dataset, epochs=2)

"""# Save and load model
There are basically two kinds of apis:
*  High-level (Keras):Model.save and tf.keras.models.load_model
*  Low-level: tf.saved_model.save and tf.saved_model.load

##Keras
save:
"""

keras_model_path = '/tmp/keras_save'
model.save(keras_model_path)

"""Restore model without distribute.Strategy"""

restored_keras_model = tf.keras.models.load_model(keras_model_path)
restored_keras_model.fit(train_dataset, epochs=2)

"""After restoring, training can continue, even without recompiling.

Now: restore model and train it using tf.distribute.Strategy:
"""

another_strategy = tf.distribute.OneDeviceStrategy('/cpu:0')
with another_strategy.scope():
  restored_keras_model_ds = tf.keras.models.load_model(keras_model_path)
  restored_keras_model_ds.fit(train_dataset, epochs=2)

"""##tf.saved_model
saving:
"""

model = get_model()  # get a fresh model
saved_model_path = '/tmp/tf_save'
tf.saved_model.save(model, saved_model_path)

"""Loading with:tf.saved_model.load. It does not return a model but rather an object containing fcns that can be used to do inference:"""

DEFAULT_FUNCTION_KEY = 'serving_default'
loaded = tf.saved_model.load(saved_model_path)
inference_func = loaded.signatures[DEFAULT_FUNCTION_KEY]

"""Loaded obj may contain several fcns, each assiciated with a key. To do inference:"""

predict_dataset = eval_dataset.map(lambda image, label: image)
for batch in predict_dataset.take(1):
  print(inference_func(batch))

"""also possible with distribution:"""

another_strategy = tf.distribute.MirroredStrategy()
with another_strategy.scope():
  loaded = tf.saved_model.load(saved_model_path)
  inference_func = loaded.signatures[DEFAULT_FUNCTION_KEY]

  dist_predict_dataset = another_strategy.experimental_distribute_dataset(
      predict_dataset)

  # Calling the function in a distributed manner
  for batch in dist_predict_dataset:
    result = another_strategy.run(inference_func, args=(batch,))
    print(result)
    break

"""calling the fcn is just a forward pass on the saved model. to continue training, wrap the loaded object in a keras layer:"""

import tensorflow_hub as hub

def build_model(loaded):
  x = tf.keras.layers.Input(shape=(28, 28, 1), name='input_x')
  # Wrap what's loaded to a KerasLayer
  keras_layer = hub.KerasLayer(loaded, trainable=True)(x)
  model = tf.keras.Model(x, keras_layer)
  return model

another_strategy = tf.distribute.MirroredStrategy()
with another_strategy.scope():
  loaded = tf.saved_model.load(saved_model_path)
  model = build_model(loaded)

  model.compile(loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                optimizer=tf.keras.optimizers.Adam(),
                metrics=[tf.metrics.SparseCategoricalAccuracy()])
  model.fit(train_dataset, epochs=2)

"""#Which to use?
for saving, if working with keras model, use model.save, should be enough. if no keras model, then the lower-level one.

for loading, it depends what shall be achieved. is no model is available, use tf.saved_model.load, else use tf.keras.models.load_model
"""