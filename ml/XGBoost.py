from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score
import data_utils
from metrics_util import get_all_metrics


class XGB:
    def __init__(self,data_path ,fold):
        self.data = data_path
        self.fold=fold
    def run(self):
        
        X_train, X_test, y_train, y_test = data_utils.load_train_test_data(self.data,self.fold)

        model = XGBClassifier()               
        model.fit(X_train,y_train)
        print(model.get_params())            
        y_pred = model.predict(X_test)
        y_score=model.predict_proba(X_test)[:,1]
       
        auc,precision, recall, f1, average_precision, fpr, tpr,ndcg=get_all_metrics(y_test,y_pred,y_score)
        acc=accuracy_score(y_test,y_pred)
        #print(f"acc:{acc},auc:{auc},precision:{precision},recall:{recall},f1:{f1},average_precision:{average_precision},ndcg:{ndcg}")

if __name__ == '__main__':
    for fold in range(1):
        model = XGB("/data/kyle/radar/data/validator_dataset.csv",fold)
      
        model.run()

