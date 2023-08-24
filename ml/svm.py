from sklearn.svm import SVC
from metrics_util import get_all_metrics
import data_utils
from data_utils import write_result,load_train_test_data




class SVM:
    def __init__(self, data_path,fold):
        self.data = data_path
        self.fold = fold

    def run(self):
        X_train, X_test, y_train, y_test = load_train_test_data(self.data,self.fold)
       
        svc = SVC(probability=True)
        svc.fit(X_train, y_train)
        y_pred=svc.predict(X_test)
        y_score=svc.predict_proba(X_test)[:,1]
        auc,precision, recall, f1, average_precision, fpr, tpr,ndcg=get_all_metrics(y_test,y_pred,y_score)
        acc=svc.score(X_test,y_test)
        write_result(f"res/{svc.__class__.__name__}_res.csv",f"{auc},{acc},{precision},{recall},{f1},{self.fold}\n")


if __name__ == '__main__':
    for fold in range(10):
        model = SVM("/data/kyle/radar/data/validator_dataset.csv",fold)
        model.run()
