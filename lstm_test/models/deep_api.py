# -*- coding: utf-8 -*-
"""
Integrate a model with the DEEP API
"""

import json
import argparse
import pkg_resources
# import project's config.py
import lstm_test.config as cfg
from aiohttp.web import HTTPBadRequest

from functools import wraps

from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import StandardScaler
import pandas as pd
from tensorflow.keras.models import load_model

# multivariate data preparation
from numpy import array
from numpy import hstack
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM
from tensorflow.keras.layers import Dense
import numpy as np
import requests
## Authorization
from flaat import Flaat
flaat = Flaat()



def mape(actual, pred): 
    actual, pred = np.array(actual), np.array(pred)
    return np.mean(np.abs((actual - pred) / actual)) * 100

def compute_metrics_fn(y_valid_resc, y_hat_resc):
    ## actual train and test values
    mae_ = mean_absolute_error(y_valid_resc, y_hat_resc)
    mse_ = mean_squared_error(y_valid_resc, y_hat_resc)
    rmse_ = mean_squared_error(y_valid_resc, y_hat_resc, squared = False)
    cvrmse_ = rmse_/np.mean(y_valid_resc)*100 # it is a percentage
    mape_ = mape(y_valid_resc, y_hat_resc)
    return mae_, mse_, rmse_, cvrmse_, mape_

# split a multivariate sequence into samples
def split_sequences(sequences, n_steps):
	X, y = list(), list()
	for i in range(len(sequences)):
		# find the end of this pattern
		end_ix = i + n_steps
		# check if we are beyond the dataset
		if end_ix > len(sequences)-1:
			break
		# gather input and output parts of the pattern
		seq_x, seq_y = sequences[i:end_ix, :], sequences[end_ix, :]
		X.append(seq_x)
		y.append(seq_y)
	return array(X), array(y)

def _catch_error(f):
    """Decorate function to return an error as HTTPBadRequest, in case
    """
    @wraps(f)
    def wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            raise HTTPBadRequest(reason=e)
    return wrap


def _fields_to_dict(fields_in):
    """
    Example function to convert mashmallow fields to dict()
    """
    dict_out = {}
    
    for key, val in fields_in.items():
        param = {}
        param['default'] = val.missing
        param['type'] = type(val.missing)
        if key == 'files' or key == 'urls':
            param['type'] = str

        val_help = val.metadata['description']
        if 'enum' in val.metadata.keys():
            val_help = "{}. Choices: {}".format(val_help, 
                                                val.metadata['enum'])
        param['help'] = val_help

        try:
            val_req = val.required
        except:
            val_req = False
        param['required'] = val_req

        dict_out[key] = param
    return dict_out


def get_metadata():
    """
    Function to read metadata
    https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/latest/user/v2-api.html#deepaas.model.v2.base.BaseModel.get_metadata
    :return:
    """
    print("entra aqui get metadata")
    module = __name__.split('.', 1)

    try:
        pkg = pkg_resources.get_distribution(module[0])
    except pkg_resources.RequirementParseError:
        # if called from CLI, try to get pkg from the path
        distros = list(pkg_resources.find_distributions(cfg.BASE_DIR, 
                                                        only=True))
        if len(distros) == 1:
            pkg = distros[0]
    except Exception as e:
        raise HTTPBadRequest(reason=e)

    ### One can include arguments for train() in the metadata
    train_args = _fields_to_dict(get_train_args())
    # make 'type' JSON serializable
    for key, val in train_args.items():
        print(key)
        train_args[key]['type'] = str(val['type'])

    ### One can include arguments for predict() in the metadata
    predict_args = _fields_to_dict(get_predict_args())
    # make 'type' JSON serializable
    for key, val in predict_args.items():
       print(key)
       predict_args[key]['type'] = str(val['type'])

    meta = {
        'name': None,
        'version': None,
        'summary': None,
        'home-page': None,
        'author': None,
        'author-email': None,
        'license': None,
        'help-train' : train_args,
        'help-predict' : predict_args
    }

    for line in pkg.get_metadata_lines("PKG-INFO"):
        line_low = line.lower() # to avoid inconsistency due to letter cases
        for par in meta:
            if line_low.startswith(par.lower() + ":"):
                _, value = line.split(": ", 1)
                meta[par] = value

    return meta


def warm():
    """
    https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/latest/user/v2-api.html#deepaas.model.v2.base.BaseModel.warm
    :return:
    """
    # e.g. prepare the data


def get_predict_args():
    """
    https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/latest/user/v2-api.html#deepaas.model.v2.base.BaseModel.get_predict_args
    :return:
    """
    return cfg.PredictArgsSchema().fields


