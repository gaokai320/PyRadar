import pandas as pd



def load_raw_data(file_path):

    df = pd.read_csv(file_path)
    return df[["num_phantom_pyfiles","setup_change","num_downloads","tag_match","num_maintainers","num_maintainer_pkgs","maintainer_max_downloads","label"]]




def load_train_test_data(file_path,fold):

    T= load_raw_data(file_path)
    T.dropna(inplace=True)
    p_train_split1=int((fold/10)*T.shape[0])
    p_train_split2=int((fold/10+0.1)*T.shape[0])


    train_data1=T.iloc[:p_train_split1]
    train_data2=T.iloc[p_train_split2:]
    train_data=pd.concat([train_data1,train_data2],axis=0)

    test_data=T.iloc[p_train_split1:p_train_split2]

    #正样本过采样
    p_train = train_data[train_data.label == 1]
    p_train = p_train.sample(frac=10000/p_train.shape[0],replace=True,random_state=0)

    #负样本欠采样
    n_train = train_data[train_data.label == -1]
    n_train=n_train.sample(frac=10000/n_train.shape[0],replace=True,random_state=0)
    n_train.label=0

    train_data=pd.concat([p_train,n_train],ignore_index=True)
    train_data=train_data.sample(frac=1, random_state=0)



    y_train=train_data['label']
    y_test=test_data['label']

    del train_data['label']
    del test_data['label']
    X_train=train_data
    X_test=test_data

    return X_train, X_test, y_train, y_test




