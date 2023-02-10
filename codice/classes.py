from utils import read_imgs, callbacks, create_new_dir, save_image, convert_to_grayscale, shuffle_data
from plots import  ROC, get_confusion_matrix, plot, comparison_plot, plot_mean_stdev
from hypermodel import hyp_tuning_model
import os
from keras.preprocessing.image import ImageDataGenerator
import numpy as np
from matplotlib import pyplot as plt
from keras.utils.layer_utils import count_params
from random import shuffle
import tensorflow as tf
import shutil
#import matlab.engine
from sklearn.model_selection import KFold
from sklearn.model_selection import train_test_split
import keras_tuner as kt
from keras.models import load_model
import torch
import torch.nn as nn
import statistics as stats
from sklearn.metrics import auc
from tools_for_Pytorch import weights_init, WeightNormalizer, pytorch_linear_model
from ensemble import train_ensemble
from PIL import Image
import warnings 
warnings.filterwarnings('ignore')

img_width = 60
img_height = 60

wave_settings_default = {
    'wavelet_family': 'sym3',
    'threshold': 1.5
}


class Data:
    def __init__(self, augmented=False, wavelet=False, wave_settings=wave_settings_default):
        """class used to choose and initialize dataset
        ...
        Attributes
        ----------
        augmentes: bools
            whether to perform data augmentation
        wavelet: bool
            whether to use wavelet procedure 
        wave_settings: dict
            settings for wavelet procedure"""
        
        #default path to dataset
        self._PATH = 'total_data'

        # path to dataset
        @property
        def path(self):
            return self._PATH
        
        @path.setter
        def path(self, directory):
            if type(directory) != str:
                raise TypeError(f'Expected str type got {type(directory)}')
            self._PATH = directory
        
        # augmentation procedure
        if augmented:
            self.aug()
        
        #wavelet procedure
        if wavelet:
            #self.wave(wave_settings)
            pass
        
        self.set_data(self._PATH)
        self.X, self.y = shuffle_data(self.X, self.y)
        self.len = len(self.X)

    def __len__(self):
        return self.len

    def __getitem__(self, index):    
        return self.X[index], self.y[index] 
    
    def set_data(self, directory):
        self.X, self.y = read_imgs(directory, [0,1])

    def aug(self):
        IMGS_DIR ='augmented_data'
        for cl in ['0', '1']:
            create_new_dir(os.path.join(f'{IMGS_DIR}', cl))
            dataset_path = os.path.join(f'{self._PATH}', cl)
            names = os.listdir(dataset_path)
            for name in names:
                shutil.copy(os.path.join(f'{self._PATH}', cl, f'{name}'), os.path.join(f'{IMGS_DIR}', cl))

        datagen = ImageDataGenerator(
        rotation_range=50,
        width_shift_range=3,
        height_shift_range=3,
        horizontal_flip=True,
        vertical_flip=True,
        fill_mode='reflect',
        validation_split=0)
        
        for i, one_class in enumerate(os.listdir(self._PATH)):
            dir_path = os.path.join(f'{IMGS_DIR}', one_class)
            gen = datagen.flow_from_directory(
                self._PATH,
                target_size = (img_width, img_height),
                batch_size = 1,
                color_mode = 'grayscale',
                class_mode = None,
                classes = [one_class],
                save_to_dir = dir_path
            )
            #generate & save the images
            for k in range(len(gen)):
                gen.next()

        self._PATH = IMGS_DIR

    
    '''def wave(self, wave_settings):

        """Performs a Wavelet-based filtering procedure on the input images (images from the
        original dataset or augmented images) and then saves the new images in a proper 
        directory"""
        
        #calling MATLAB as a computational engine
        eng = matlab.engine.start_matlab()
        
        #setting the Wavelet family to be used 
        wave = wave_settings['wavelet_family']
        #the decomposition level is already set
        N = 3 
        #setting the threshold for decomposistion coefficients in terms of their stdev
        Q =  wave_settings['threshold'] 
   
        IMGS_DIR = 'wavelet_data'

        for cl in ['0', '1']:
            #creating a new directory for wavelet images
            create_new_dir(os.path.join(f'{IMGS_DIR}', cl))
            #setting the path to images which will be processed
            dataset_path = os.path.join(f'{self._PATH}', cl)
            names = os.listdir(dataset_path)
            
            for name in names:
                #reading images from the choosen dataset
                I = eng.imread(os.path.join(dataset_path, f'{name}'))
                #converting MATLAB matrices into numpy arrays
                I = np.asarray(I)
                
                #performing the 2-D Wavelet decomposition
                c, s = eng.wavedec2(I, N, wave, nargout=2)
                
                """s is the bookkeping matrix: it contains the dimensions of the wavelet
                coefficients by level and is used to parse the wavelet decomposition vector c"""

                """c is the vector of decomposition coefficients: it first contains the unrolled 
                approximation matrix, and then the three detail matrices (Horizontal, Vertical, 
                Diagonal) for each of the 3 decomposition levels """

                #converting MATLAB matrices into numpy arrays
                s = np.asarray(s)
                c = np.asarray(c)
                #dimensional adjustment
                c = c[0]

                #extraction of the first level approximation and detail coefficients
                A1 = eng.appcoef2(c,s,wave,1, nargout=1)
                H1,V1,D1 = eng.detcoef2('all',c,s,1, nargout=3)

                #extraction of the second level approximation and detail coefficients
                A2 = eng.appcoef2(c,s,wave,2, nargout=1)
                H2,V2,D2 = eng.detcoef2('all',c,s,2, nargout=3)

                #extraction of the third level approximation and detail coefficients
                A3 = eng.appcoef2(c,s,wave,3, nargout=1)
                H3,V3,D3 = eng.detcoef2('all',c,s,3, nargout=3)

                """Approximation and detail coefficients are stored in the c vector.
                It cointains the unrolled coefficient matrices as it follows:
                [A3(:); H3(:); V3(:); D3(:); H2(:); V2(:); D2(:); H1(:); V1(:); D1(:)]."""

                """We will create a vector of labels where:
                First level detail coefficients (H1,V1,D1) are labelled as 1
                Second level detail coefficients (H2,V2,D2) are labelled as 2
                Third level detail coefficients (H3,V3,D3) are labelled as 3
                Third level approximation coefficients (A3) are labelled as 0"""

                #setting the size of labels' vector
                size_CM = eng.prod(s,2, nargout=1)
                #converting MATLAB matrices into numpy arrays
                size_CM = np.asarray(size_CM)

                #initializing labels' vector
                c_labels= eng.zeros(1,size_CM[0])
                #converting MATLAB matrices into numpy arrays
                c_labels = np.asarray(c_labels)
                #dimensional adjustement
                c_labels = c_labels[0]

                for il in range(1, N+1):
                    #creating a vector of "1"
                    ones = eng.ones(1,3*np.double(size_CM[il]))
                    #converting MATLAB matrices into numpy arrays
                    ones = np.asarray(ones)
                    #dimensional adjustement
                    ones = ones[0]
                    #setting labels' vector
                    c_labels = np.concatenate((c_labels, np.double(N+1-il)*ones))
                

                #setting the stdev of coefficients' ditribution at level 1
                std1=np.double(eng.std(c[c_labels==1], nargout=1))
                #setting the stdev of coefficients' ditribution at level 2
                std2=np.double(eng.std(c[c_labels==2], nargout=1))
                #setting the stdev of coefficients' ditribution at level 3
                std3=np.double(eng.std(c[c_labels==3], nargout=1))

                """We can set thresholds of coefficients in terms of the stdev of their
                distributions and set to zero the 'low spatial frequency approximation' 
                information while keeping only the 'high spatial frequency details' that
                exceed a certain number Q of standard deviations""" 

                c_mod = c.copy()
                c_mod.setflags(write=1)
                c_mod[c_labels==0]=0

                c_mod[(c_labels==1)&(abs(c)<Q*std1)]=0
                c_mod[(c_labels==2)&(abs(c)<Q*std2)]=0
                c_mod[(c_labels==3)&(abs(c)<Q*std3)]=0

                #reconstructing filtered images
                I_rec = eng.waverec2(c_mod,s,wave, nargout=1)
                ##converting MATLAB matrices into numpy arrays
                I_rec = np.asarray(I_rec)

                #saving wavelet_filtered images in the new directory
                save_image(os.path.join(f'{IMGS_DIR}', cl, f'{name}.png'), I_rec)
                #converting saved images to grayscale
                convert_to_grayscale(os.path.join(f'{IMGS_DIR}', cl, f'{name}.png'))


        #setting the self path to the new wavelet-filtered images dataset
        self._PATH = IMGS_DIR'''

    def get_random_images(self, size:int, classes=None):
        """Extract random elements from the dataset
        .....
        Parameters
        ----------
        size: int
            number of random images """
        
        if classes is not None:
            idx = []
            for cl in classes:
                print(cl)
                idx.append(np.where(self.y == cl)[0])
            
            print(idx)
            idx = np.squeeze(np.array(idx))
            rand_idx = np.random.randint(0, len(idx), size=size)
            rand_idx = idx[rand_idx]
            print('rand:',rand_idx)
        else:
            rand_idx = np.random.randint(0, len(self.X), size=size)
            
        X = self.X[rand_idx]
        y = self.y[rand_idx]
        return X, y

