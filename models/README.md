## Model Tuning Results

| Approaches          | Parameters                                                                                            | cv_auc | test_auc |
| ------------------- | ----------------------------------------------------------------------------------------------------- | ------ | -------- |
| Logistic Regression | C = 100, max_iter = 100, penalty = l2, solver = liblinear                                             | 0.956  | 0.963    |
| SVM                 | C = 100, kernel = rbf                                                                                 | 0.936  | 0.981    |
| Decision Tree       | criterion = gini, max_depth = 20, max_features = 4, min_impurity_decrease = 0.0, min_samples_leaf = 5 | 0.989  | 0.982    |
| Random Forest       | max_depth = 9, max_features = 3, n_estimators = 400                                                   | 0.991  | 0.995    |
| AdaBoost            | learning_rate = 1, n_estimators = 450                                                                 | 0.976  | 0.992    |
| Gradient Boosting   | learning_rate = 0.01, max_depth = 10, n_estimators = 1000                                             | 0.996  | 0.992    |
| XGBoost             | learning_rate = 0.5, max_depth = 9, n_estimators = 100                                                | 0.997  | 0.991    |
