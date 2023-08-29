## Model Tuning Results

## Logistic Regression

| Over Sampling | C     | max_iter | penalty | solver    | val_auc   | test_auc |
| ------------- | ----- | -------- | ------- | --------- | --------- | -------- |
| Random        | 0.001 | 100      | l1      | liblinear | **0.927** | 0.925    |
| SMOTE         | 0.001 | 100      | l1      | liblinear | 0.923     | 0.924    |
| ADASYN        | 0.001 | 500      | l1      | saga      | 0.910     | 0.908    |

## Decision Tree

| Over Sampling | criterion | max_depth | max_features | min_impurity_decrease | min_samples_leaf | val_auc   | test_auc |
| ------------- | --------- | --------- | ------------ | --------------------- | ---------------- | --------- | -------- |
| Random        | entropy   | 6         | 5            | 0.0                   | 15               | 0.981     | 0.982    |
| SMOTE         | entropy   | 5         | 5            | 0.0                   | 10               | **0.982** | 0.981    |
| ADASYN        | entropy   | 6         | 6            | 0.0                   | 15               | 0.980     | 0.982    |

## Random Forest

| Over Sampling | max_depth | max_features | n_estimators | val_auc   | test_auc |
| ------------- | --------- | ------------ | ------------ | --------- | -------- |
| Random        | 9         | 1            | 500          | **0.986** | 0.987    |
| SMOTE         | 9         | 1            | 500          | 0.985     | 0.987    |
| ADASYN        | 9         | 2            | 300          | 0.984     | 0.986    |

## AdaBoost

| Over Sampling | learning_rate | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | ------------ | --------- | -------- |
| Random        | 0.1           | 500          | **0.985** | 0.987    |
| SMOTE         | 0.1           | 500          | 0.984     | 0.986    |
| ADASYN        | 0.1           | 500          | 0.982     | 0.983    |


## Gradient Boosting

| Over Sampling | learning_rate | max_depth | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | --------- | ------------ | --------- | -------- |
| Random        | 0.1           | 3         | 200          | **0.986** | 0.986    |
| SMOTE         | 0.01          | 3         | 1000         | 0.986     | 0.986    |
| ADASYN        | 0.1           | 3         | 200          | 0.984     | 0.984    |

## SVM

| Over Sampling | kernel | C   | degree | val_auc | test_auc |
| ------------- | ------ | --- | ------ | ------- | -------- |
| Random        | rbf    | 100 | -      | 0.967   | 0.966    |
| SMOTE         | rbf    | 100 | -      | 0.963   | 0.962    |
| ADASYN        | rbf    | 100 | -      | 0.960   | 0.960    |

## XGBoost

| Over Sampling | learning_rate | max_depth | n_estimators | val_auc   | test_auc |
| ------------- | ------------- | --------- | ------------ | --------- | -------- |
| Random        | 0.1           | 3         | 100          | **0.986** | 0.987    |
| SMOTE         | 0.1           | 3         | 100          | 0.986     | 0.987    |
| ADASYN        | 0.1           | 5         | 100          | 0.984     | 0.985    |
