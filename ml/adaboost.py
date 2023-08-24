from sklearn.ensemble import AdaBoostClassifier
from metrics_util import get_all_metrics
from data_utils import write_result,load_train_test_data



class AdaBoost:
    def __init__(self, data_path,fold, base_estimator=None, n_estimators=10):
        self.data = data_path
        self.fold=fold
        self.base_estimator = base_estimator
        self.n_estimators = n_estimators
        

    def run(self):
        X_train, X_test, y_train, y_test = load_train_test_data(self.data,self.fold)
        
        ab = AdaBoostClassifier(base_estimator=self.base_estimator, n_estimators=self.n_estimators)
        ab.fit(X_train, y_train)
        y_pred=ab.predict(X_test)
        y_score=ab.predict_proba(X_test)[:,1]
        
        auc,precision, recall, f1, average_precision, fpr, tpr,ndcg=get_all_metrics(y_test,y_pred,y_score)
        acc=ab.score(X_test,y_test)
        write_result(f"res/{ab.__class__.__name__}_res.csv",f"{auc},{acc},{precision},{recall},{f1},{self.fold}\n")


if __name__ == '__main__':
    for fold in range(10):
        model = AdaBoost("/data/kyle/radar/data/validator_dataset.csv",fold)
        model.run()

