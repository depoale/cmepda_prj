
import os
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
from tqdm import tqdm
import copy
from sklearn.preprocessing import LabelEncoder

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from tools_for_Pytorch import EarlyStopping, weights_init_uniform_fan_in, count_parameters
import torch
from torch import nn
from utils import read_imgs
from sklearn.model_selection import KFold, ShuffleSplit, train_test_split
from tools_for_Pytorch import EarlyStopping, weights_init_uniform_fan_in, count_parameters
import keras 
from tools_for_Pytorch import get_predictions

if torch.cuda.is_available():
    print('CUDA is available. Working on GPU')
    DEVICE = torch.device('cuda')
else:
    print('CUDA is not available. Working on CPU')
    DEVICE = torch.device('cpu')


global test_mse_list, epochs_list

test_mse_list = []
epochs_list = []


def train(model, optimizer, X_train, y_train, X_val, y_val, X_test, y_test, name=None):

    '''Performs the forward and backwards training loop until early stopping, then computes the metric'''

    loss_fn = nn.MSELoss()
    early_stopping = EarlyStopping()

    torch.manual_seed(42)

    epochs = 500
    epoch_count = []

    train_mse_values = []
    val_mse_values = []
    test_mse_values = []


    for epoch in range(epochs):

        # train mode
        model.train()

        # 1. Forward pass on train data
        train_pred = model(X_train)
        
        # 2. Calculate the loss
        train_mse = loss_fn(train_pred, y_train)

        # 3. Zero grad of the optimizer
        optimizer.zero_grad()
        
        # 4. Backpropagation
        train_mse.backward()
        
        # 5. Progress the optimizer
        optimizer.step()
        
        # evaluation mode
        model.eval()
        
        # make predictions with model without gradient tracking 
        with torch.inference_mode():

            # 1. Forward pass on validation and test data
            val_pred = model(X_val)
            test_pred = model(X_test)

            # 2. Caculate mse and on validation and test data        
            val_mse = loss_fn(val_pred, y_val)                    
            test_mse = loss_fn(test_pred, y_test)

        epoch_count.append(epoch)
        train_mse_values.append(train_mse)
        val_mse_values.append(val_mse)
        test_mse_values.append(test_mse)

    
        # early_stopping needs the validation loss to check if it has decreased
        early_stopping(val_mse, model)
        
        if early_stopping.early_stop:
            print("Early stopping")
            break
            
        if epoch % 10 == 0:
            print(f"Epoch is {epoch:<3} | Training MSE: {train_mse:.3f} | Validation MSE: {val_mse:.3f}")

    print(f"Epoch is {epoch:<3} \nTraining MSE: {train_mse:.3f} | Validation MSE: {val_mse:.3f} | Test MSE: {test_mse:.3f}")
   

    test_mse_list.append(test_mse_values[-1])
    epochs_list.append(epoch_count[-1])

    if name: 
        fig,ax = plt.subplots()
        plt.plot(epoch_count, np.array(torch.tensor(train_mse_values).numpy()), label="Training MSE")
        plt.plot(epoch_count, val_mse_values, label="Validation MSE", linestyle='dashed')
        plt.title(name  + " TR and VL MSE")
        plt.ylabel("MSE")
        plt.xlabel("Epochs")
        plt.legend()
        plt.show(block = False)
    
    return model.parameters()

VAL_SPLIT =0.2
X, y = read_imgs('total_data', [0,1])

model1=keras.models.load_model('model1')
model2=keras.models.load_model('model2')
model3=keras.models.load_model('model3')
models_list = [model1, model2, model3]

#data for the ensemble model comes from the predictions of the experts
X = get_predictions(X, models_list)

X = torch.from_numpy(X. astype('float32'))
print(X.dtype)
y = torch.from_numpy(y.astype('float32'))
print(y.dtype)
w_init = weights_init_uniform_fan_in
X_dev, X_test, y_dev, y_test = train_test_split(X, y, test_size=VAL_SPLIT, shuffle=False)
X_train, X_val, y_train, y_val = train_test_split(X_dev, y_dev, test_size=VAL_SPLIT, shuffle=False)
    
model = nn.Sequential(nn.Linear(in_features=len(models_list), out_features=1))

# weights initialization 
model.apply(w_init)

optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

weights = train(model, optimizer, X_train, y_train, X_val, y_val, X_test, y_test, name='no')
for p in weights:
    print(p)
plt.show()