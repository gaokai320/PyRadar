## Model Tuning Results

## Logistic Regression

| Over Sampling | C     | max_iter | penalty | solver    | val_auc   | test_auc |
| ------------- | ----- | -------- | ------- | --------- | --------- | -------- |
| Random        | 0.001 | 100      | l1      | liblinear | **0.927** | 0.921    |
| SMOTE         | 0.001 | 100      | l1      | liblinear | 0.925     | 0.922    |
| ADASYN        | 0.001 | 200      | l1      | saga      | 0.908     | 0.898    |

## Decision Tree

| Over Sampling | criterion | max_depth | max_features | min_impurity_decrease | min_samples_leaf | val_auc   | test_auc |
| ------------- | --------- | --------- | ------------ | --------------------- | ---------------- | --------- | -------- |
| Random        | entropy   | 5         | 6            | 0.0                   | 5                | **0.974** | 0.973    |
| SMOTE         | entropy   | 6         | 6            | 0.0                   | 10               | 0.973     | 0.968    |
| ADASYN        | entropy   | 6         | 6            | 0.0                   | 15               | 0.972     | 0.966    |

## Random Forest

| Over Sampling | max_depth | max_features | n_estimators | val_auc   | test_auc |
| ------------- | --------- | ------------ | ------------ | --------- | -------- |
| Random        | 9         | 2            | 100          | **0.979** | 0.976    |
| SMOTE         | 9         | 2            | 500          | 0.977     | 0.974    |
| ADASYN        | 9         | 1            | 100          | 0.976     | 0.973    |

## AdaBoost

| Over Sampling | learning_rate | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | ------------ | --------- | -------- |
| Random        | 0.1           | 450          | **0.978** | 0.975    |
| SMOTE         | 0.1           | 500          | 0.977     | 0.973    |
| ADASYN        | 1             | 500          | 0.974     | 0.969    |


## Gradient Boosting

| Over Sampling | learning_rate | max_depth | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | --------- | ------------ | --------- | -------- |
| Random        | 0.01          | 3         | 1000         | **0.979** | 0.976    |
| SMOTE         | 0.1           | 3         | 200          | 0.978     | 0.975    |
| ADASYN        | 0.01          | 5         | 1000         | 0.976     | 0.972    |

## SVM

| Over Sampling | kernel | C   | degree | val_auc | test_auc |
| ------------- | ------ | --- | ------ | ------- | -------- |
| Random        | rbf    | 100 | -      | 0.962   | 0.954    |
| SMOTE         | rbf    | 100 | -      | 0.963   | 0.956    |
| ADASYN        | rbf    | 100 | -      | 0.957   | 0.949    |

## XGBoost

| Over Sampling | learning_rate | max_depth | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | --------- | ------------ | --------- | -------- |
| Random        | 0.1           | 3         | 120          | **0.979** | 0.976    |
| SMOTE         | 0.1           | 3         | 180          | 0.978     | 0.975    |
| ADASYN        | 0.1           | 6         | 120          | 0.976     | 0.971    |
