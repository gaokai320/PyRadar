import argparse
import csv
import warnings

import pandas as pd
from imblearn.over_sampling import RandomOverSampler
from imblearn.pipeline import Pipeline
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    AdaBoostClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.preprocessing import RobustScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.utils import parallel_backend
from xgboost import XGBClassifier

random_state = 42

warnings.filterwarnings(action="ignore", category=UserWarning)


def prepare_data(upsample: bool = True):
    feature_columns = [
        "num_phantom_pyfiles",
        "setup_change",
        "name_similarity",
        "tag_match",
        "num_maintainers",
        "num_maintainer_pkgs",
        # "maintainer_max_downloads",
    ]
    df = pd.read_csv("data/validator_dataset.csv", keep_default_na=False)
    train_df, test_df = train_test_split(df)
    if upsample:
        train_df = pd.concat(
            [
                train_df,
                train_df[
                    (train_df["label"] == 0) & (train_df["setup_change"] == 1)
                ].sample(frac=0.5, replace=True, random_state=random_state),
                train_df[
                    (train_df["label"] == 1) & (train_df["setup_change"] == 0)
                ].sample(frac=10, replace=True, random_state=random_state),
            ],
            ignore_index=True,
        )
    X_train = train_df[feature_columns]
    Y_train = train_df["label"]

    return X_train, Y_train, test_df[feature_columns], test_df["label"]


