import logging
import pickle
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from imblearn.ensemble import BalancedRandomForestClassifier, EasyEnsembleClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

# Get module logger
logger = logging.getLogger(__name__)

MARKET_CAP_MIN = 5000000
PROD_MODEL_FILE = "app/prod.model"
FEATURES = [
    "buysell_m5_ratio",
    "buysell_h1_ratio",
    "market_cap_liquidity_ratio",
    "market_cap_volume_ratio",
    "price_change_h24",
]


class DexModel:

    def __init__(self):
        self.model = self.load_model(PROD_MODEL_FILE)

    def _generate_features(self, df_in: pd.DataFrame):
        df = df_in.copy()
        df.loc[:, "buysell_m5_ratio"] = df["buys_m5"] / df["sells_m5"].replace(
            0, float("nan")
        )
        df.loc[:, "buysell_h1_ratio"] = df["buys_h1"] / df["sells_h1"].replace(
            0, float("nan")
        )
        df.loc[:, "market_cap_liquidity_ratio"] = df["market_cap"] / df[
            "liquidity_usd"
        ].replace(0, float("nan"))
        df.loc[:, "market_cap_volume_ratio"] = df["market_cap"] / df[
            "volume_h24"
        ].replace(0, float("nan"))

        # targets
        df.loc[:, "gain_after_5"] = df["T10m_diff_pct"] > 20
        df.loc[:, "gain_after_30"] = df["T30m_diff_pct"] > 20

        df.dropna(inplace=True)  # Drop NaN values
        return df

    def _filter_data(self, in_df: pd.DataFrame):
        df = in_df.copy()
        df.drop(
            columns=[
                "dex_id",
                "T24h_diff_pct",
                "T8hr_diff_pct",
                "T3hr_diff_pct",
                "T1hr_diff_pct",
            ],
            inplace=True,
        )
        return df[df["market_cap"] > 5000000]

    # Compute Relative Strength Index (RSI)
    def compute_rsi(series, window=14):
        delta = series.diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def save_model(model: Any, filename: str):
        logger.info(f"saving model {type(model).__name__} to {filename}")
        with open(filename, "wb") as file:
            pickle.dump(model, file)

    @staticmethod
    def load_model(filename: str) -> Any:
        try:
            with open(filename, "rb") as file:
                return pickle.load(file)
        except Exception as e:
            logger.error(f"Error opening {PROD_MODEL_FILE}", exc_info=True)
            return None

    def predict_target(self, data: dict) -> int:
        """
        Returns:
        int: Predicted target value.
            - Typically, this will be either 0 or 1 in a binary classification problem.
            - 0 might indicate one class (e.g., "Sell" or "Negative Outcome"),
            while 1 might indicate the opposite class (e.g., "Buy" or "Positive Outcome").
            - The exact meaning depends on the training data and problem definition.
        """
        if not self.model:
            raise Exception("No model to predict with")

        if not all(col in data for col in FEATURES):
            raise ValueError("Input data is missing required features")

        X = pd.DataFrame([data])  # Convert dictionary to DataFrame
        prediction = self.model.predict(X)[0]  # Predict a single value
        return prediction

    # Main ML function
    def train_crypto_models(self, df: pd.DataFrame):
        df = self._filter_data(df)
        df = self._generate_features(df)

        # Define features and target variable
        X = df[FEATURES]
        y = df["gain_after_30"]

        # Split dataset into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, shuffle=True
        )

        # Normalize the features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # ✅ Convert NumPy arrays back to DataFrame with feature names
        X_train_scaled = pd.DataFrame(
            X_train_scaled, columns=FEATURES, index=X_train.index
        )
        X_test_scaled = pd.DataFrame(
            X_test_scaled, columns=FEATURES, index=X_test.index
        )

        # Train a Random Forest model
        randomForest = RandomForestClassifier(
            class_weight="balanced", n_estimators=2000, random_state=42
        )
        xgbClassifier = xgb.XGBClassifier(
            scale_pos_weight=(len(y_train) - sum(y_train))
            / sum(
                y_train
            ),  # Handling class imbalance (similar to class_weight='balanced')
            n_estimators=2000,  # Number of boosting rounds
            random_state=42,  # For reproducibility
            use_label_encoder=True,  # To avoid warning (optional)
            eval_metric="logloss",  # Metric used for model evaluation during training
            learning_rate=0.01,  # Learning rate (adjust for performance)
            max_depth=6,  # Maximum depth of trees
            subsample=0.8,  # Subsampling rate (fraction of samples used for each tree)
            colsample_bytree=0.8,  # Fraction of features used for each tree
        )
        logisticRegression = LogisticRegression(
            class_weight="balanced", random_state=42, max_iter=1000
        )  # class_weight='balanced' helps with imbalance
        supportVectorMachine = SVC(
            class_weight="balanced", kernel="rbf", random_state=42
        )
        randomForestBalanced = BalancedRandomForestClassifier(
            n_estimators=200, random_state=42
        )
        eec = EasyEnsembleClassifier(n_estimators=50, random_state=42)

        models = [
            randomForest,
            randomForestBalanced,
            xgbClassifier,
            logisticRegression,
            supportVectorMachine,
            eec,
        ]
        prod_model = supportVectorMachine
        for model in models:
            model.fit(X_train_scaled, y_train)

            # Predictions
            y_pred = model.predict(X_test_scaled)

            # Evaluate the model
            accuracy = accuracy_score(y_test, y_pred)
            logger.info(f"{type(model).__name__} Accuracy: {accuracy}")
            logger.info(classification_report(y_test, y_pred))

        self.save_model(prod_model, PROD_MODEL_FILE)


def test_predict():
    model = DexModel()
    buysell_m5_ratio = 40 / 28
    buysell_h1_ratio = 2587 / 2479
    market_cap_liquidity_ratio = 72122.95 / 10489.91
    market_cap_volume_ratio = 72122.95 / 388108.97
    price_change_h24 = 1034.72
    data = {
        "buysell_m5_ratio": buysell_m5_ratio,
        "buysell_h1_ratio": buysell_h1_ratio,
        "market_cap_liquidity_ratio": market_cap_liquidity_ratio,
        "market_cap_volume_ratio": market_cap_volume_ratio,
        "price_change_h24": price_change_h24,
    }
    result = model.predict_target(data)
    logger.info(result)
