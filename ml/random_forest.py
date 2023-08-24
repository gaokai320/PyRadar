from sklearn.ensemble import RandomForestClassifier
from metrics_util import get_all_metrics
from data_utils import write_result,load_train_test_data



class RandomForest:
    def __init__(self, data_path,fold,n_estimators=10, criterion='gini'):
        self.data = data_path
        self.n_estimators = n_estimators
        self.criterion = criterion
        self.fold=fold
    def run(self):
        
        X_train, X_test, y_train, y_test = load_train_test_data(self.data,self.fold)

        rf = RandomForestClassifier(n_estimators=self.n_estimators, criterion=self.criterion)
        rf.fit(X_train, y_train)
        y_pred=rf.predict(X_test)
        y_score=rf.predict_proba(X_test)[:,1]
        auc,precision, recall, f1, average_precision, fpr, tpr,ndcg=get_all_metrics(y_test,y_pred,y_score)
        acc=rf.score(X_test,y_test)

        write_result(f"res/{rf.__class__.__name__}_res.csv",f"{auc},{acc},{precision},{recall},{f1},{self.fold}\n")

        

if __name__ == '__main__':

    for fold in range(10):
        
        model = RandomForest("/data/kyle/radar/data/validator_dataset.csv",fold)

        model.run()