class Model:
    """Perform hyperparameters search, k-fold and train ensemble"""
    def __init__(self, data, overwrite, max_trials, k=5):
        self.X = data.X
        self.y = data.y
        self.max_trials = max_trials
        self.overwrite = overwrite
        self.k = k
        self.modelBuilder = hyp_tuning_model
        self.models_list = []
        self._SELECTED_MODEL = ''

        @property
        def selected_model(self):
            return self._SELECTED_MODEL
        
        @selected_model.setter
        def selected_model(self, model_name):
            if type(model_name) != str:
                raise TypeError(f'Expected str type got {type(model_name)}')
            self._SELECTED_MODEL = model_name


    def train(self):
        """Perform hyperparameters search, k-fold and train ensemble"""
        #self.fold()
        self.set_models_list()
        self.get_ensemble()

    def tuner(self, X_dev, y_dev, modelBuilder, i, k=5):
        """If overwrite is true performes hps search, else takes default hps.
        ....
        Parameters
        ----------
        X_dev: np.array
            X for development/design set (train+validation)
        y_dev: np.array
            y for development/design set (train+validation)
        modelBuilder: keras.Hypermodel
            funtion returning the hypermodel or model if hps are fixed
        i: int
            k-fold index
        k:int
            number of folds. Default 5
        """
        tuner_dir = os.path.join('tuner', f'tuner_{i}')
        if self.overwrite :
            project_name = 'tuner'
        else:
            project_name = 'base'
        tuner = kt.BayesianOptimization(modelBuilder, objective='val_accuracy', max_trials=self.max_trials, 
                                        overwrite=self.overwrite, directory=tuner_dir, project_name=project_name)
        tuner.search(X_dev, y_dev, epochs=50, validation_split=1/(k-1), batch_size=64, 
                    callbacks=callbacks, verbose=1)
        best_hps = tuner.get_best_hyperparameters(num_trials=1)[0]
        best_model = tuner.get_best_models()[0]
        return best_hps, best_model
    
    def set_models_list(self):
        for i in range(self.k):
            self.models_list.append(f'model_{i}') 

    def fold(self, k=5):
        """Performs kfold & hps search in each fold.
        Returs best hps list (one entry for each fold)"""
        #initialize lists to keep track of each fold's performance
        test_acc=[]
        dimension=[]
        best_hps_list=[]

        #preparation for figures
        plt.figure('ROC - Testing')
        plt.title('ROC - Testing')
        tprs = []
        aucs = []
        mean_fpr = np.linspace(0, 1, 100)
        plt.figure('Confusion Matrices')
        plt.title('Confusion Matrices')
        colors = ['green', 'red', 'blue', 'darkorange', 'gold']

        # here model selection and model assessment are peformed (k-fold + hold-out)
        fold  = KFold(n_splits=self.k, shuffle=True, random_state=42)
        for i, (dev_idx, test_idx) in enumerate(fold.split(self.X, self.y)):
            #divide development and test sets
            X_dev, X_test = self.X[dev_idx], self.X[test_idx]
            y_dev, y_test = self.y[dev_idx], self.y[test_idx]
            print('--------------')
            print(f'FOLD {i+1}')
            print('--------------')
            best_hps, best_model = self.tuner(X_dev, y_dev, self.modelBuilder, i, k=5)
            best_hps_list.append(best_hps)

            #train best model and assess model's performance
            history = best_model.fit(X_dev, y_dev, epochs=100, batch_size=64, validation_split=1/(k-1), callbacks=callbacks)
            accuracy= round(best_model.evaluate(X_test, y_test)[1],3)

            dimension.append(count_params(best_model.trainable_weights))
            test_acc.append(accuracy)
            
            #add this fold's results to the plots
            plot(history=history, i=i)
            ROC(X_test, y_test=y_test, model=best_model, color=colors[i], i=i+1, mean_fpr=mean_fpr, tprs=tprs, aucs=aucs)
            get_confusion_matrix(X_test, y_test=y_test, model=best_model, i=i+1)

            #retrain on the whole dataset and save best model 
            best_model.save(f'model_{i}')

        # plot mean and stdev in ROC curve plot
        plot_mean_stdev(tprs, mean_fpr, aucs)
        comparison_plot(names=self.models_list, dimension=dimension, accuracy=test_acc)
    
        print(f'Test Accuracy {test_acc}')
        print(f'Expected accuracy: {stats.mean(test_acc):.2f}+/- {stats.stdev(test_acc):.2f}')
        print(f'best hps:')
        for i, hps in enumerate(best_hps_list):
            print(f'--------------------')
            print(f'Model_{i} chosen hps:')
            print(f'--------------------')
            print(f"Depth: {hps.get('depth')}")
            print(f"Conv_in: {hps.get('Conv2d_init')}")
            print(f"Dropout: {hps.get('dropout')}")
            print(f'--------------------')
        plt.show(block=False)
    

    def get_predictions(self, X=None):
        """Creates and returns an array of model predictions. Each column corrispond to one expert preds.
        Used both in training and in assessing the performance of the model (when X=None the predictions are 
        evaluated on self.X, otherwise on whatever X is passed)"""
        if X is None:
            X = self.X
        y = np.empty(shape=(len(X), len(self.models_list)))
        for count, expert in enumerate(self.models_list):
            expert = load_model(expert)
            y[:, count] = np.squeeze(expert.predict(X))
        return y

    def get_ensemble(self):
        """Create and train ensemble starting from models previously obtained"""
        #get each expert's predictions
        X = self.get_predictions()

        # transform to tensors
        X = torch.from_numpy(X.astype('float32'))
        y = torch.from_numpy(self.y.astype('float32'))

        # split train and validation
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, shuffle=True, random_state=24)
        
        # create dataset for external test
        test_data = Data()
        test_data.path=os.path.join('New_dataset', 'NEW_DATA')
        X_test, y_test = test_data.get_random_images(size=25)
        X_test = self.get_predictions(X_test)
        X_test = torch.from_numpy(X_test.astype('float32'))
        y_test = torch.from_numpy(y_test.astype('float32'))

        # model = weighted average 
        model = pytorch_linear_model(in_features=len(self.models_list), out_features=1)   
    
        # weights initialization and bias set to zero not trainable
        w_init = weights_init
        model.apply(w_init)

        optimizer = torch.optim.Adam(model.parameters(), lr=0.005, betas=(0.9, 0.9999))
        # we want the sum of the weights to be one
        normalizer = WeightNormalizer()

        weights, final_acc, test_acc = train_ensemble(model, optimizer, normalizer, X_train, y_train, X_val, y_val, X_test, y_test, batch_size=20, name='ensemble')
        print(f'Final accuracy: {final_acc}')
        print(f'Test accuracy: {test_acc}')
        for w in weights:
            weights = torch.tensor(w.data).numpy()
            print(type(weights))
            print(type(weights.max()))
            best_idx = np.where(weights==weights.max())[0][0]
            print(best_idx)
            print(type(best_idx))
            self._SELECTED_MODEL = f'model_{best_idx}'

        plt.show()


