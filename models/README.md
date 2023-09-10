## Model Tuning Results

| Approaches          | Parameters                                                                                            | cv_auc | test_auc |
| ------------------- | ----------------------------------------------------------------------------------------------------- | ------ | -------- |
| Logistic Regression | C = 0.01, max_iter = 100, penalty = l2, solver = liblinear                                            | 0.947  | 0.965    |
| SVM                 | C = 100, kernel = rbf                                                                                 | 0.936  | 0.978    |
| Decision Tree       | criterion = gini, max_depth = 16, max_features = 3, min_impurity_decrease = 0.0, min_samples_leaf = 5 | 0.990  | 0.986    |
| Random Forest       | max_depth = 9, max_features = 3, n_estimators = 200                                                   | 0.991  | 0.996    |
| AdaBoost            | learning_rate = 1, n_estimators = 500                                                                 | 0.976  | 0.990    |
| Gradient Boosting   | learning_rate = 0.1, max_depth = 10, n_estimators = 200                                               | 0.997  | 0.994    |
| XGBoost             | learning_rate = 0.1, max_depth = 10, n_estimators = 200                                               | 0.997  | 0.994    |