def dump_results(model_name, model):
    feature_columns = [
        "num_phantom_pyfiles",
        "setup_change",
        "name_similarity",
        "tag_match",
        "num_maintainers",
        "num_maintainer_pkgs",
        # "maintainer_max_downloads",
    ]
    df = pd.read_csv("data/validator_dataset.csv", keep_default_na=False)

    X = df[feature_columns]
    Y = df["label"]

    with open(f"data/{model_name}_prediction.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["true", "score"])
        for y_true, y_score in zip(Y, model.predict_proba(X)[:, 1]):
            writer.writerow([y_true, y_score])

    dump(model, f"models/best_{model_name}.joblib")


def grid_search(
    X_train,
    Y_train,
    X_test,
    Y_test,
    steps,
    params,
    model_name,
    n_jobs: int = 1,
    cv: int = 10,
    verbose: int = 0,
):
    pipeline = Pipeline(
        [("oversampling", RandomOverSampler(random_state=random_state))] + steps
    )
    grid = GridSearchCV(
        pipeline,
        param_grid=params,
        scoring="roc_auc",
        refit=True,
        n_jobs=n_jobs,
        cv=cv,
        verbose=verbose,
    )
    with parallel_backend("multiprocessing"):
        grid.fit(X_train, Y_train)
        test_auc = roc_auc_score(
            Y_test, grid.best_estimator_.predict_proba(X_test)[:, 1]
        )
        print(grid.best_params_)
        print(grid.best_score_, test_auc)

        dump_results(model_name, grid.best_estimator_)


def fit_lr(X_train, Y_train, X_test, Y_test, n_jobs: int = 1, cv: int = 10):
    ct = ColumnTransformer(
        [
            (
                "num_preprocess",
                RobustScaler(),
                [
                    "num_phantom_pyfiles",
                    "name_similarity",
                    "num_maintainers",
                    "num_maintainer_pkgs",
                    # "maintainer_max_downloads",
                ],
            )
        ]
    )

    params = dict(
        logisticregression__C=[0.001, 0.01, 0.1, 1, 10, 100],
        logisticregression__penalty=["l1", "l2"],
        logisticregression__solver=["liblinear", "saga"],
        logisticregression__max_iter=[100, 200, 500, 1000],
    )

    steps = [
        ("columntransformer", ct),
        ("logisticregression", LogisticRegression(random_state=random_state)),
    ]
    grid_search(
        X_train=X_train,
        Y_train=Y_train,
        X_test=X_test,
        Y_test=Y_test,
        steps=steps,
        params=params,
        model_name="lr",
        n_jobs=n_jobs,
        cv=cv,
    )


def fit_dt(X_train, Y_train, X_test, Y_test, n_jobs: int = 1, cv: int = 10):
    params = dict(
        decisiontreeclassifier__criterion=["gini", "entropy"],
        decisiontreeclassifier__max_depth=list(range(3, 21, 1)),
        decisiontreeclassifier__min_samples_leaf=[5, 10, 15],
        decisiontreeclassifier__min_impurity_decrease=[0.0, 0.1, 0.2],
        decisiontreeclassifier__max_features=list(range(1, X_train.shape[1])),
    )
    steps = [
        ("decisiontreeclassifier", DecisionTreeClassifier(random_state=random_state))
    ]
    grid_search(
        X_train=X_train,
        Y_train=Y_train,
        X_test=X_test,
        Y_test=Y_test,
        steps=steps,
        params=params,
        model_name="dt",
        n_jobs=n_jobs,
        cv=cv,
    )


def fit_rf(X_train, Y_train, X_test, Y_test, n_jobs: int = 1, cv: int = 10):
    params = dict(
        randomforestclassifier__n_estimators=list(range(20, 100, 20))
        + list(range(100, 600, 100)),
        randomforestclassifier__max_depth=list(range(1, 10, 1)),
        randomforestclassifier__max_features=list(range(1, X_train.shape[1])),
    )

    steps = [
        ("randomforestclassifier", RandomForestClassifier(random_state=random_state))
    ]
    grid_search(
        X_train=X_train,
        Y_train=Y_train,
        X_test=X_test,
        Y_test=Y_test,
        steps=steps,
        params=params,
        model_name="rf",
        n_jobs=n_jobs,
        cv=cv,
    )


def fit_svm(X_train, Y_train, X_test, Y_test, n_jobs: int = 1, cv: int = 10):
    params = [
        # {"svc__C": [0.1, 1, 10, 100], "svc__kernel": ["linear"]},
        {
            "svc__C": [0.1, 1, 10, 100],
            "svc__kernel": ["rbf", "sigmoid"],
        },
        # {
        #     "svc__C": [0.1, 1, 10, 100],
        #     "svc__kernel": ["poly"],
        #     "svc__degree": [2, 3, 4, 5],
        # },
    ]

    steps = [
        ("robustscaler", RobustScaler()),
        ("svc", SVC(probability=True, random_state=random_state)),
    ]

    grid_search(
        X_train=X_train,
        Y_train=Y_train,
        X_test=X_test,
        Y_test=Y_test,
        steps=steps,
        params=params,
        model_name="svm",
        n_jobs=n_jobs,
        cv=cv,
        verbose=1,
    )


def fit_ada(X_train, Y_train, X_test, Y_test, n_jobs: int = 1, cv: int = 10):
    params = dict(
        adaboostclassifier__n_estimators=list(range(20, 100, 20))
        + list(range(100, 550, 50)),
        adaboostclassifier__learning_rate=[0.01, 0.1, 1],
    )

    steps = [("adaboostclassifier", AdaBoostClassifier(random_state=random_state))]

    grid_search(
        X_train=X_train,
        Y_train=Y_train,
        X_test=X_test,
        Y_test=Y_test,
        steps=steps,
        params=params,
        model_name="ada",
        n_jobs=n_jobs,
        cv=cv,
    )


def fit_gb(X_train, Y_train, X_test, Y_test, n_jobs: int = 1, cv: int = 10):
    params = dict(
        gradientboostingclassifier__learning_rate=[0.01, 0.1, 1],
        gradientboostingclassifier__n_estimators=[100, 200, 500, 1000],
        gradientboostingclassifier__max_depth=list(range(3, 11, 1)),
    )

    steps = [
        (
            "gradientboostingclassifier",
            GradientBoostingClassifier(random_state=random_state),
        )
    ]
    grid_search(
        X_train=X_train,
        Y_train=Y_train,
        X_test=X_test,
        Y_test=Y_test,
        steps=steps,
        params=params,
        model_name="gb",
        n_jobs=n_jobs,
        cv=cv,
    )


def fit_xgb(X_train, Y_train, X_test, Y_test, n_jobs: int = 1, cv: int = 10):
    params = dict(
        xgbclassifier__n_estimators=list(range(100, 220, 20)),
        xgbclassifier__max_depth=list(range(2, 11, 1)),
        xgbclassifier__learning_rate=[0.01, 0.1, 0.5],
    )

    steps = [
        (
            "xgbclassifier",
            XGBClassifier(random_state=random_state, tree_method="hist", n_jobs=16),
        )
    ]
    grid_search(
        X_train=X_train,
        Y_train=Y_train,
        X_test=X_test,
        Y_test=Y_test,
        steps=steps,
        params=params,
        model_name="xgb",
        n_jobs=16,
        cv=cv,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lr", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--dt", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--rf", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--svm", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--ada", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--gb", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--xgb", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--all", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--n_jobs", default=1, type=int)
    parser.add_argument("--cv", default=10, type=int)
    args = parser.parse_args()

    X_train, Y_train, X_test, Y_test = prepare_data()

    if args.all:
        args.lr = True
        args.dt = True
        args.rf = True
        args.svm = True
        args.ada = True
        args.gb = True
        args.xgb = True

    if args.lr:
        fit_lr(X_train, Y_train, X_test, Y_test, args.n_jobs, args.cv)

    if args.dt:
        fit_dt(X_train, Y_train, X_test, Y_test, args.n_jobs, args.cv)

    if args.rf:
        fit_rf(X_train, Y_train, X_test, Y_test, args.n_jobs, args.cv)

    if args.svm:
        fit_svm(X_train, Y_train, X_test, Y_test, args.n_jobs, args.cv)

    if args.ada:
        fit_ada(X_train, Y_train, X_test, Y_test, args.n_jobs, args.cv)

    if args.gb:
        fit_gb(X_train, Y_train, X_test, Y_test, args.n_jobs, args.cv)

    if args.xgb:
        fit_xgb(X_train, Y_train, X_test, Y_test, args.n_jobs, args.cv)
