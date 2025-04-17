from dataclasses import dataclass
import logging
import os
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

MARKET_CAP_MIN = 100000

FEATURES = [
    "buysell_m5_ratio",
    "buysell_h1_ratio",
    "market_cap_liquidity_ratio",
    "market_cap_volume_ratio",
    "price_change_h24",
]
TARGETS = [
    "gain_after_1",
    "gain_after_6",
    "gain_after_20",
    "gain_after_60"
]
MODEL_PREFS = {
    TARGETS[0] : 2,
    TARGETS[1] : 1,
    TARGETS[2] : 0,
    TARGETS[3] : 1,
}

@dataclass
class ModelScaler:
    model: Any
    scaler: StandardScaler

    def save(self, prefix: str) -> None:
        directory = "app"
        os.makedirs(directory, exist_ok=True)
        directory = "app/models"
        os.makedirs(directory, exist_ok=True)
        model_path = os.path.join(directory, f"{prefix}.model")
        scaler_path = os.path.join(directory, f"{prefix}.scaler")
        
        with open(model_path, "wb") as f:
            pickle.dump(self.model, f)
        with open(scaler_path, "wb") as f:
            pickle.dump(self.scaler, f)

    @classmethod
    def load(cls, prefix: str) -> "ModelScaler":
        directory: str = "app/models"
        model_path = os.path.join(directory, f"{prefix}.model")
        scaler_path = os.path.join(directory, f"{prefix}.scaler")
        
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
        except Exception as e:
            return None

        try:
            with open(scaler_path, "rb") as f:
                scaler = pickle.load(f)
        except Exception as e:
            return None

        return cls(model=model, scaler=scaler)
    
    def predict_target(self, data: dict) -> bool:
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
        X_scaled = pd.DataFrame(self.scaler.transform(X), columns=X.columns)
        prediction = self.model.predict(X_scaled)[0]  # Predict a single value
        return bool(prediction)

class DexModel:

    def __init__(self):
        self.models = {}
        for target in TARGETS:
            self.models[target] = ModelScaler.load(target)

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
        df.loc[:, "gain_after_1"] = df["M0001_diff_pct"] > 10
        df.loc[:, "gain_after_6"] = df["M0006_diff_pct"] > 10
        df.loc[:, "gain_after_20"] = df["M0020_diff_pct"] > 10
        df.loc[:, "gain_after_60"] = df["M0060_diff_pct"] > 10

        df.dropna(inplace=True)  # Drop NaN values
        return df

    def _filter_data(self, in_df: pd.DataFrame):
        df = in_df.copy()
        df.drop(
            columns=[
                "dex_id"
            ],
            inplace=True,
        )
        return df[df["market_cap"] > MARKET_CAP_MIN]

    # Compute Relative Strength Index (RSI)
    def compute_rsi(series, window=14):
        delta = series.diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    # Main ML function
    def train_crypto_models(self, df: pd.DataFrame):
        df = self._filter_data(df)
        df = self._generate_features(df)
        
        for target in TARGETS:
            model_scaler = self.get_best_model(df, target)
            logger.info(f"Saving {type(model_scaler.model).__name__} for {target}")
            model_scaler.save(target)

    def get_predictions(self, data: dict):
        predictions = {}
        for target in TARGETS:
            prediction = self.models[target].predict_target(data)
            predictions[target] = prediction
        return predictions

    def get_best_model(self, df: pd.DataFrame, target: str) -> ModelScaler:
        # Define features and target variable
        X = df[FEATURES]
        y = df[target]
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

        logger.info(f"Train size {len(X_train_scaled)} test size {len(X_test_scaled)}")

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
        best_model = None
        best_accuracy = 0
        for model in models:
            model.fit(X_train_scaled, y_train)

            # Predictions
            y_pred = model.predict(X_test_scaled)

            # Evaluate the model
            accuracy = accuracy_score(y_test, y_pred)
            if accuracy > best_accuracy:
                best_model = model
                best_accuracy = accuracy
            logger.info(f"{type(model).__name__} Accuracy: {accuracy}")
            print(classification_report(y_test, y_pred))
        chosen_model_index = MODEL_PREFS[target]
        chosen_model = models[chosen_model_index]
        return ModelScaler(chosen_model, scaler) 


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
    result = model.get_predictions(data)
    print(result)

test_predict()