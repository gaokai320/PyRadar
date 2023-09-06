## Model Tuning Results

## Logistic Regression

| Over Sampling | C     | max_iter | penalty | solver    | val_auc   | test_auc |
| ------------- | ----- | -------- | ------- | --------- | --------- | -------- |
| Random        | 0.001 | 100      | l1      | liblinear | 0.886     | 0.917    |
| SMOTE         | 0.001 | 100      | l1      | liblinear | **0.887** | 0.919    |
| ADASYN        | 0.01  | 100      | l1      | liblinear | 0.873     | 0.905    |

## Decision Tree

| Over Sampling | criterion | max_depth | max_features | min_impurity_decrease | min_samples_leaf | val_auc   | test_auc |
| ------------- | --------- | --------- | ------------ | --------------------- | ---------------- | --------- | -------- |
| Random        | gini      | 19        | 6            | 0.0                   | 15               | 0.977     | 0.966    |
| SMOTE         | gini      | 19        | 3            | 0.0                   | 10               | **0.978** | 0.970    |
| ADASYN        | gini      | 18        | 4            | 0.0                   | 5                | 0.975     | 0.961    |

## Random Forest

| Over Sampling | max_depth | max_features | n_estimators | val_auc   | test_auc |
| ------------- | --------- | ------------ | ------------ | --------- | -------- |
| Random        | 9         | 6            | 300          | **0.980** | 0.983    |
| SMOTE         | 9         | 6            | 300          | 0.979     | 0.982    |
| ADASYN        | 9         | 6            | 200          | 0.968     | 0.983    |

## AdaBoost

| Over Sampling | learning_rate | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | ------------ | --------- | -------- |
| Random        | 1             | 500          | **0.950** | 0.978    |
| SMOTE         | 1             | 500          | 0.950     | 0.976    |
| ADASYN        | 1             | 500          | 0.931     | 0.981    |


## Gradient Boosting

| Over Sampling | learning_rate | max_depth | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | --------- | ------------ | --------- | -------- |
| Random        | 0.1           | 9         | 1000         | **0.995** | 0.985    |
| SMOTE         | 0.1           | 9         | 1000         | 0.994     | 0.984    |
| ADASYN        | 0.1           | 9         | 1000         | 0.993     | 0.982    |

## SVM

| Over Sampling | kernel | C   | degree | val_auc   | test_auc |
| ------------- | ------ | --- | ------ | --------- | -------- |
| Random        | rbf    | 100 | -      | **0.967** | 0.966    |
| SMOTE         | rbf    | 100 | -      | 0.963     | 0.962    |
| ADASYN        | rbf    | 100 | -      | 0.960     | 0.960    |

## XGBoost

| Over Sampling | learning_rate | max_depth | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | --------- | ------------ | --------- | -------- |
| Random        | 0.1           | 10        | 200          | 0.992     | 0.984    |
| SMOTE         | 0.5           | 9         | 100          | **0.992** | 0.980    |
| ADASYN        | 0.5           | 10        | 120          | 0.991     | 0.982    |
