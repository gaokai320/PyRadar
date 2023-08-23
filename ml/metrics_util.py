from sklearn.metrics import recall_score
from sklearn.metrics import precision_score
from sklearn.metrics import f1_score
from sklearn.metrics import average_precision_score
from sklearn.metrics import roc_curve
from sklearn.metrics import auc

from sklearn.metrics import ndcg_score
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def get_dcg(y_pred, y_true, k):
    #注意y_pred与y_true必须是一一对应的，并且y_pred越大越接近label=1(用相关性的说法就是，与label=1越相关)
    df = pd.DataFrame({"y_pred":y_pred, "y_true":y_true})
    df = df.sort_values(by="y_pred", ascending=False)  # 对y_pred进行降序排列，越排在前面的，越接近label=1
    df = df.iloc[0:k, :]  # 取前K个
    dcg = (2 ** df["y_true"] - 1) / np.log2(np.arange(1, df["y_true"].count()+1) + 1) # 位置从1开始计数
    dcg = np.sum(dcg)
    return dcg
    
def get_ndcg(df, k):
    # df包含y_pred和y_true
    dcg = get_dcg(df["y_pred"], df["y_true"], k)
    idcg = get_dcg(df["y_true"], df["y_true"], k)
    ndcg = dcg / idcg
    return ndcg


def get_all_metrics(eval_labels, pred_labels,scores):
    fpr, tpr, thresholds_keras = roc_curve(eval_labels,scores)
    print(thresholds_keras[np.argmax(tpr - fpr)])
    auc_ = auc(fpr, tpr)
    print("auc_keras:" + str(auc_))

    precision = precision_score(eval_labels, pred_labels)
    print('Precision score: {0:0.8f}'.format(precision))

    recall = recall_score(eval_labels, pred_labels)
    print('Recall score: {0:0.8f}'.format(recall))

    f1 = f1_score(eval_labels, pred_labels)
    print('F1 score: {0:0.8f}'.format(f1))

    average_precision = average_precision_score(eval_labels, pred_labels)
    print('Average precision-recall score: {0:0.8f}'.format(average_precision))

    df = pd.DataFrame({"y_pred":scores, "y_true":eval_labels})
    ndcg=get_ndcg(df,df.shape[0])
    print('ndcg score: {0:0.8f}'.format(ndcg))
    
    return auc_, precision, recall, f1, average_precision, fpr, tpr,ndcg #,thresholds_keras[np.argmax(tpr - fpr)]


def save_roc_curve(fpr, tpr, roc_auc,file_name):
    fig = plt.figure()
    lw = 2
    plt.plot(fpr, tpr, color='darkorange',
            lw=lw, label='ROC curve (area = %0.2f)' % roc_auc)
    plt.plot([0, 1], [0, 1], color='green', lw=lw, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    #plt.title('Receiver operating characteristic')
    plt.legend(loc="lower right")
    # plt.show()
    
    fig.savefig(file_name)


