import tensorflow as tf
import numpy as np

from keras import backend, applications, optimizers, losses
from keras.models import Sequential
from keras.layers import Input, Dropout, Flatten, Dense
from keras.preprocessing.image import ImageDataGenerator

from sklearn.metrics import confusion_matrix, mean_squared_error

import os.path
import argparse

tf.logging.set_verbosity(tf.logging.ERROR)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
print("TensorFlow version: " + tf.__version__)

parser = argparse.ArgumentParser(description='Build a top layer for the similarity training and train it.')
parser.add_argument('-w', '--overwrite', dest="w",
                    action='store_true', help="Overwrite initial feature embeddings")
parser.add_argument('-t', '--train-dir', dest='train_dir',
                    default="/opt/datasets/data/simulated_flight_1/train/",
                    help='Path to dataset training directory')
parser.add_argument('-v', '--valid-dir', dest='valid_dir',
                    default="/opt/datasets/data/simulated_flight_1/valid/",
                    help='Path to dataset validation directory')
parser.add_argument('-e', '--epochs', dest='epochs', type=int,
                    default=5, help='Number of epochs to train the model')
parser.add_argument('-b', '--batch-size', dest='batch_size', type=int,
                    default=3, help='Batch size')

args = parser.parse_args()

#img_width, img_height = 224, 224
top_model_weights_path = 'top_model_weights.h5'
train_features_file = 'top_model_features_train.npy'
valid_features_file = 'top_model_features_valid.npy'

def save_features():

  datagen = ImageDataGenerator()
  
  vgg16_model = applications.VGG16(include_top = False, weights = 'imagenet')

  generator = datagen.flow_from_directory(directory = args.train_dir, target_size = (224, 224), batch_size = args.batch_size, class_mode = None, shuffle = False)
  #, save_to_dir = 'train_augmented')
  
  top_model_features_train = vgg16_model.predict_generator(generator, nb_train_samples)
  np.save(open(train_features_file, 'wb'), top_model_features_train)

  generator = datagen.flow_from_directory(directory = args.valid_dir, target_size = (224, 224), batch_size = args.batch_size, class_mode = None, shuffle = False)
  #, save_to_dir = 'test_augmented')

  top_model_features_valid = vgg16_model.predict_generator(generator, nb_valid_samples)
  np.save(open(valid_features_file, 'wb'), top_model_features_valid)

def triplet_loss(y_true, y_pred):
  N = 3
  beta = N
  epsilon = 1e-8

  anchor = y_pred[0::3]
  positive = y_pred[1::3]
  negative = y_pred[2::3]

  positive_distance = tf.reduce_sum(tf.square(tf.subtract(anchor, positive)), 1)
  negative_distance = tf.reduce_sum(tf.square(tf.subtract(anchor, negative)), 1)

  # -ln(-x/N+1)
  #positive_distance = -tf.log(-tf.divide((positive_distance), beta) + 1 + epsilon)
  #negative_distance = -tf.log(-tf.divide((N - negative_distance), beta) + 1 + epsilon)
    
  positive_distance = (-tf.divide((positive_distance), beta) + 1 + epsilon)
  negative_distance = (-tf.divide((N - negative_distance), beta) + 1 + epsilon)

  loss = negative_distance + positive_distance
  return loss
   
def metric_positive_distance(y_true, y_pred):
  N = 3
  beta = N
  epsilon = 1e-8
  anchor = y_pred[0::3]
  positive = y_pred[1::3]
  positive_distance = tf.reduce_sum(tf.square(tf.subtract(anchor, positive)), 1)
  #positive_distance = -tf.log(-tf.divide((positive_distance), beta) + 1 + epsilon)
  positive_distance = (-tf.divide((positive_distance), beta) + 1 + epsilon)
  return backend.mean(positive_distance)

def metric_negative_distance(y_true, y_pred):
  N = 3
  beta = N
  epsilon = 1e-8
  anchor = y_pred[0::3]
  negative = y_pred[2::3]
  negative_distance = tf.reduce_sum(tf.square(tf.subtract(anchor, negative)), 1)
  #negative_distance = -tf.log(-tf.divide((N - negative_distance), beta) + 1 + epsilon)
  negative_distance = (-tf.divide((N - negative_distance), beta) + 1 + epsilon)
  return backend.mean(negative_distance)

def train_top_model():
  train_data = np.load(open('top_model_features_train.npy', 'rb'))
  valid_data = np.load(open('top_model_features_valid.npy', 'rb'))

  top_model = Sequential()
  top_model.add(Flatten(input_shape = train_data.shape[1:]))
  top_model.add(Dense(64, activation = 'relu'))
  top_model.add(Dropout(0.5))
  top_model.add(Dense(1, activation = 'sigmoid'))

  top_model.compile(optimizer = optimizers.Adam(), loss = triplet_loss, metrics = [metric_positive_distance, metric_negative_distance])

  top_model.summary()
  y_dummie = np.array([1, 1, 0] * (int(nb_train_samples)))
  top_model.fit(train_data, y_dummie, epochs = args.epochs, batch_size = args.batch_size, shuffle = False)
  top_model.save_weights(top_model_weights_path)
    
if __name__ == '__main__':
  nb_train_samples = len(os.listdir(args.train_dir + "/0")) / 3
  nb_valid_samples = len(os.listdir(args.valid_dir + "/0")) / 3
  if nb_train_samples > 0 and nb_valid_samples > 0:
    if args.w or not (os.path.isfile(train_features_file) and os.path.isfile(valid_features_file)):
      print("Writing features")
      save_features()
    train_top_model()
  else:
    print("Dataset images were not found")
