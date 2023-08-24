from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score
from data_utils import write_result,load_train_test_data
from metrics_util import get_all_metrics


class XGB:
    def __init__(self,data_path ,fold):
        self.data = data_path
        self.fold=fold
    def run(self):
        
        X_train, X_test, y_train, y_test = load_train_test_data(self.data,self.fold)

        model = XGBClassifier()               
        model.fit(X_train,y_train)
        print(model.get_params())            
        y_pred = model.predict(X_test)
        y_score=model.predict_proba(X_test)[:,1]
       
        auc,precision, recall, f1, average_precision, fpr, tpr,ndcg=get_all_metrics(y_test,y_pred,y_score)
        acc=accuracy_score(y_test,y_pred)
        write_result(f"res/{model.__class__.__name__}_res.csv",f"{auc},{acc},{precision},{recall},{f1},{self.fold}\n")

if __name__ == '__main__':
    for fold in range(10):
        model = XGB("/data/kyle/radar/data/validator_dataset.csv",fold)
      
        model.run()