@_catch_error
def predict(**kwargs):
    """
    Function to execute prediction
    https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/latest/user/v2-api.html#deepaas.model.v2.base.BaseModel.predict
    :param kwargs:
    :return:
    """
    # use the schema
    schema = cfg.PredictArgsSchema()
    # deserialize key-word arguments
    pred_args = schema.load(kwargs)
    #print("PRINT THE TRAINING ARGUMENTS>> ", train_args)
    the_url=pred_args['urls']
    r = requests.get(the_url, allow_redirects=True)
    the_path=cfg.DATA_DIR+'/pred_file.csv'
    open(the_path, 'wb').write(r.content)
    # 1. implement your training here
    print("Starting the prediction")
    df = pd.read_csv(the_path, sep=",", header=None)
    dataset = df.to_numpy()
    print(dataset)
    # choose a number of time steps
    n_steps = pred_args['nSteps']
    # convert into input/output
    X, y = split_sequences(dataset, n_steps)
    print("Loading model....")
    print(cfg.MODELS_DIR+'/lstm.h5')
    model = load_model(cfg.MODELS_DIR+'/lstm.h5')
    print("model loaded")
    yhat = model.predict(X, verbose=0)
    print(yhat)
    print(y)
    return(json.dumps({"prediction": yhat.tolist()}))


    if (not any([kwargs['urls'], kwargs['files']]) or
            all([kwargs['urls'], kwargs['files']])):
        raise Exception("You must provide either 'url' or 'data' in the payload")

    if kwargs['files']:
        kwargs['files'] = [kwargs['files']]  # patch until list is available
        return _predict_data(kwargs)
    elif kwargs['urls']:
        kwargs['urls'] = [kwargs['urls']]  # patch until list is available
        return _predict_url(kwargs)


def _predict_data(*args):
    """
    (Optional) Helper function to make prediction on an uploaded file
    """
    message = 'Not implemented (predict_data())'
    message = {"Error": message}
    return message


def _predict_url(*args):
    """
    (Optional) Helper function to make prediction on an URL
    """
    message = 'Not implemented (predict_url())'
    message = {"Error": message}
    return message


def get_train_args():
    """
    https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/latest/user/v2-api.html#deepaas.model.v2.base.BaseModel.get_train_args
    :param kwargs:
    :return:
    """
    
    return cfg.TrainArgsSchema().fields


###
# @flaat.login_required() line is to limit access for only authorized people
# Comment this line, if you open training for everybody
# More info: see https://github.com/indigo-dc/flaat
###
#@flaat.login_required() # Allows only authorized people to train
def train(**kwargs):
    """
    Train network
    https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/latest/user/v2-api.html#deepaas.model.v2.base.BaseModel.train
    :param kwargs:
    :return:
    """
    
    message = { "status": "ok",
                "training": [],
              }
    import os
    # use the schema
    schema = cfg.TrainArgsSchema()
    # deserialize key-word arguments
    train_args = schema.load(kwargs)
    #print("PRINT THE TRAINING ARGUMENTS>> ", train_args)
    the_url=train_args['urls']
    r = requests.get(the_url, allow_redirects=True)
    the_path=cfg.DATA_DIR+'/train_file.csv'
    open(the_path, 'wb').write(r.content)
    # 1. implement your training here
    print("Starting the training")
    df = pd.read_csv(the_path, sep=",")
    dataset = df.to_numpy()
    print(dataset)
    # choose a number of time steps
    n_steps = train_args['nSteps']
    # convert into input/output
    X, y = split_sequences(dataset, n_steps)
    # the dataset knows the number of features, e.g. 2
    n_features = X.shape[2]
    # define model
    model = Sequential()
    model.add(LSTM(100, activation='relu', return_sequences=True, input_shape=(n_steps, n_features)))
    model.add(LSTM(100, activation='relu'))
    model.add(Dense(n_features))
    model.compile(optimizer='adam', loss='mse')
    # fit model
    model.fit(X, y, epochs=train_args['epochs'], verbose=2)
   # model.fit(X,y, epochs=20, verbose=2)
    model.save(cfg.MODELS_DIR+'/lstm.h5')  # creates a HDF5 file 'my_model.h5'
    print("model saved")
    # 2. update "message"
    train_results = {"modelo": model}
    #train_results = { "Error": "No model implemented for training (train())" }
    message["training"].append(train_results)
    del model
    return message


# during development it might be practical 
# to check your code from CLI (command line interface)
def main():
    """
    Runs above-described methods from CLI
    (see below an example)
    """


    if args.method == 'get_metadata':
        meta = get_metadata()
        print(json.dumps(meta))
        return meta
    elif args.method == 'predict':
        # [!] you may need to take special care in the case of args.files [!]
        results = predict(**vars(args))
        print(json.dumps(results))
        return results
    elif args.method == 'train':
        results = train(**vars(args))
        print(json.dumps(results))
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Model parameters', 
                                     add_help=False)

    cmd_parser = argparse.ArgumentParser()
    subparsers = cmd_parser.add_subparsers(
                            help='methods. Use \"deep_api.py method --help\" to get more info', 
                            dest='method')

    ## configure parser to call get_metadata()
    get_metadata_parser = subparsers.add_parser('get_metadata', 
                                         help='get_metadata method',
                                         parents=[parser])
    # normally there are no arguments to configure for get_metadata()

    ## configure arguments for predict()
    predict_parser = subparsers.add_parser('predict', 
                                           help='commands for prediction',
                                           parents=[parser]) 
    # one should convert get_predict_args() to add them in predict_parser
    # For example:
    predict_args = _fields_to_dict(get_predict_args())
    for key, val in predict_args.items():
        predict_parser.add_argument('--%s' % key,
                               default=val['default'],
                               type=val['type'],
                               help=val['help'],
                               required=val['required'])

    ## configure arguments for train()
    train_parser = subparsers.add_parser('train', 
                                         help='commands for training',
                                         parents=[parser]) 
    # one should convert get_train_args() to add them in train_parser
    # For example:
    train_args = _fields_to_dict(get_train_args())
    for key, val in train_args.items():
        train_parser.add_argument('--%s' % key,
                               default=val['default'],
                               type=val['type'],
                               help=val['help'],
                               required=val['required'])

    args = cmd_parser.parse_args()
    
    main()
